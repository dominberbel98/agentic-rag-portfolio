"""FUTBOARD: input bounds, and a round trip against a real Postgres.

Two tiers, the same split the golden-questions suite uses.

*Validation* runs everywhere with no database. It is the tier that matters most,
because FUTBOARD accepts writes from anyone: every bound here is the difference
between a shared scoreboard and an open landfill.

*Storage* needs `FUTBOARD_DATABASE_URL` and skips with a stated reason when it is
absent. It never touches the real tables — the fixture creates a throwaway
schema, points the connection's `search_path` at it, and drops it afterwards, so
running the suite cannot damage the data Domingo and his friends have recorded.
The direct host is used rather than the pooler, because the pooler does not
reliably honour a `search_path` set at connection time and the isolation is the
whole point.
"""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.futboard_models import (
    MAX_GOALS_PER_MATCH,
    MAX_NAME_LENGTH,
    MAX_ROSTER_PER_SIDE,
    GoalInput,
    MatchCreate,
    PlayerCreate,
    TeamCreate,
)

TEST_SCHEMA = "futboard_pytest"


# ── validation: no database needed ──────────────────────────────────────────


def test_name_whitespace_is_collapsed():
    """'Los  Pibes' and 'Los Pibes' must not become two different teams."""
    assert TeamCreate(name="  Los   Pibes  ").name == "Los Pibes"


@pytest.mark.parametrize("name", ["", "   ", "\t\n", "---", "...", "###"])
def test_names_without_a_letter_or_digit_are_rejected(name):
    with pytest.raises(ValidationError):
        TeamCreate(name=name)


def test_names_are_capped():
    TeamCreate(name="a" * MAX_NAME_LENGTH)
    with pytest.raises(ValidationError):
        TeamCreate(name="a" * (MAX_NAME_LENGTH + 1))


def test_a_player_can_be_registered_without_a_team():
    assert PlayerCreate(name="Dani").team_id is None


def _match(**overrides):
    payload = {
        "home_team_id": 1,
        "away_team_id": 2,
        "half_minutes": 25,
        "sub_interval_minutes": 5,
        "home_player_ids": [10, 11],
        "away_player_ids": [12],
        "goals": [],
    }
    payload.update(overrides)
    return MatchCreate(**payload)


def test_a_team_cannot_play_itself():
    with pytest.raises(ValidationError):
        _match(away_team_id=1)


def test_a_player_cannot_be_listed_twice_on_one_side():
    with pytest.raises(ValidationError):
        _match(home_player_ids=[10, 10])


def test_a_goal_without_a_scorer_is_valid():
    """The normal case when nobody noted who scored, not an error."""
    goal = GoalInput(team_id=1, player_id=None, half=1, minute=12)
    assert goal.player_id is None


@pytest.mark.parametrize("half", [0, 3, -1])
def test_goals_belong_to_one_of_two_halves(half):
    with pytest.raises(ValidationError):
        GoalInput(team_id=1, player_id=None, half=half, minute=1)


def test_the_roster_and_goal_lists_are_bounded():
    with pytest.raises(ValidationError):
        _match(home_player_ids=list(range(100, 100 + MAX_ROSTER_PER_SIDE + 1)))
    with pytest.raises(ValidationError):
        _match(
            goals=[
                GoalInput(team_id=1, player_id=None, half=1, minute=1)
                for _ in range(MAX_GOALS_PER_MATCH + 1)
            ]
        )


@pytest.mark.parametrize("minutes", [0, 61])
def test_half_length_is_bounded(minutes):
    with pytest.raises(ValidationError):
        _match(half_minutes=minutes)


# ── storage: needs a database ───────────────────────────────────────────────


def _database_url() -> str | None:
    url = os.environ.get("FUTBOARD_DATABASE_URL")
    if not url:
        env_file = Path(__file__).resolve().parents[1] / "backend" / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("FUTBOARD_DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    return url or None


@pytest.fixture(scope="module")
def store():
    url = _database_url()
    if not url:
        pytest.skip("FUTBOARD_DATABASE_URL is not set; storage tests need a database")

    import psycopg

    from app.services.futboard_store import FutboardStore

    direct = url.replace("-pooler", "")
    separator = "&" if "?" in direct else "?"
    options = urllib.parse.quote(f"-c search_path={TEST_SCHEMA}")
    scoped = f"{direct}{separator}options={options}"

    with psycopg.connect(direct, connect_timeout=25) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
        conn.execute(f"CREATE SCHEMA {TEST_SCHEMA}")
        conn.commit()

    instance = FutboardStore(scoped)
    instance.migrate()
    yield instance
    instance.close()

    with psycopg.connect(direct, connect_timeout=25) as conn:
        conn.execute(f"DROP SCHEMA {TEST_SCHEMA} CASCADE")
        conn.commit()


@pytest.fixture(scope="module")
def played(store):
    """One recorded match, reused by the assertions below."""
    home = store.create_team("Los Pibes", "127.0.0.1")
    away = store.create_team("FC Resaca", "127.0.0.1")
    dani = store.create_player("Dani", home.id, "127.0.0.1")
    javi = store.create_player("Javi", home.id, "127.0.0.1")
    nacho = store.create_player("Nacho", away.id, "127.0.0.1")
    # The explicit requirement: a player turns out for more than one team.
    store.add_player_to_team(away.id, javi.id)

    match_id = store.save_match(
        MatchCreate(
            home_team_id=home.id,
            away_team_id=away.id,
            half_minutes=25,
            sub_interval_minutes=5,
            home_player_ids=[dani.id, javi.id],
            away_player_ids=[nacho.id],
            goals=[
                GoalInput(team_id=home.id, player_id=dani.id, half=1, minute=4),
                # Scored, but nobody recorded by whom.
                GoalInput(team_id=home.id, player_id=None, half=1, minute=11),
                GoalInput(team_id=away.id, player_id=nacho.id, half=2, minute=31),
            ],
        ),
        "127.0.0.1",
    )
    return {
        "match_id": match_id,
        "home": home,
        "away": away,
        "dani": dani,
        "javi": javi,
        "nacho": nacho,
    }


def test_an_unattributed_goal_still_counts_for_its_team(store, played):
    """The point of the nullable scorer: the score is right regardless."""
    match = store.list_matches()[0]
    assert (match.home_goals, match.away_goals) == (2, 1)
    unattributed = [g for g in match.goals if g.player_id is None]
    assert len(unattributed) == 1
    assert unattributed[0].team_id == played["home"].id


def test_goals_come_back_in_playing_order(store, played):
    match = store.list_matches()[0]
    assert [(g.half, g.minute) for g in match.goals] == [(1, 4), (1, 11), (2, 31)]


def test_a_player_can_belong_to_several_teams(store, played):
    javi = next(p for p in store.list_players() if p.name == "Javi")
    assert {played["home"].id, played["away"].id} == set(javi.team_ids)


def test_player_stats_count_appearances_and_goals(store, played):
    by_name = {p.name: p for p in store.stats().players}
    assert (by_name["Dani"].matches, by_name["Dani"].goals) == (1, 1)
    # Played, did not score, and is not credited with the unattributed goal.
    assert (by_name["Javi"].matches, by_name["Javi"].goals) == (1, 0)
    assert sorted(by_name["Javi"].teams) == ["FC Resaca", "Los Pibes"]


def test_team_stats_record_the_result(store, played):
    by_name = {t.name: t for t in store.stats().teams}
    pibes, resaca = by_name["Los Pibes"], by_name["FC Resaca"]
    assert (pibes.played, pibes.won, pibes.drawn, pibes.lost) == (1, 1, 0, 0)
    assert (pibes.goals_for, pibes.goals_against, pibes.goal_difference) == (2, 1, 1)
    assert (resaca.played, resaca.won, resaca.lost) == (1, 0, 1)
    assert resaca.goal_difference == -1


def test_team_names_are_unique_regardless_of_case(store, played):
    from app.services.futboard_store import FutboardError

    with pytest.raises(FutboardError) as exc:
        store.create_team("los pibes", None)
    assert exc.value.status_code == 409


def test_a_goal_from_a_team_that_did_not_play_is_refused(store, played):
    from app.services.futboard_store import FutboardError

    other = store.create_team("Atletico Jueves", None)
    with pytest.raises(FutboardError):
        store.save_match(
            MatchCreate(
                home_team_id=played["home"].id,
                away_team_id=played["away"].id,
                half_minutes=25,
                sub_interval_minutes=5,
                goals=[GoalInput(team_id=other.id, player_id=None, half=1, minute=3)],
            ),
            None,
        )


def test_a_player_cannot_turn_out_for_both_sides_at_once(store, played):
    from app.services.futboard_store import FutboardError

    with pytest.raises(FutboardError):
        store.save_match(
            MatchCreate(
                home_team_id=played["home"].id,
                away_team_id=played["away"].id,
                half_minutes=25,
                sub_interval_minutes=5,
                home_player_ids=[played["javi"].id],
                away_player_ids=[played["javi"].id],
            ),
            None,
        )


def test_a_team_with_no_matches_reports_zeroes(store, played):
    by_name = {t.name: t for t in store.stats().teams}
    idle = by_name["Atletico Jueves"]
    assert (idle.played, idle.won, idle.goals_for, idle.goals_against) == (0, 0, 0, 0)
