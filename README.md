# Portfolio — Agentic RAG, live analytics and in-browser models

An interactive professional portfolio you can interrogate, in English and Spanish. A retrieval-augmented
assistant answers questions about a real career from a structured profile, a
scheduled PySpark job publishes live La Liga analytics, three machine learning
models run entirely in the browser, and FUTBOARD keeps the score for a Sunday
football game.

**Live:** [domingoberbel.com](https://domingoberbel.com)

## What is in it

Every section is available in both languages; the switch is in the header and the
choice is remembered.

| Section | What it does |
|---------|--------------|
| **chat_cv** | Agentic RAG assistant over a structured profile, streaming over SSE |
| **visualisations** | La Liga standings, form and rates, refreshed every 30 minutes |
| **laliga_prediction** | End-of-season projection: pace model, Poisson Monte Carlo, XGBoost zones |
| **credit_scoring** | Logistic regression scorecard, 300–850, scored client-side |
| **recommender** | Content-based recommender with TF-IDF and MMR re-ranking, client-side |
| **certifications** | Verified certifications, generated from the profile |
| **futboard** | Match clock, squads and statistics for amateur football, on Neon Postgres |

## Architecture

```
                       ┌───────────────────────────────┐
Browser ──────────────►│ Azure Static Web Apps          │
                       │ React 18 + Vite + Tailwind     │
                       │ static JSON for models/La Liga │
                       └───────────────┬────────────────┘
                                       │  /api
                       ┌───────────────▼────────────────┐
                       │ Azure Container Apps           │
                       │ FastAPI · 0.25 vCPU / 0.5 GiB  │
                       └───┬───────────┬────────────┬───┘
                           │           │            │
                     OpenAI API   Google Gemini   Neon Postgres
                     (generation)  (embeddings)    (FUTBOARD)
```

The retrieval index ships inside the backend image; there is no vector database
and no Azure AI Search. The three models are trained offline and exported to
JSON, so moving a slider recomputes a score in the browser with no backend call.

## Single source of truth

`data/profile.yml` is the only hand-edited description of the profile. Everything
downstream is generated and must not be edited:

```
data/profile.yml
      ├──→ data/kb/*.md                      one document per entity, for retrieval
      ├──→ data/kb/vocabulary.json           allowed proper nouns, for groundedness
      └──→ frontend/public/data/profile.json certifications and skills, for the UI
```

```bash
python scripts/build_kb.py --check   # validate, write nothing
python scripts/build_kb.py           # regenerate
python scripts/index_documents.py    # re-embed (needs GOOGLE_API_KEY)
```

The schema in `backend/app/profile_schema.py` enforces that ids are globally
unique, that exactly one role is current, and that every `stack:` entry is a
declared skill — a typo is a hard error rather than a new skill.

## How the assistant works

The model is given search tools and decides what to look up, instead of keyword
rules deciding for it. Facts are never in the prompt: it carries role, tone,
scope and safety only, so the corpus is the source of truth rather than
decoration.

- **Retrieval** — hybrid dense (`gemini-embedding-2`, asymmetric query/document
  task types) plus BM25, each min-max normalised and fused with the lexical half
  weighted at 0.25. Score fusion beat Reciprocal Rank Fusion on a golden set of
  18 real questions from the site's own logs (recall 18/18 and MRR 0.696, against
  13/18 and 0.562), because discarding score magnitude let a weak keyword match
  displace a confident semantic one.
- **Agent loop** — three tools (`search_profile`, `get_entity`, `list_entities`),
  bounded by iteration, tool-call and document caps.
- **Groundedness** — every entity named in an answer is checked against the
  profile vocabulary and the retrieved text before it is returned. An answer that
  invents a technology is regenerated once without it.
- **Reranking** is done by the model, not a cross-encoder: the container has
  0.25 vCPU and 0.5 GiB, where local model weights alongside FastAPI risk OOM.

## FUTBOARD

A scoreboard for amateur football, added because a portfolio that only contains
demos is a portfolio of demos.

- Teams are created once and then chosen; players live in one registry and can
  turn out for several teams.
- The match clock is derived from timestamps rather than accumulated ticks, so a
  phone that locks its screen mid-half comes back with the correct time.
- Three synthesised Web Audio cues: substitutions on an interval, end of half,
  end of match. No audio files, so nothing to download on a pitch with bad signal.
- Every goal is a row with a nullable scorer, so the team's score is right even
  when nobody noted who scored.
- The match lives in `localStorage` while it is played and is saved in one
  request at the end, so it survives a reload and needs no connection until then.
- Writes are open, with per-IP rate limiting, field bounds and global row caps.
- English and Spanish, switchable in the section.

Storage is Neon Postgres on the free plan, in an **AWS** region. Neon suspends
the compute after five minutes idle, which is correct and deliberately not
worked around: the free plan gives 100 CU-hours a month and the smallest compute
is 0.25 CU, so a database kept permanently awake would cost 182 CU-hours and run
out mid-month. The cost is a ~0.4 s wake on the first request, which the UI names
rather than hides.

```bash
python scripts/futboard_migrate.py --check   # report what is missing
python scripts/futboard_migrate.py           # create the schema
```

## Local development

```bash
cp backend/.env.example backend/.env        # fill in your values
cp infra/aca/azure.env.example infra/aca/azure.env
docker compose up --build
```

Frontend on http://localhost:3000, backend on http://localhost:8000/health. For
frontend work alone, `cd frontend && npm install && npm run dev` serves on 5173,
so `CORS_ORIGINS` should list both ports during mixed local development.

## Tests

```bash
python -m pytest            # everything
python -m pytest -m ""      # same; there are no custom markers
```

Tests that need a credential skip with a stated reason rather than failing:
retrieval quality needs `GOOGLE_API_KEY`, FUTBOARD storage needs
`FUTBOARD_DATABASE_URL`. The FUTBOARD storage tests never touch real data — they
create a throwaway Postgres schema and drop it afterwards.

The suite covers the profile schema and its cross-field rules, corpus generation,
retrieval and fusion, the agent loop, the groundedness check, La Liga transforms
across season boundaries, FUTBOARD validation and aggregation, and a set of
frontend invariants that need no JS runner: zone definitions agreeing across the
Python/JavaScript boundary, dictionary keys that are referenced existing, English
and Spanish FUTBOARD dictionaries matching key for key, the match clock, no
untranslated Spanish left in a component, and every text colour clearing WCAG AA
against the CRT surface.

## Deployment

Backend to Azure Container Apps, frontend to Azure Static Web Apps:

```bash
git push origin main          # required, see below
az login
source infra/aca/azure.env
./scripts/deploy_azure.sh
```

**Push before deploying.** The La Liga workflow rebuilds the frontend from
`origin/main` every 30 minutes and redeploys it, so a local deploy whose commits
are not pushed is reverted within half an hour — silently, because both
deployments succeed. The script refuses to run with unpushed commits for that
reason.

Every credential is stored as a Container Apps secret and referenced with
`secretref:`; the script fails the deploy if any of them ends up as a plaintext
environment variable. See [DEPLOYMENT.md](DEPLOYMENT.md) for the full runbook.

Two scheduled workflows: La Liga data every 30 minutes (which also rebuilds and
redeploys the frontend), and a weekly FUTBOARD health check.

## Security

- CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy and
  Permissions-Policy on both tiers
- Per-IP rate limiting on chat and, separately and more tightly, on FUTBOARD writes
- Daily token budget capping LLM spend
- Admin endpoints behind a timing-safe key comparison
- Wildcard CORS refused at startup in production
- No secrets in version control

## Tech stack

| Layer | Technology |
|-------|-----------|
| LLM | OpenAI API |
| Embeddings | Google `gemini-embedding-2` |
| Retrieval | Local cached embeddings + BM25, score fusion |
| Backend | FastAPI, Pydantic, Uvicorn, psycopg 3 |
| Database | Neon Postgres (FUTBOARD), SQLite (analytics) |
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Data | PySpark, XGBoost, scikit-learn, pandas, NumPy |
| Infra | Azure Container Apps, Azure Static Web Apps, GHCR, Docker |
| CI/CD | GitHub Actions |

## License

MIT
