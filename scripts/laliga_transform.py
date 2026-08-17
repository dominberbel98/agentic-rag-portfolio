"""Pure transforms for the La Liga pipeline.

Everything here is a function from data to data: no network, no Spark, no file
I/O. `pipeline_laliga.py` owns those. Splitting them out is what makes the season
boundaries testable — the faults that broke production for two days (all teams at
zero played games, and an upstream rank full of ties) were both arithmetic on a
calendar edge, and both are now fixtures in tests/test_laliga_transform.py.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

# ── Zones ───────────────────────────────────────────────────────────────────
#
# One definition, used by the pipeline, the predictive model and the frontend.
# These boundaries were previously magic numbers repeated in four places, which
# is how the Conference League zone stayed missing without anyone noticing: the
# table showed Champions, Europa and relegation only, so seventh place was
# painted as mid-table.

CHAMPIONS_LEAGUE_SLOTS = 4  # positions 1-4
EUROPA_LEAGUE_SLOTS = 6  # positions 5-6
CONFERENCE_LEAGUE_SLOTS = 7  # position 7
RELEGATION_FROM = 18  # positions 18-20

ZONES = ("champions", "europa", "conference", "mid", "relegation")


def zone_for_position(position: int) -> str:
    """Which European or relegation zone a finishing position falls in."""
    if position <= CHAMPIONS_LEAGUE_SLOTS:
        return "champions"
    if position <= EUROPA_LEAGUE_SLOTS:
        return "europa"
    if position <= CONFERENCE_LEAGUE_SLOTS:
        return "conference"
    if position >= RELEGATION_FROM:
        return "relegation"
    return "mid"


# ── Ranking ─────────────────────────────────────────────────────────────────


def league_sort_key(row: dict) -> tuple:
    """La Liga tiebreak order, minus head-to-head (absent from this feed).

    Name last so the ordering is deterministic: on the opening matchday every
    team is level on every other criterion.
    """
    return (
        -(row.get("points") or 0),
        -(row.get("goalDifference") or 0),
        -(row.get("goalsFor") or 0),
        row.get("teamName") or "",
    )


def assign_ranks(table: list[dict]) -> list[dict]:
    """Replace the upstream tied `position` with a unique 1-N rank.

    Upstream returns a rank *with ties* — on matchday one, twelve teams that had
    not kicked off all came back as position 6. That collapsed the zone split so
    `mid` never appeared and twelve clubs were painted into a European slot, and
    gave the standings table twelve rows sharing a React key. The original value
    is kept as `apiPosition`.
    """
    ordered = sorted(table, key=league_sort_key)
    for rank, row in enumerate(ordered, start=1):
        row["apiPosition"] = row.get("position")
        row["position"] = rank
    return ordered


def add_rates(table: list[dict]) -> list[dict]:
    """Win/draw/loss percentages, safe on zero games played."""
    for row in table:
        played = row.get("playedGames") or 0
        divisor = played if played > 0 else 1
        for name, source in (("winRate", "won"), ("drawRate", "draw"), ("lossRate", "lost")):
            row[name] = round((row.get(source) or 0) / divisor * 100, 1)
    return table


# ── Team name matching ──────────────────────────────────────────────────────

_CLUB_NOISE = re.compile(
    r"\b(cf|fc|cd|ud|rc|rcd|sd|sad|club|de|del|la|balompie|futbol|athletic)\b"
)


def fold(text: str) -> str:
    """Lowercase and strip accents, so 'Alavés' and 'Alaves' compare equal."""
    stripped = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in stripped if not unicodedata.combining(c))


def build_team_aliases(table: list[dict]) -> dict[str, list[str]]:
    """Map each team's short name to the strings that identify it in free text.

    The upcoming-fixtures feed is global football with no league field and no team
    ids — only a title like "Atlético Madrid vs. Málaga" — so identifying La Liga
    fixtures means matching against the names we already know from the standings.
    """
    aliases: dict[str, list[str]] = {}
    for row in table:
        short = row.get("teamShortName") or row.get("teamName") or ""
        if not short:
            continue
        candidates: set[str] = set()
        for value in (row.get("teamName"), row.get("teamShortName")):
            if not value:
                continue
            folded = fold(value)
            candidates.add(folded)
            core = " ".join(_CLUB_NOISE.sub(" ", folded).split())
            if len(core) >= 4:
                candidates.add(core)
        aliases[short] = sorted(candidates, key=len, reverse=True)
    return aliases


def match_team(text: str, aliases: dict[str, list[str]]) -> str | None:
    """Identify a team in a free-text fixture side, longest alias wins.

    Matching is on word boundaries, not substrings. Substring matching made
    "Atlético Bucaramanga" — an Argentine club — match La Liga's "Atleti", so a
    Colombian fixture was published as a La Liga one.
    """
    folded = fold(text)
    best: tuple[str, int] | None = None
    for short, candidates in aliases.items():
        for alias in candidates:
            if len(alias) < 4:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", folded):
                if best is None or len(alias) > best[1]:
                    best = (short, len(alias))
                break
    return best[0] if best else None


# ── Fixtures and results ────────────────────────────────────────────────────


def extract_results(scores_raw: Any) -> list[dict]:
    """Finished and in-play La Liga matches, newest first.

    Reads the `scores` endpoint, which returns properly structured La Liga
    fixtures. The previous pipeline fetched this, wrote it to the JSON untouched,
    and rendered none of it — while trying to build a fixtures list from a
    different endpoint that could never work.
    """
    data = scores_raw.get("data", scores_raw) if isinstance(scores_raw, dict) else {}
    out: list[dict] = []
    for bucket in ("live", "finished"):
        for match in data.get(bucket) or []:
            score = match.get("score") or {}
            full_time = score.get("fullTime") or {}
            home = match.get("homeTeam") or {}
            away = match.get("awayTeam") or {}
            out.append(
                {
                    "id": match.get("id"),
                    "utcDate": match.get("utcDate"),
                    "status": match.get("status"),
                    "matchday": match.get("matchday"),
                    "homeId": home.get("id"),
                    "homeName": home.get("shortName") or home.get("name"),
                    "homeCrest": home.get("crest"),
                    "awayId": away.get("id"),
                    "awayName": away.get("shortName") or away.get("name"),
                    "awayCrest": away.get("crest"),
                    "homeGoals": full_time.get("home"),
                    "awayGoals": full_time.get("away"),
                    "winner": score.get("winner"),
                    "live": bucket == "live",
                }
            )
    out.sort(key=lambda m: (m.get("utcDate") or ""), reverse=True)
    return out


def merge_results(previous: Iterable[dict], current: Iterable[dict]) -> list[dict]:
    """Accumulate match history across runs, newest first, de-duplicated by id.

    The scores endpoint only exposes a rolling window — four matches on the day
    this was written — so no single run can see enough history to compute form
    over the last five games. The pipeline runs every 30 minutes and commits its
    output, so the JSON itself is the store: each run folds in whatever is newly
    finished and keeps the rest.
    """
    by_id: dict[Any, dict] = {}
    for match in previous:
        if match.get("id") is not None:
            by_id[match["id"]] = match
    for match in current:
        if match.get("id") is not None:
            # A live match seen again may now be finished, so current wins.
            by_id[match["id"]] = match
    merged = list(by_id.values())
    merged.sort(key=lambda m: (m.get("utcDate") or ""), reverse=True)
    return merged


def extract_fixtures(matches_raw: Any, aliases: dict[str, list[str]]) -> list[dict]:
    """Upcoming La Liga fixtures from the global football feed.

    Both sides must resolve to a La Liga team. Requiring only one side would
    admit any fixture involving a club whose name resembles a Spanish one.
    """
    data = matches_raw.get("data", matches_raw) if isinstance(matches_raw, dict) else matches_raw
    if not isinstance(data, list):
        return []

    out: list[dict] = []
    for item in data:
        title = item.get("title") or ""
        sides = re.split(r"\s+vs\.?\s+", title, flags=re.IGNORECASE)
        if len(sides) != 2:
            continue
        home = match_team(sides[0], aliases)
        away = match_team(sides[1], aliases)
        if not home or not away or home == away:
            continue
        out.append(
            {
                "id": item.get("id"),
                "homeName": home,
                "awayName": away,
                "kickoff": item.get("date"),
                "title": title.strip(),
            }
        )
    out.sort(key=lambda m: (m.get("kickoff") or 0))
    return out


# ── Derived form ────────────────────────────────────────────────────────────

FORM_LENGTH = 5


def derive_form(table: list[dict], results: Iterable[dict]) -> list[dict]:
    """Attach each team's last five results as a 'W'/'D'/'L' string.

    Upstream sends `form: null` on every row on every request — verified against
    the live API — so the previous pipeline's coercion of None to "" meant the
    column could never populate. It has to be computed from match history.

    Newest result first, so 'WWD' reads left to right as most recent to oldest.
    """
    history: dict[Any, list[tuple[str, str]]] = {}
    for match in results:
        if match.get("status") != "FINISHED":
            continue
        home_goals = match.get("homeGoals")
        away_goals = match.get("awayGoals")
        if home_goals is None or away_goals is None:
            continue
        when = match.get("utcDate") or ""
        if home_goals > away_goals:
            home_outcome, away_outcome = "W", "L"
        elif home_goals < away_goals:
            home_outcome, away_outcome = "L", "W"
        else:
            home_outcome = away_outcome = "D"
        for team_id, outcome in ((match.get("homeId"), home_outcome), (match.get("awayId"), away_outcome)):
            if team_id is not None:
                history.setdefault(team_id, []).append((when, outcome))

    for row in table:
        entries = history.get(row.get("teamId"), [])
        entries.sort(key=lambda pair: pair[0], reverse=True)
        row["form"] = "".join(outcome for _, outcome in entries[:FORM_LENGTH])
    return table


# ── Season state ────────────────────────────────────────────────────────────

TOTAL_MATCHES = 38


def league_priors(table: list[dict]) -> dict[str, float]:
    """League-average per-game rates, used as the prior for shrinkage.

    Derived from the table itself where matches have been played, which keeps the
    prior honest without needing an external dataset. Before kickoff there is
    nothing to derive from, so these fall back to long-run La Liga averages:
    roughly 2.7 goals per match — about 1.35 per team per game — and about 1.37
    points per team per game, since a decided match distributes 3 points and a
    draw 2.
    """
    total_played = sum(row.get("playedGames") or 0 for row in table)
    if total_played == 0:
        return {
            "ppg": 1.37,
            "gfPerGame": 1.35,
            "gaPerGame": 1.35,
            "winRate": 0.37,
            "drawRate": 0.26,
            "lossRate": 0.37,
        }

    totals = {key: 0.0 for key in ("points", "goalsFor", "goalsAgainst", "won", "draw", "lost")}
    for row in table:
        for key in totals:
            totals[key] += row.get(key) or 0

    return {
        "ppg": totals["points"] / total_played,
        "gfPerGame": totals["goalsFor"] / total_played,
        "gaPerGame": totals["goalsAgainst"] / total_played,
        "winRate": totals["won"] / total_played,
        "drawRate": totals["draw"] / total_played,
        "lossRate": totals["lost"] / total_played,
    }


# Matches of observed data at which the prior and the observation carry equal
# weight. Five keeps the prior dominant through the opening month, which is the
# window where a naive projection produced 114-point seasons off one result.
SHRINKAGE_K = 5.0


def shrink(observed: float, prior: float, played: int, k: float = SHRINKAGE_K) -> float:
    """Blend an observed rate toward a prior, weighted by sample size.

        rate = (played · observed + k · prior) / (played + k)

    With no matches played the result is the prior; as matches accumulate the
    observation takes over. This is what stops one 3-0 win becoming a 114-point
    projected season — the failure the predictive panel shipped with, where
    Espanyol and Alavés were given a combined 100% title probability on matchday
    one while Real Madrid and Barcelona projected zero points.
    """
    if played <= 0:
        return prior
    return (played * observed + k * prior) / (played + k)


def season_state(table: list[dict], matchday: Any) -> dict:
    """A summary the frontend can render without recomputing anything.

    Empty states are the condition that let the site show a finished season's
    table as if it were current for several days, so the phase is explicit data
    rather than something the UI has to infer.
    """
    played = [row.get("playedGames") or 0 for row in table]
    total_played = sum(played)
    max_played = max(played, default=0)

    if total_played == 0:
        phase = "preseason"
    elif max_played >= TOTAL_MATCHES:
        phase = "finished"
    else:
        phase = "in_progress"

    return {
        "phase": phase,
        "matchday": matchday,
        "matchesPlayed": total_played // 2,
        "maxGamesPlayed": max_played,
        "totalMatchdays": TOTAL_MATCHES,
        # Below this, per-team rates and projections are not meaningful.
        "lowConfidence": max_played < 5,
    }
