"""Persistence for FUTBOARD, on Neon Postgres.

The only module in the codebase that speaks SQL. Everything above it works in
terms of the models in `app.futboard_models`, so the API layer never builds a
query and the schema can change without touching a route.

## Why the pool is configured the way it is

Neon's free plan suspends the compute after five minutes with no connections,
and that cannot be turned off. Three consequences shape this file:

* `min_size=0` — holding a connection open would keep the compute awake, and a
  compute that never sleeps burns 182 CU-hours a month against a 100 CU-hour
  allowance. Sleeping is the correct behaviour, not a problem to work around.
* `check=ConnectionPool.check_connection` — a pooled connection that survived a
  suspend is dead. Without the check the first request after a quiet spell fails
  instead of reconnecting.
* The `-pooler` host belongs in the connection string. It makes the reconnect
  after a wake cheap; a direct connection pays the full handshake.

Measured cold connect through the pooler: ~0.4 s. The frontend shows a loading
state from the first paint because of it.

## Schema notes

Every goal is a row, and `goals.player_id` is nullable. A team's score is the
count of its rows, so the score is right whether or not anyone recorded who
scored — there is no separate total that could drift away from the detail.

`match_players` is keyed on `(match_id, player_id)` rather than including the
team, which is what stops one player being registered on both sides of the same
match.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg import errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.futboard_models import (
    Match,
    MatchCreate,
    MatchGoal,
    Player,
    PlayerStats,
    Stats,
    Team,
    TeamStats,
)

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id         bigserial PRIMARY KEY,
    name       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_ip text
);
CREATE UNIQUE INDEX IF NOT EXISTS teams_name_lower_key ON teams (lower(name));

CREATE TABLE IF NOT EXISTS players (
    id         bigserial PRIMARY KEY,
    name       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_ip text
);
CREATE UNIQUE INDEX IF NOT EXISTS players_name_lower_key ON players (lower(name));

CREATE TABLE IF NOT EXISTS team_players (
    team_id   bigint NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    player_id bigint NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    PRIMARY KEY (team_id, player_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id                   bigserial PRIMARY KEY,
    home_team_id         bigint NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    away_team_id         bigint NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    played_at            timestamptz NOT NULL DEFAULT now(),
    half_minutes         int NOT NULL,
    sub_interval_minutes int NOT NULL,
    created_ip           text,
    CONSTRAINT matches_distinct_teams CHECK (home_team_id <> away_team_id)
);
CREATE INDEX IF NOT EXISTS matches_played_at_idx ON matches (played_at DESC);

CREATE TABLE IF NOT EXISTS match_players (
    match_id  bigint NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_id   bigint NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    player_id bigint NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    PRIMARY KEY (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS goals (
    id        bigserial PRIMARY KEY,
    match_id  bigint NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_id   bigint NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    player_id bigint REFERENCES players(id) ON DELETE SET NULL,
    half      smallint NOT NULL CHECK (half IN (1, 2)),
    minute    int NOT NULL CHECK (minute >= 0)
);
CREATE INDEX IF NOT EXISTS goals_match_idx ON goals (match_id);
CREATE INDEX IF NOT EXISTS goals_player_idx ON goals (player_id);
"""


class FutboardError(Exception):
    """A request that cannot be satisfied, with a message safe to show a user."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FutboardStore:
    """Postgres-backed storage. Constructing it does not open a connection."""

    def __init__(
        self,
        database_url: str | None,
        *,
        max_teams: int = 200,
        max_players: int = 500,
    ) -> None:
        self._url = database_url
        self._max_teams = max_teams
        self._max_players = max_players
        self._pool: ConnectionPool | None = None

    @property
    def available(self) -> bool:
        return bool(self._url)

    # --- connection ---------------------------------------------------------

    def _get_pool(self) -> ConnectionPool:
        if not self._url:
            raise FutboardError("FUTBOARD is not configured on this deployment.", 503)
        if self._pool is None:
            self._pool = ConnectionPool(
                self._url,
                min_size=0,
                max_size=2,
                max_idle=60.0,
                timeout=25.0,
                check=ConnectionPool.check_connection,
                open=True,
                kwargs={"row_factory": dict_row},
            )
            logger.info("FUTBOARD pool created (min=0, max=2)")
        return self._pool

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def migrate(self) -> None:
        """Create the schema if it is not there. Safe to run repeatedly."""
        with self._get_pool().connection() as conn:
            conn.execute(SCHEMA)
        logger.info("FUTBOARD schema ensured")

    def health(self) -> bool:
        with self._get_pool().connection() as conn:
            conn.execute("SELECT 1")
        return True

    # --- teams --------------------------------------------------------------

    def list_teams(self) -> list[Team]:
        with self._get_pool().connection() as conn:
            rows = conn.execute(
                """
                SELECT t.id, t.name, count(tp.player_id) AS player_count
                FROM teams t
                LEFT JOIN team_players tp ON tp.team_id = t.id
                GROUP BY t.id, t.name
                ORDER BY lower(t.name)
                """
            ).fetchall()
        return [Team(**row) for row in rows]

    def create_team(self, name: str, client_ip: str | None) -> Team:
        with self._get_pool().connection() as conn:
            total = conn.execute("SELECT count(*) AS n FROM teams").fetchone()["n"]
            if total >= self._max_teams:
                raise FutboardError("The team limit for this site has been reached.", 409)
            try:
                row = conn.execute(
                    "INSERT INTO teams (name, created_ip) VALUES (%s, %s) RETURNING id, name",
                    (name, client_ip),
                ).fetchone()
            except errors.UniqueViolation:
                raise FutboardError(f"A team called '{name}' already exists.", 409) from None
        return Team(id=row["id"], name=row["name"], player_count=0)

    # --- players ------------------------------------------------------------

    def list_players(self) -> list[Player]:
        with self._get_pool().connection() as conn:
            rows = conn.execute(
                """
                SELECT p.id, p.name,
                       coalesce(array_agg(tp.team_id ORDER BY tp.team_id)
                                FILTER (WHERE tp.team_id IS NOT NULL), '{}') AS team_ids
                FROM players p
                LEFT JOIN team_players tp ON tp.player_id = p.id
                GROUP BY p.id, p.name
                ORDER BY lower(p.name)
                """
            ).fetchall()
        return [Player(**row) for row in rows]

    def create_player(
        self, name: str, team_id: int | None, client_ip: str | None
    ) -> Player:
        with self._get_pool().connection() as conn:
            total = conn.execute("SELECT count(*) AS n FROM players").fetchone()["n"]
            if total >= self._max_players:
                raise FutboardError("The player limit for this site has been reached.", 409)
            try:
                row = conn.execute(
                    "INSERT INTO players (name, created_ip) VALUES (%s, %s) RETURNING id, name",
                    (name, client_ip),
                ).fetchone()
            except errors.UniqueViolation:
                raise FutboardError(f"A player called '{name}' already exists.", 409) from None

            team_ids: list[int] = []
            if team_id is not None:
                try:
                    conn.execute(
                        "INSERT INTO team_players (team_id, player_id) VALUES (%s, %s)",
                        (team_id, row["id"]),
                    )
                except errors.ForeignKeyViolation:
                    raise FutboardError("That team does not exist.", 404) from None
                team_ids = [team_id]
        return Player(id=row["id"], name=row["name"], team_ids=team_ids)

    def add_player_to_team(self, team_id: int, player_id: int) -> None:
        with self._get_pool().connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO team_players (team_id, player_id) VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (team_id, player_id),
                )
            except errors.ForeignKeyViolation:
                raise FutboardError("That team or player does not exist.", 404) from None

    def remove_player_from_team(self, team_id: int, player_id: int) -> None:
        with self._get_pool().connection() as conn:
            conn.execute(
                "DELETE FROM team_players WHERE team_id = %s AND player_id = %s",
                (team_id, player_id),
            )

    # --- matches ------------------------------------------------------------

    def save_match(self, match: MatchCreate, client_ip: str | None) -> int:
        """Persist a finished match in one transaction.

        All or nothing on purpose: a match row with half its goals missing would
        silently corrupt every statistic derived from it.
        """
        sides = {match.home_team_id, match.away_team_id}
        for goal in match.goals:
            if goal.team_id not in sides:
                raise FutboardError("A goal was credited to a team that did not play.", 400)

        overlap = set(match.home_player_ids) & set(match.away_player_ids)
        if overlap:
            raise FutboardError("A player cannot appear on both sides of a match.", 400)

        with self._get_pool().connection() as conn, conn.transaction():
            try:
                row = conn.execute(
                    """
                    INSERT INTO matches (home_team_id, away_team_id, half_minutes,
                                         sub_interval_minutes, created_ip)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        match.home_team_id,
                        match.away_team_id,
                        match.half_minutes,
                        match.sub_interval_minutes,
                        client_ip,
                    ),
                ).fetchone()
                match_id = row["id"]

                lineup = [
                    (match_id, match.home_team_id, pid) for pid in match.home_player_ids
                ] + [(match_id, match.away_team_id, pid) for pid in match.away_player_ids]
                if lineup:
                    conn.cursor().executemany(
                        "INSERT INTO match_players (match_id, team_id, player_id) VALUES (%s, %s, %s)",
                        lineup,
                    )

                if match.goals:
                    conn.cursor().executemany(
                        """
                        INSERT INTO goals (match_id, team_id, player_id, half, minute)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            (match_id, g.team_id, g.player_id, g.half, g.minute)
                            for g in match.goals
                        ],
                    )
            except errors.ForeignKeyViolation:
                raise FutboardError("A team or player in this match does not exist.", 404) from None
        return match_id

    def list_matches(self, limit: int = 20) -> list[Match]:
        with self._get_pool().connection() as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.played_at, m.half_minutes, m.sub_interval_minutes,
                       m.home_team_id, h.name AS home_team_name,
                       m.away_team_id, a.name AS away_team_name,
                       count(*) FILTER (WHERE g.team_id = m.home_team_id) AS home_goals,
                       count(*) FILTER (WHERE g.team_id = m.away_team_id) AS away_goals
                FROM matches m
                JOIN teams h ON h.id = m.home_team_id
                JOIN teams a ON a.id = m.away_team_id
                LEFT JOIN goals g ON g.match_id = m.id
                GROUP BY m.id, h.name, a.name
                ORDER BY m.played_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
            if not rows:
                return []

            goal_rows = conn.execute(
                """
                SELECT g.match_id, g.team_id, g.player_id, p.name AS player_name,
                       g.half, g.minute
                FROM goals g
                LEFT JOIN players p ON p.id = g.player_id
                WHERE g.match_id = ANY(%s)
                ORDER BY g.half, g.minute, g.id
                """,
                ([r["id"] for r in rows],),
            ).fetchall()

        by_match: dict[int, list[MatchGoal]] = {}
        for goal in goal_rows:
            by_match.setdefault(goal.pop("match_id"), []).append(MatchGoal(**goal))
        return [Match(**row, goals=by_match.get(row["id"], [])) for row in rows]

    # --- statistics ---------------------------------------------------------

    def stats(self) -> Stats:
        """Aggregates for the stats screen.

        Both halves are one query each rather than a join across everything: a
        player's goals and a player's appearances are counted over different
        tables, and combining them in a single statement produces a fan-out that
        multiplies both.
        """
        with self._get_pool().connection() as conn:
            player_rows = conn.execute(
                """
                WITH appearances AS (
                    SELECT player_id, count(*) AS matches
                    FROM match_players GROUP BY player_id
                ),
                scored AS (
                    SELECT player_id, count(*) AS goals
                    FROM goals WHERE player_id IS NOT NULL GROUP BY player_id
                ),
                squads AS (
                    SELECT tp.player_id,
                           array_agg(t.name ORDER BY lower(t.name)) AS teams
                    FROM team_players tp JOIN teams t ON t.id = tp.team_id
                    GROUP BY tp.player_id
                )
                SELECT p.id AS player_id, p.name,
                       coalesce(a.matches, 0) AS matches,
                       coalesce(s.goals, 0) AS goals,
                       coalesce(q.teams, '{}') AS teams
                FROM players p
                LEFT JOIN appearances a ON a.player_id = p.id
                LEFT JOIN scored s ON s.player_id = p.id
                LEFT JOIN squads q ON q.player_id = p.id
                ORDER BY coalesce(s.goals, 0) DESC, lower(p.name)
                """
            ).fetchall()

            team_rows = conn.execute(
                """
                WITH scored AS (
                    SELECT m.id AS match_id, m.home_team_id, m.away_team_id,
                           count(*) FILTER (WHERE g.team_id = m.home_team_id) AS home_goals,
                           count(*) FILTER (WHERE g.team_id = m.away_team_id) AS away_goals
                    FROM matches m
                    LEFT JOIN goals g ON g.match_id = m.id
                    GROUP BY m.id
                ),
                sides AS (
                    SELECT home_team_id AS team_id, home_goals AS gf, away_goals AS ga FROM scored
                    UNION ALL
                    SELECT away_team_id AS team_id, away_goals AS gf, home_goals AS ga FROM scored
                )
                SELECT t.id AS team_id, t.name,
                       count(s.team_id) AS played,
                       count(*) FILTER (WHERE s.gf > s.ga) AS won,
                       count(*) FILTER (WHERE s.gf = s.ga AND s.team_id IS NOT NULL) AS drawn,
                       count(*) FILTER (WHERE s.gf < s.ga) AS lost,
                       coalesce(sum(s.gf), 0) AS goals_for,
                       coalesce(sum(s.ga), 0) AS goals_against
                FROM teams t
                LEFT JOIN sides s ON s.team_id = t.id
                GROUP BY t.id, t.name
                ORDER BY count(*) FILTER (WHERE s.gf > s.ga) DESC,
                         coalesce(sum(s.gf), 0) - coalesce(sum(s.ga), 0) DESC,
                         lower(t.name)
                """
            ).fetchall()

        return Stats(
            players=[
                PlayerStats(
                    **row,
                    goals_per_match=round(row["goals"] / row["matches"], 2)
                    if row["matches"]
                    else 0.0,
                )
                for row in player_rows
            ],
            teams=[
                TeamStats(**row, goal_difference=row["goals_for"] - row["goals_against"])
                for row in team_rows
            ],
        )
