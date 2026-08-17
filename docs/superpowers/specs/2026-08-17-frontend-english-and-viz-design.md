# Block C — Frontend in English, and La Liga visualisations

**Date:** 2026-08-17
**Depends on:** Block A (certifications and skills come from `profile.json`)

## Constraint

The CRT / phosphor-green aesthetic is the thing the owner likes most about the
site and must not change. Everything here is strings, columns and data plumbing —
no visual redesign, no palette change, no layout rework beyond the new panels
described below.

## Part 1 — English

The frontend is ~2,500 lines across six components, currently a mix of Spanish
and English. `Chat.jsx` is already mostly English; the model components and the
La Liga dashboard are largely Spanish.

Approach: a single `src/i18n/en.js` dictionary of user-facing strings, no i18n
library. One target language does not justify the dependency, and a flat
dictionary keeps the strings out of the JSX where the current mix makes them easy
to miss.

Scope, by file:

| File | Work |
|------|------|
| `index.html` | `lang="es"` → `lang="en"`, English meta description, keep the canonical URL |
| `App.jsx` | Nav labels (currently lowercase Spanish slugs: `visualizaciones`, `modelos`, `prediccion_la_liga`, `certificaciones`), the mascot bubble copy |
| `Visualizaciones.jsx` | Panel titles, table headers (`Equipo`/`PJ`/`V`/`E`/`D`/`GF`/`GC`/`DG`), zone legend, loading and error states, `toLocaleString("es-ES")` → `en-GB` |
| `ModelosPredictivos.jsx` | `PROBABILIDAD_CAMPEÓN`, `PUNTOS_PROYECTADOS`, `METODOLOGÍA`, feature labels, tooltips |
| `ModelosScoring.jsx` | Feature labels and all slider labels (`Ingresos anuales`, `Años de empleo`, `Antigüedad crédito`, …), `MÉTRICAS_MODELO`, `DISTRIBUCIÓN_SCORES` |
| `ModelosRecomendacion.jsx` | `PERSONAS_DEMO`, `RANKING_SIMILARIDAD`, `CATÁLOGO`, `RECOMENDACIONES` |
| `Chat.jsx` | Contact form (`Tu nombre`, `Tu email`, `Enviar contacto`, `— Contacto directo`, `Ver perfil de LinkedIn`), the backend error string |
| `Certificaciones.jsx` | `CERTIFICACIONES_DS`, and stop hardcoding the six certifications — read `profile.json` from Block A |

The nav ids stay as they are: they are internal keys used by `activeSection` and
`MODEL_IDS`, and renaming them is churn with no user-visible effect. Only the
displayed labels change.

Deliberately unchanged: `frontend/public/sitemap.xml` and the canonical URL, so
existing search indexing is not disturbed. The `robots.txt` needs no change.

## Part 2 — La Liga visualisations

### Conference zone

The requested gap. Zones today are `champions` (1-4), `europa` (5-6),
`relegation` (18-20) and `mid`. There is no UEFA Conference League zone, so
7th place is painted as mid-table and the legend shows only three tiers.

Added as a fourth zone in `pipeline_laliga.py` (both the Spark and plain-Python
paths, which must stay in agreement) and in the `ZONE_COLORS` map and legend in
`Visualizaciones.jsx`. It needs a colour that reads as distinct from the existing
green / blue / red inside the phosphor palette.

Zone boundaries become a single named constant rather than magic numbers repeated
across `pipeline_laliga.py`, `predict_laliga.py` and two frontend components.
They currently disagree, which is how the missing zone went unnoticed.

### Form column

Requested, and not simply available: the upstream `form` field is `null` for
every team on every request — verified against the live API. The current pipeline
papers over this by coercing `None` to `""`, so the column could never populate.

The `scores` endpoint does return finished fixtures with `homeTeam`, `awayTeam`,
`score` and `matchday`, so form must be **derived** from the last five finished
matches per team. This is real work, not a field to surface.

### Fixtures and results

`scores` is currently fetched, dumped raw into the JSON, and never rendered.
Meanwhile `matches` is always empty because `_filter_laliga_matches` reads
`matches_raw.get("matches", [])` while the API returns `{"success":…, "data":[…]}`
— a key mismatch — and because that feed is *global* football with no league
field, so the La Liga filter could never match anyway. Its fallback then returns
`items[:10]` of an empty list.

Therefore: **drop `matches` entirely** and render from `scores`, which is
correctly structured and already being fetched. Two new panels:

- **Latest results** — finished fixtures for the current matchday, with scores.
- **Upcoming fixtures** — scheduled matches with kickoff times.

### Correctness fixes

- `key={t.position}` → `key={t.teamId}`. The shipped hotfix made `position`
  unique so this no longer breaks React, but `teamId` is the stable identity.
- Header shows real season state — matchday and whether the season is in
  progress, pre-season or finished — instead of printing whatever `matchday` the
  feed returns.
- `Top5Radar` sorts by position and slices five; with the hotfix's unique ranks
  this is now deterministic, but the radar normalises across only the top five
  while its caption claims otherwise. Caption and computation reconciled.

## Error handling

- Every panel already handles a fetch failure; the messages move into the
  dictionary and stop being Spanish.
- **Empty-state handling is new and necessary.** At matchday 0 there are no
  finished fixtures and no form. Panels must render an explicit "season has not
  started" state rather than empty charts — this is exactly the condition that
  made the site show stale data for days.
- A missing `profile.json` must not blank the certifications page; the component
  renders an error state.
- Derived form tolerates teams with fewer than five finished matches.

## Testing

Frontend tests are absent today and a full harness is out of scope for this
block. What is worth adding:

- Pure-function tests for the new derived-form logic and the zone classifier,
  extracted out of the components so they are testable without a DOM.
- A dictionary completeness check: no user-facing string literal remains in the
  JSX, and every key referenced by a component exists in `en.js`.
- Fixture-based rendering checks for the three season states — not started,
  in progress, finished.

## Verification

Run the site locally against three fixtures (matchday 0, matchday 1 with partial
results, mid-season) and confirm: no Spanish text remains anywhere in the UI, all
four zones appear in the legend, the form column populates from derived data, and
the results and fixtures panels render. Compare screenshots against the current
site to confirm the aesthetic is unchanged.
