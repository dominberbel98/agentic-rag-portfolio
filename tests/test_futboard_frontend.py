"""Guards on the two FUTBOARD modules that cannot fail loudly on their own.

Written in pytest and driven through `node`, for the same reason the rest of the
frontend checks are: the repository has no JS test runner, and standing one up to
cover two modules would cost more than it returns. Node is already a build
dependency, so importing the real ESM module and asserting on it is honest —
these are the shipped functions, not a transcription of them.

Two things are covered.

**The dictionary**, because a key present in English and missing in Spanish
renders as the string `undefined` in the UI rather than failing the build. That
is invisible until someone switches language on a pitch.

**The clock**, because it is the one piece with no safe failure mode. It is
derived from timestamps precisely so a phone that sleeps mid-half comes back
correct, and the substitution cue arithmetic decides when a whistle blows.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; frontend checks need it"
)

I18N = "src/i18n/futboard.js"
CLOCK = "src/lib/matchClock.js"


def _node(repo_root, script: str):
    """Run an ESM snippet inside frontend/ and parse what it prints as JSON."""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=repo_root / "frontend",
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


# ── dictionary ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dictionaries(repo_root):
    return _node(
        repo_root,
        f"""
        import {{ dictionary }} from "./{I18N}";
        const walk = (node, prefix = "") =>
          Object.entries(node).flatMap(([key, value]) => {{
            const path = prefix ? `${{prefix}}.${{key}}` : key;
            return value && typeof value === "object" && !Array.isArray(value)
              ? walk(value, path)
              : [[path, typeof value]];
          }});
        console.log(JSON.stringify({{
          en: Object.fromEntries(walk(dictionary.en)),
          es: Object.fromEntries(walk(dictionary.es)),
        }}));
        """,
    )


def test_both_languages_define_exactly_the_same_keys(dictionaries):
    english, spanish = set(dictionaries["en"]), set(dictionaries["es"])
    assert not english - spanish, f"missing from Spanish: {sorted(english - spanish)}"
    assert not spanish - english, f"missing from English: {sorted(spanish - english)}"


def test_a_key_is_a_function_in_both_languages_or_neither(dictionaries):
    """A string where the UI calls `f.live.of(25)` throws at render time."""
    mismatched = [
        key
        for key, kind in dictionaries["en"].items()
        if kind != dictionaries["es"][key]
    ]
    assert not mismatched, f"type differs between languages: {mismatched}"


def test_no_value_is_empty(dictionaries):
    assert all(dictionaries["en"].values()), "an English entry has no value"
    assert all(dictionaries["es"].values()), "a Spanish entry has no value"


# ── clock ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def clock(repo_root):
    """Exercise the clock over a scripted timeline with a fixed `now`."""
    return _node(
        repo_root,
        f"""
        import * as c from "./{CLOCK}";
        const MIN = 60000;
        const t0 = 1_700_000_000_000;

        // A 25-minute half with a cue every 5 minutes.
        let clock = c.createClock(25, 5);
        const out = {{}};

        out.startsAtZero = c.elapsedMs(clock, t0);

        clock = c.start(clock, t0);
        out.afterSevenMinutes = c.elapsedMs(clock, t0 + 7 * MIN);
        out.cuesAfterSeven = c.dueSubCues(clock, t0 + 7 * MIN);
        out.msToNextCueAtSeven = c.msToNextSubCue(clock, t0 + 7 * MIN);

        // Paused at minute 10, still paused three minutes later.
        const paused = c.pause(clock, t0 + 10 * MIN);
        out.frozenWhilePaused = c.elapsedMs(paused, t0 + 13 * MIN);

        // Resumed at minute 13: the three paused minutes must not be played.
        const resumed = c.start(paused, t0 + 13 * MIN);
        out.afterResume = c.elapsedMs(resumed, t0 + 14 * MIN);

        // A half cannot overrun its own length.
        out.clampedAtTheEnd = c.elapsedMs(clock, t0 + 40 * MIN);

        // The last cue never lands on the whistle: 25/5 gives 5, 10, 15, 20.
        out.cuesInAWholeHalf = c.dueSubCues(clock, t0 + 25 * MIN);
        out.noCueLeftAtTheEnd = c.msToNextSubCue(clock, t0 + 25 * MIN);

        // Second half restarts the clock but keeps the settings.
        const second = c.startSecondHalf(clock, t0 + 30 * MIN);
        out.secondHalfStartsAtZero = c.elapsedMs(second, t0 + 30 * MIN);
        out.secondHalfNumber = second.half;
        out.minuteStampContinues = c.elapsedMinutes(second, t0 + 30 * MIN + 3 * MIN);

        // Ending each half moves to the right terminal state.
        out.afterFirstHalfEnds = c.endHalf(clock).status;
        out.afterSecondHalfEnds = c.endHalf(second).status;

        out.formatted = c.formatClock(7 * MIN + 4000);
        console.log(JSON.stringify(out));
        """,
    )


def test_the_clock_starts_stopped(clock):
    assert clock["startsAtZero"] == 0


def test_elapsed_time_tracks_the_wall_clock(clock):
    assert clock["afterSevenMinutes"] == 7 * 60_000


def test_a_paused_clock_does_not_advance(clock):
    assert clock["frozenWhilePaused"] == 10 * 60_000


def test_paused_time_is_not_played(clock):
    """Paused at 10, resumed at 13, read at 14 — eleven minutes played, not fourteen."""
    assert clock["afterResume"] == 11 * 60_000


def test_a_half_cannot_overrun_its_length(clock):
    assert clock["clampedAtTheEnd"] == 25 * 60_000


def test_substitution_cues_land_on_the_interval(clock):
    assert clock["cuesAfterSeven"] == 1
    assert clock["msToNextCueAtSeven"] == 3 * 60_000


def test_no_substitution_cue_coincides_with_the_final_whistle(clock):
    """A 25-minute half at 5-minute intervals cues at 5, 10, 15 and 20 — not 25."""
    assert clock["cuesInAWholeHalf"] == 4
    assert clock["noCueLeftAtTheEnd"] is None


def test_the_second_half_restarts_the_clock(clock):
    assert clock["secondHalfStartsAtZero"] == 0
    assert clock["secondHalfNumber"] == 2


def test_goal_minutes_continue_across_the_interval(clock):
    """Three minutes into the second half of 25-minute halves is minute 28."""
    assert clock["minuteStampContinues"] == 28


def test_ending_a_half_reaches_the_right_state(clock):
    assert clock["afterFirstHalfEnds"] == "half_over"
    assert clock["afterSecondHalfEnds"] == "match_over"


def test_the_display_is_zero_padded(clock):
    assert clock["formatted"] == "07:04"
