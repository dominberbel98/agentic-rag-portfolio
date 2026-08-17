# Block D — La Liga pipeline correctness

**Date:** 2026-08-17
**Depends on:** nothing
**Status:** phase 1 shipped to branch `fix/laliga-pipeline-season-rollover`

## Problem

The scheduled workflow `update-laliga.yml` had failed on every run for two days.
Investigation found three independent faults, not one.

### 1. Divide-by-zero on season rollover (fixed)

The 2026-27 season opened on 2026-08-16. At the time of investigation 12 of 20
teams had `playedGames = 0`. `pipeline_laliga.py:109` divided by that column to
compute win/draw/loss rates, and Spark under ANSI mode raises `DIVIDE_BY_ZERO`
rather than returning null. The plain-Python fallback guarded this
(`played = t.get("playedGames", 1) or 1`); the Spark path did not.

The upstream API itself was never broken — it returns 200 with valid data.

### 2. Production data was wrong, not merely stale (fixed by 1)

Because the pipeline could not complete, `la_liga_data.json` was frozen at
2026-08-15 holding the **final 2025-26 table** (38 games played, Barcelona on 94
points) while labelled `season 2026 / matchday 1`. The site presented last
season's finished standings as the current league for several days.

### 3. Upstream `position` has ties (fixed)

The feed returns rank *with ties*: every team that had not yet kicked off came
back as `position: 6` — twelve of them. Consequences, all live in production:

- The zone classifier read that field, so twelve clubs were painted into the
  Europa League slot and the `mid` zone never appeared at all.
- `Visualizaciones.jsx` keys standings rows on `t.position`, producing twelve
  React rows sharing a key.
- `predict_laliga.py` derived its XGBoost training labels from the same field.

Both transform paths now compute a unique 1-20 rank from the league tiebreak
(points, goal difference, goals for, then name for determinism — head-to-head is
not available in this feed) and retain the upstream value as `apiPosition`.

## Phase 1 — shipped

Commit `182aeca` on `fix/laliga-pipeline-season-rollover`.

Verified locally against the live API with the exact CI dependency set (PySpark
4.2.0, Java 17, xgboost 3.4.1, scikit-learn 1.9.0): `pipeline_laliga.py` and
`predict_laliga.py` both exit 0, ranks are a unique 1-20, zones split 4/2/11/3
with `mid` present, all rates fall within [0, 100], and the Spark output is
identical to the plain-Python fallback's.

The data files were deliberately left untouched — the workflow regenerates and
commits them itself, and merging is the owner's call.

## Phase 2 — prediction cold start

Deferred by explicit decision: ship the crash fix, address this after.

At matchday 1 the pace model extrapolates one match across 38 and produces
nonsense. Measured output from the fixed pipeline:

| Team | pace points | MC mean | champion % |
|------|-------------|---------|------------|
| Espanyol | 114.0 | 106.2 | 46.6 |
| Alavés | 114.0 | 105.9 | 53.4 |
| Real Madrid / Barcelona | 0.0 | ~44 | 0.0 |
| Getafe / Levante | 0.0 | 5.1 | 0.0 |

Three compounding causes: `ppg` computed from a one-match sample; XGBoost trained
on 20 rows whose feature vectors are nearly all zeros; and the Monte Carlo
falling back to `max(gfPerGame, 0.3)`, which makes unplayed teams identical and
the simulated champion arbitrary.

Implemented — **shrinkage toward a prior**, with k=5. Measured on the same
matchday-one data: Alavés from 114.0 to 62.5 projected points, Real Madrid from
0.0 to 52.2, the spread from 0-114 down to 43.5-62.5, and the title probability
spread across the field instead of split between the two clubs that kicked off
first.

Original proposal follows.

**Shrinkage toward a prior**. Blend the current-season rate with a
prior, weighting the observed data by matches played:

```
rate = (played * observed + k * prior) / (played + k)
```

with the prior taken from the previous season's final table where available and
the league mean otherwise, and `k` set so the prior dominates for roughly the
first five matchdays. This is standard, cheap, and a considerably better portfolio
demonstration than a naive pace projection — it shows the author knows why a
one-match sample cannot be extrapolated.

Alongside it, the payload carries a confidence flag derived from total matches
played, so Block C can render an honest caveat instead of presenting an early
projection as settled.

## Phase 3 — data quality

Folded into Block C where it touches the frontend, listed here because it is
pipeline work:

- **Conference League zone.** Zone boundaries currently live as magic numbers in
  `pipeline_laliga.py`, `predict_laliga.py` and two frontend components, and they
  disagree. One named constant, four zones.
- **Derived form.** Upstream `form` is `null` on every row; it must be computed
  from the last five finished fixtures in the `scores` feed.
- **Drop `matches`, use `scores`.** `matches` never worked — a key mismatch
  (`matches_raw.get("matches")` against a `{"data": […]}` response) compounded by
  it being a global football feed with no league field. `scores` returns properly
  structured La Liga fixtures with matchday, status and score, and is already
  fetched and discarded.

## Error handling

The recurring failure mode is that a **calendar transition** breaks arithmetic
assumptions. The pipeline should be written so that season boundaries are
ordinary cases:

- No division by a count that can legitimately be zero, on either path.
- The two transform paths must produce identical output; the Spark path exists to
  demonstrate PySpark, so it must not be the one that is under-tested.
- A run that produces implausible output — fewer than 20 teams, non-unique ranks,
  a rate outside [0, 100] — should fail loudly rather than commit bad data. The
  current workflow would happily publish anything that does not raise.
- The workflow commits and deploys unconditionally. It should assert before
  committing, so a bad transform cannot reach the site.

## Testing

Fixtures captured from the live API, so these cases stop being discovered in
production:

| Fixture | Covers |
|---------|--------|
| matchday 0 | all teams at `playedGames = 0` — the divide-by-zero |
| matchday 1, partial | mixed 0 and 1, ties in `position` — the rank collapse |
| mid-season | unique positions, populated form |
| end of season | 38 games played, `remaining = 0` |

Assertions for each: exit 0, 20 teams, unique 1-20 ranks, rates within [0, 100],
all four zones representable, and Spark output equal to plain-Python output.

The `--dry-run` capability is worth adding: the pipeline should be runnable
without writing to `frontend/public/data/`, which is what made local verification
awkward this time.

## Note on tooling access

The GitHub token in use lacks the `workflow` scope, so workflow files cannot be
pushed from this environment. Changes to `.github/workflows/update-laliga.yml` —
including the pre-commit assertions described above — must be applied by the owner
through the GitHub web UI or with a token that carries the scope.
