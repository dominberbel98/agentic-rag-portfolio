"""Tests for the La Liga transforms, built around the calendar edges that broke
production rather than around the happy path.

Both faults that took the scheduled workflow down for two days were arithmetic on
a season boundary: every team at zero games played, and an upstream rank made
entirely of ties. Each is a fixture here.
"""

from __future__ import annotations

import pytest

from scripts.laliga_transform import (
    FORM_LENGTH,
    SHRINKAGE_K,
    ZONES,
    add_rates,
    assign_ranks,
    build_team_aliases,
    derive_form,
    extract_fixtures,
    extract_results,
    league_priors,
    match_team,
    merge_results,
    season_state,
    shrink,
    zone_for_position,
)


def _team(tid, name, short, played=0, won=0, draw=0, lost=0, gf=0, ga=0, position=1):
    return {
        "teamId": tid,
        "teamName": name,
        "teamShortName": short,
        "playedGames": played,
        "won": won,
        "draw": draw,
        "lost": lost,
        "goalsFor": gf,
        "goalsAgainst": ga,
        "goalDifference": gf - ga,
        "points": won * 3 + draw,
        "position": position,
    }


@pytest.fixture
def preseason_table():
    """Matchday 0: nobody has kicked off, and upstream ties every position."""
    return [
        _team(1, "FC Barcelona", "Barça", position=1),
        _team(2, "Real Madrid CF", "Real Madrid", position=1),
        _team(3, "Club Atlético de Madrid", "Atleti", position=1),
    ]


@pytest.fixture
def midseason_table():
    return [
        _team(1, "FC Barcelona", "Barça", played=10, won=8, draw=1, lost=1, gf=25, ga=8, position=1),
        _team(2, "Real Madrid CF", "Real Madrid", played=10, won=7, draw=2, lost=1, gf=22, ga=10, position=2),
        _team(3, "Club Atlético de Madrid", "Atleti", played=10, won=2, draw=2, lost=6, gf=9, ga=20, position=3),
    ]


# --- zones -------------------------------------------------------------------


@pytest.mark.parametrize(
    "position,expected",
    [
        (1, "champions"), (4, "champions"),
        (5, "europa"), (6, "europa"),
        (7, "conference"),  # the zone that was missing entirely
        (8, "mid"), (17, "mid"),
        (18, "relegation"), (20, "relegation"),
    ],
)
def test_zone_for_position(position, expected):
    assert zone_for_position(position) == expected


def test_every_zone_is_reachable_over_a_full_table():
    produced = {zone_for_position(p) for p in range(1, 21)}
    assert produced == set(ZONES)


def test_conference_zone_exists():
    """It did not before: seventh place was painted as mid-table."""
    assert "conference" in ZONES
    assert zone_for_position(7) == "conference"


# --- ranks -------------------------------------------------------------------


def test_assign_ranks_breaks_upstream_ties(preseason_table):
    ranked = assign_ranks(preseason_table)
    assert [r["position"] for r in ranked] == [1, 2, 3]


def test_assign_ranks_is_deterministic_with_everything_level(preseason_table):
    first = [r["teamShortName"] for r in assign_ranks(list(preseason_table))]
    second = [r["teamShortName"] for r in assign_ranks(list(reversed(preseason_table)))]
    assert first == second


def test_assign_ranks_keeps_the_upstream_value(preseason_table):
    ranked = assign_ranks(preseason_table)
    assert all("apiPosition" in row for row in ranked)


def test_assign_ranks_orders_by_points_then_goal_difference(midseason_table):
    ranked = assign_ranks(midseason_table)
    assert [r["teamShortName"] for r in ranked] == ["Barça", "Real Madrid", "Atleti"]


# --- rates -------------------------------------------------------------------


def test_add_rates_survives_zero_games_played(preseason_table):
    """The DIVIDE_BY_ZERO that broke every scheduled run for two days."""
    rated = add_rates(preseason_table)
    for row in rated:
        assert row["winRate"] == row["drawRate"] == row["lossRate"] == 0.0


def test_add_rates_computes_percentages(midseason_table):
    rated = add_rates(midseason_table)
    assert rated[0]["winRate"] == 80.0
    assert rated[0]["drawRate"] == 10.0
    assert rated[0]["lossRate"] == 10.0


def test_rates_always_fall_within_range(midseason_table, preseason_table):
    for row in add_rates(midseason_table) + add_rates(preseason_table):
        for key in ("winRate", "drawRate", "lossRate"):
            assert 0.0 <= row[key] <= 100.0


# --- team matching -----------------------------------------------------------


@pytest.fixture
def aliases(midseason_table):
    return build_team_aliases(midseason_table)


def test_match_team_finds_the_full_name(aliases):
    assert match_team("FC Barcelona", aliases) == "Barça"


def test_match_team_finds_the_short_name(aliases):
    assert match_team("Real Madrid", aliases) == "Real Madrid"


def test_match_team_ignores_accents(aliases):
    assert match_team("Atletico Madrid", aliases) == "Atleti"


def test_match_team_rejects_a_foreign_club_with_a_similar_name(aliases):
    """Substring matching made Atlético Bucaramanga, an Argentine club, resolve to
    La Liga's Atleti, so a Colombian fixture was published as a La Liga one."""
    assert match_team("Atlético Bucaramanga", aliases) is None


def test_match_team_returns_none_for_an_unknown_club(aliases):
    assert match_team("Seattle Sounders", aliases) is None


# --- fixtures ----------------------------------------------------------------


def test_extract_fixtures_requires_both_sides_to_be_la_liga(aliases):
    feed = {
        "data": [
            {"id": 1, "title": "Real Madrid vs. FC Barcelona", "date": 100},
            {"id": 2, "title": "Real Madrid vs. Seattle Sounders", "date": 200},
            {"id": 3, "title": "Atlético Bucaramanga vs Deportivo Pasto", "date": 300},
        ]
    }
    fixtures = extract_fixtures(feed, aliases)
    assert [f["id"] for f in fixtures] == [1]


def test_extract_fixtures_handles_an_empty_feed(aliases):
    assert extract_fixtures({"data": []}, aliases) == []


def test_extract_fixtures_tolerates_the_wrong_shape(aliases):
    """The old code read matches_raw['matches'] against a {'data': [...]} response,
    so the fixtures list was always empty."""
    assert extract_fixtures({"matches": []}, aliases) == []
    assert extract_fixtures([], aliases) == []


def test_extract_fixtures_orders_by_kickoff(aliases):
    feed = {
        "data": [
            {"id": 2, "title": "Real Madrid vs. Atlético Madrid", "date": 500},
            {"id": 1, "title": "FC Barcelona vs. Real Madrid", "date": 100},
        ]
    }
    assert [f["id"] for f in extract_fixtures(feed, aliases)] == [1, 2]


# --- results -----------------------------------------------------------------


def _score(mid, home_id, away_id, hg, ag, when, status="FINISHED"):
    return {
        "id": mid,
        "utcDate": when,
        "status": status,
        "matchday": 1,
        "homeTeam": {"id": home_id, "shortName": f"T{home_id}", "crest": ""},
        "awayTeam": {"id": away_id, "shortName": f"T{away_id}", "crest": ""},
        "score": {"winner": None, "fullTime": {"home": hg, "away": ag}},
    }


def test_extract_results_reads_finished_and_live():
    raw = {
        "data": {
            "finished": [_score(1, 1, 2, 3, 0, "2026-08-15T17:30:00Z")],
            "live": [_score(2, 2, 3, 1, 1, "2026-08-17T19:00:00Z", status="IN_PLAY")],
        }
    }
    results = extract_results(raw)
    assert len(results) == 2
    assert results[0]["id"] == 2  # newest first
    assert results[0]["live"] is True


def test_extract_results_handles_an_empty_feed():
    assert extract_results({"data": {"live": [], "finished": []}}) == []


def test_merge_results_accumulates_history_across_runs():
    """One run cannot see enough history for a five-match form string, so the
    committed JSON is the store."""
    previous = [{"id": 1, "utcDate": "2026-08-15T17:30:00Z", "status": "FINISHED"}]
    current = [{"id": 2, "utcDate": "2026-08-22T17:30:00Z", "status": "FINISHED"}]
    merged = merge_results(previous, current)
    assert [m["id"] for m in merged] == [2, 1]


def test_merge_results_lets_a_finished_match_supersede_a_live_one():
    previous = [{"id": 1, "utcDate": "x", "status": "IN_PLAY", "homeGoals": 0}]
    current = [{"id": 1, "utcDate": "x", "status": "FINISHED", "homeGoals": 2}]
    merged = merge_results(previous, current)
    assert len(merged) == 1
    assert merged[0]["status"] == "FINISHED"


def test_merge_results_drops_entries_without_an_id():
    assert merge_results([{"utcDate": "x"}], [{"utcDate": "y"}]) == []


# --- form --------------------------------------------------------------------


def test_derive_form_reads_newest_first(midseason_table):
    results = [
        {"id": 1, "status": "FINISHED", "utcDate": "2026-09-01", "homeId": 1, "awayId": 2, "homeGoals": 2, "awayGoals": 0},
        {"id": 2, "status": "FINISHED", "utcDate": "2026-09-08", "homeId": 3, "awayId": 1, "homeGoals": 1, "awayGoals": 1},
    ]
    derive_form(midseason_table, results)
    barca = next(r for r in midseason_table if r["teamId"] == 1)
    assert barca["form"] == "DW"


def test_derive_form_is_empty_with_no_history(midseason_table):
    """Upstream sends form: null on every row, so an empty string is the honest
    value until enough matches have accumulated."""
    derive_form(midseason_table, [])
    assert all(row["form"] == "" for row in midseason_table)


def test_derive_form_caps_at_five(midseason_table):
    results = [
        {"id": i, "status": "FINISHED", "utcDate": f"2026-09-{i:02d}",
         "homeId": 1, "awayId": 2, "homeGoals": 1, "awayGoals": 0}
        for i in range(1, 9)
    ]
    derive_form(midseason_table, results)
    assert len(next(r for r in midseason_table if r["teamId"] == 1)["form"]) == FORM_LENGTH


def test_derive_form_ignores_unfinished_matches(midseason_table):
    results = [
        {"id": 1, "status": "IN_PLAY", "utcDate": "2026-09-01", "homeId": 1, "awayId": 2, "homeGoals": 1, "awayGoals": 0},
    ]
    derive_form(midseason_table, results)
    assert all(row["form"] == "" for row in midseason_table)


def test_derive_form_records_draws_for_both_sides(midseason_table):
    results = [
        {"id": 1, "status": "FINISHED", "utcDate": "2026-09-01", "homeId": 1, "awayId": 2, "homeGoals": 1, "awayGoals": 1},
    ]
    derive_form(midseason_table, results)
    assert next(r for r in midseason_table if r["teamId"] == 1)["form"] == "D"
    assert next(r for r in midseason_table if r["teamId"] == 2)["form"] == "D"


# --- season state ------------------------------------------------------------


def test_season_state_detects_preseason(preseason_table):
    state = season_state(preseason_table, matchday=1)
    assert state["phase"] == "preseason"
    assert state["lowConfidence"] is True


def test_season_state_detects_in_progress(midseason_table):
    state = season_state(midseason_table, matchday=10)
    assert state["phase"] == "in_progress"
    assert state["lowConfidence"] is False


def test_season_state_detects_a_finished_season():
    table = [_team(1, "FC Barcelona", "Barça", played=38, won=30, draw=4, lost=4, gf=90, ga=30)]
    assert season_state(table, matchday=38)["phase"] == "finished"


def test_low_confidence_holds_through_the_opening_matchdays():
    """The condition under which the projection is not worth showing."""
    table = [_team(1, "FC Barcelona", "Barça", played=2, won=2, gf=6, ga=0)]
    assert season_state(table, matchday=2)["lowConfidence"] is True


# --- shrinkage ---------------------------------------------------------------


def test_league_priors_fall_back_before_kickoff(preseason_table):
    priors = league_priors(preseason_table)
    assert 1.0 < priors["gfPerGame"] < 2.0
    assert 1.0 < priors["ppg"] < 2.0
    assert priors["gfPerGame"] == priors["gaPerGame"], "goals scored and conceded must balance"


def test_league_priors_are_derived_once_matches_exist(midseason_table):
    priors = league_priors(midseason_table)
    # 30 games played across the table, 56 goals scored.
    assert priors["gfPerGame"] == pytest.approx(56 / 30)


def test_league_priors_balance_goals_over_a_closed_table():
    """Every goal scored is a goal conceded, so over a table whose members only
    played each other the two averages must agree.

    The midseason fixture cannot show this — its three teams also played opponents
    outside the fixture, so its totals do not balance. The invariant is a property
    of a complete table, and this uses one.
    """
    closed = [
        _team(1, "A", "A", played=2, won=1, lost=1, gf=3, ga=2),
        _team(2, "B", "B", played=2, won=1, lost=1, gf=2, ga=3),
    ]
    priors = league_priors(closed)
    assert priors["gfPerGame"] == pytest.approx(priors["gaPerGame"])


def test_shrink_returns_the_prior_with_no_data():
    assert shrink(observed=3.0, prior=1.35, played=0) == 1.35


def test_shrink_barely_moves_off_one_match():
    """One 3-0 win is not a 3-goals-per-game team. The projection that shipped
    turned exactly this into a 114-point season."""
    result = shrink(observed=3.0, prior=1.35, played=1)
    assert result < 1.7


def test_shrink_approaches_the_observation_as_matches_accumulate():
    early = shrink(observed=3.0, prior=1.35, played=1)
    later = shrink(observed=3.0, prior=1.35, played=20)
    assert early < later < 3.0
    assert later > 2.6


def test_shrink_is_exactly_halfway_at_k_matches():
    result = shrink(observed=3.0, prior=1.0, played=int(SHRINKAGE_K))
    assert result == pytest.approx(2.0)


def test_shrink_leaves_an_observation_equal_to_the_prior_untouched():
    assert shrink(observed=1.35, prior=1.35, played=7) == pytest.approx(1.35)


def test_shrink_is_monotonic_in_matches_played():
    values = [shrink(observed=2.5, prior=1.0, played=n) for n in range(0, 25)]
    assert values == sorted(values)
