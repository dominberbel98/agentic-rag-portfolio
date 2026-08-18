# FUTBOARD, model clarity and housekeeping — design

**Date:** 2026-08-18
**Status:** approved and implemented

## Context

Three unrelated pieces of work, taken together because they were requested
together. They share nothing but the repository, so they were designed and
delivered as independent blocks.

1. **Model clarity.** The credit scoring and recommender sections opened onto six
   panels at once, with the interactive part fifth. The explanation existed but
   was buried above the wall.
2. **FUTBOARD.** A new section: a scoreboard for the amateur football Domingo and
   his friends play. Teams, players, a match clock with two halves, statistics,
   and audible cues for substitutions and the end of each half.
3. **Housekeeping.** README and DEPLOYMENT.md had drifted from reality, the
   repository root had accumulated dead directories, and `ProfileAgent.stream()`
   was unreachable code.

## Decisions taken

| Question | Decision | Why |
|----------|----------|-----|
| Model layout | Three tabs: TRY IT / HOW IT WORKS / EVIDENCE | User's choice over progressive disclosure |
| Hiding the evaluation | Headline metric strip always visible | A reader who never opens EVIDENCE would otherwise never learn the model was validated |
| Score comprehension | Add a per-input driver breakdown | A number with no reason attached is what a scorecard exists to avoid |
| FUTBOARD navigation | Hub with three cards, back button on every inner screen | User's choice over a bottom tab bar |
| Live match layout | One column per team, scorers always visible | User's choice over a clock-first layout |
| Write access | Open, no access code | User's explicit choice; the concern about spam was raised and overruled |
| Match clock | One device, local | No live sync: polling would cost Neon compute and break on a bad signal |
| Statistics scope | Team goals, optional per-player goals, who played | User's scope; no assists, cards, substitutions or minutes |
| Halftime | No timed break | User's scope: the second half starts when someone taps |
| Language | English default, visible EN/ES switch, FUTBOARD only | Its audience is not a recruiter; the rest of the site stays English |
| Database | Neon Postgres, free plan, **AWS** region | See below |
| Iconography | Material Symbols, never emoji | Emoji read as machine-authored on a hiring surface |

## Neon: what was actually verified

The premise behind the request was that the database had to be kept from
switching off, with a query every few days. Checking Neon's current
documentation changed the design:

* The free plan **suspends the compute after five minutes idle and this cannot be
  disabled**. Suspension is a pause, not a shutdown: data persists and the next
  connection wakes it in about 0.4 s, measured through the pooler.
* **Keeping it warm would be actively harmful.** The plan allows 100 CU-hours per
  project per month; the smallest compute is 0.25 CU. Permanently awake is
  0.25 × 730 = 182 CU-hours, so a frequent keepalive exhausts the allowance
  mid-month and the database stops accepting connections entirely.
* **There is no general deletion-for-inactivity policy.** The widely repeated
  "free projects inactive for 90 days are subject to deletion from 5 October
  2026" belongs to Neon's [Azure regions deprecation](https://neon.com/docs/import/azure-regions-deprecation)
  and applies only to Azure-hosted projects. Choosing `aws-eu-central-1` avoids
  it entirely.
* Free plan quotas: 0.5 GB storage and 5 GB transfer per month. FUTBOARD's data
  is kilobytes.

**Resulting design:** let it sleep, use the `-pooler` host, name the wake in the
UI rather than hiding it behind a spinner, and keep one *weekly* health check as
insurance rather than as a warming mechanism.

Supabase was considered and rejected: its free tier pauses projects after seven
days of inactivity, which is the failure the user was actually worried about.

## Data model

Six tables. The load-bearing decision is that **every goal is a row and
`goals.player_id` is nullable**.

```
teams          id · name (unique, case-insensitive) · created_ip
players        id · name (unique, case-insensitive) · created_ip
team_players   team_id · player_id                     squad, many-to-many
matches        id · home_team_id · away_team_id · played_at
                  · half_minutes · sub_interval_minutes · created_ip
match_players  match_id · team_id · player_id          who played
goals          id · match_id · team_id · player_id? · half · minute
```

A team's score is the count of its goal rows. There is deliberately no
denormalised `goals_home` column: with one, a match recorded as 3–2 whose detail
lists four goals would be silently wrong in two different places. With the count
derived, the team total is right whether or not anyone recorded the scorer —
which is exactly the requested behaviour.

`match_players` is keyed `(match_id, player_id)`, which is what prevents a player
being registered on both sides of the same match.

`created_ip` is stored on every write and never returned to a client. Writes are
open, so the ability to undo a spam wave with one `DELETE` is the compensating
control.

## The match clock

Derived from wall-clock timestamps (`Date.now() - startedAt - pausedTotal`),
never accumulated from interval ticks. This is the single most important
correctness decision in the feature: mobile browsers throttle or suspend timers
when the screen locks or the tab is backgrounded, so a tick-counting clock
returns from a pocket minutes short. The render interval therefore only controls
how smoothly the display updates, not what it says.

Substitution cues fire at each whole multiple of the interval but never at the
end of a half — a 25-minute half at 5-minute intervals cues at 5, 10, 15 and 20,
not 25, because a cue one second before the whistle reads as a malfunction.

The whole match is mirrored into `localStorage` on every change and sent to the
API in a single request when it ends. A closed tab, a reload or a locked phone
does not lose a game in progress, and no connection is needed until the end.

## Audio

Three synthesised Web Audio cues rather than audio files: nothing to download on
a pitch with poor signal, no `media-src` addition to the CSP, and no assets to
keep in sync with the build. Gain is ramped rather than switched, because an
abruptly started square wave clicks and three clicks in a row sound like a fault.

Mobile browsers refuse audio without a user gesture, so the context is unlocked
inside the tap that starts the match. The phone may still be on silent, which no
audio code can defeat, so every cue is paired with a visual flash.

## Guardrails, given open writes

* Per-IP write ceiling, separate from and tighter than the chat limiter.
* Field bounds in Pydantic: name length, roster size, goals per match, half
  length, substitution interval.
* Global row caps for teams and players, checked in the store.
* Case-insensitive uniqueness on team and player names.
* Names collapsed to single spaces and rejected if they contain no alphanumeric
  character, so `---` and `Los  Pibes` cannot create junk or near-duplicates.

## Frontend structure

```
components/futboard/
  Futboard.jsx      hub, screen state, the only component that calls the API
  SquadsScreen.jsx  teams, players, squad editor
  MatchSetup.jsx    pick teams, who played, minutes per half
  LiveMatch.jsx     two columns, goal buttons, scorer sheet, cues
  StatsScreen.jsx   players, teams, history
  ui.jsx            shared primitives, 44px minimum tap targets
lib/matchClock.js   pure clock functions, no React
lib/matchSounds.js  Web Audio cues
lib/futboardApi.js  fetch wrappers and error shape
i18n/futboard.js    EN/ES dictionary and the language hook
```

The Spanish dictionary lives in `i18n/`, not in `components/`, because a test
fails on Spanish text inside a component. Keeping it outside means FUTBOARD gets
translations without weakening that guard for the rest of the site.

Screens are local state, not routes: the site has no router and adding one for
four screens would be a dependency bought for nothing.

## Testing

* `tests/test_futboard.py` — validation bounds with no database, plus a storage
  round trip that runs only when `FUTBOARD_DATABASE_URL` is set. The storage
  fixture creates a throwaway Postgres schema, points `search_path` at it, and
  drops it afterwards, so the suite can never damage real match data.
* `tests/test_futboard_frontend.py` — drives `node` against the real ESM modules
  to check that the two dictionaries match key for key and type for type, and to
  exercise the clock over a scripted timeline: pause, resume, clamping, cue
  arithmetic, second-half reset and goal-minute stamping.
* `tests/test_frontend_consistency.py` — its component scan was flat, so
  `components/futboard/*.jsx` escaped both the Spanish sweep and the WCAG
  contrast check. Made recursive; it immediately caught a placeholder at 3.00:1.

## What was deliberately not touched

The chat, retrieval, `profile.yml` and its generation, the La Liga pipeline and
its workflow, and the existing `en.js` dictionary. FUTBOARD is additive: one nav
entry, one component tree, one router. With no `FUTBOARD_DATABASE_URL` the
endpoints answer 503 and the rest of the site behaves exactly as before.
