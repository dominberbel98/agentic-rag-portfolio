# Project notes

Conventions and traps for this repository. Everything here was learned by being
bitten by it; none of it is derivable from reading the code.

## Deploying: push first, always

`.github/workflows/update-laliga.yml` runs **every 30 minutes**, checks out
`origin/main`, rebuilds the frontend and redeploys it to Azure Static Web Apps.

So the frontend has two publishers and the cron always wins. A deploy from
`scripts/deploy_azure.sh` whose commits are not pushed is silently reverted
within half an hour, with no error anywhere: both deployments "succeed", the site
just goes back in time. This happened on 2026-08-18.

`deploy_azure.sh` now refuses to run with a dirty tree or unpushed commits. Do
not weaken that check.

```bash
git push origin main
source infra/aca/azure.env
./scripts/deploy_azure.sh
```

Rebasing is normal here: the cron commits La Liga data constantly, so local work
is routinely dozens of commits behind. Those commits only touch
`frontend/public/data/la_liga_*.json`, so a rebase is conflict-free unless you
edited those.

## `infra/aca/azure.env` is not authoritative

It has drifted from live Azure before — a missing Static Web App name, a stale
chat model, the wrong GHCR account, an absent Google key. Verify against reality
rather than trusting the file:

```bash
az containerapp show -g rg-rag-domingo-prod -n rag-backend \
  --query "properties.template.containers[0].env"
az containerapp show -g rg-rag-domingo-prod -n rag-backend \
  --query "properties.configuration.registries"     # which GHCR account
az staticwebapp list -g rg-rag-domingo-prod
```

Secret values are recoverable, so a missing key never needs to be asked for:

```bash
az containerapp secret show -g rg-rag-domingo-prod -n rag-backend \
  --secret-name google-api-key --query value -o tsv
```

Deploying with a stale `OPENAI_MODEL` would silently downgrade the assistant.
Check it before every deploy.

## Generated files: never edit by hand

`data/profile.yml` is the only hand-written description of the profile.

```
data/profile.yml
   ├──→ data/kb/*.md                        corpus for retrieval
   ├──→ data/kb/vocabulary.json             allowed proper nouns
   ├──→ backend/vocabulary.json             the copy the container ships
   └──→ frontend/public/data/profile.json   certifications and skills
```

Regenerate with `python scripts/build_kb.py`; validate with `--check`. After
changing the profile you must also re-embed (`scripts/index_documents.py`,
needs `GOOGLE_API_KEY`) or retrieval will answer from a stale corpus.

The Docker build context is `backend/`, so `backend/embeddings_cache.json` and
`backend/vocabulary.json` must exist before building or the image ships without
an index and answers with nothing to ground itself on.

## Frontend

**Never import a dictionary in a component.** Use `useT()` from `src/i18n`.
Importing `i18n/en.js` pins that component to English regardless of the switch,
which looks like a partial translation rather than an error. `tests/test_i18n.py`
enforces this.

**Never read the dictionary at module scope.** `const TABS = [{label: tr.x}]` at
the top of a file freezes the labels at import time. Every such constant has been
moved inside its component; do not reintroduce the pattern.

**Text contrast is tested.** Phosphor green needs `/55` or higher against the
`#0e0e0e` surface to clear WCAG AA; red `#FF4136` fails at any reduction, so use
it at full strength. `tests/test_frontend_consistency.py` fails the build below
that.

**No emoji.** Use Material Symbols (`<span className="material-symbols-outlined">`)
or typographic characters. This is a hiring surface.

**Zone boundaries live in two languages** — `scripts/laliga_transform.py` and
`frontend/src/lib/laliga.js`. A test asserts they agree. They disagreed once and
the Conference League zone silently vanished from the table.

## Neon (FUTBOARD)

Free plan, **AWS region** (`aws-eu-central-1`), never Azure — Neon is deprecating
its Azure regions and free projects there are subject to deletion after 90 days
of inactivity. That rule does not apply on AWS.

The compute suspends after 5 minutes idle and that cannot be disabled. **Do not
add a keepalive to prevent it.** The plan allows 100 CU-hours/month and the
minimum compute is 0.25 CU, so staying awake costs 182 CU-hours and the database
stops accepting connections mid-month. Let it sleep; the wake costs ~0.4 s
through the pooler, and the UI says so rather than hiding it.

Always use the `-pooler` host in the connection string.

Tests never touch real match data: the storage fixture creates a throwaway schema
and drops it. Keep it that way.

## Backend

The container is **0.25 vCPU / 0.5 GiB with no scale-to-zero**. That rules out
loading model weights in-process — it is why reranking is done by the LLM rather
than a local cross-encoder.

`Settings` uses `extra="ignore"` on purpose: the deployed container still carries
environment variables from older revisions, and a strict model would crash at
startup rather than ignore them.

## Testing

```bash
python -m pytest        # 262 tests
```

Tests needing a credential skip with a stated reason rather than failing:
retrieval quality needs `GOOGLE_API_KEY`, FUTBOARD storage needs
`FUTBOARD_DATABASE_URL`.

The frontend has no JS test runner and does not need one. Its guards are pytest
files that drive `node` against the real ESM modules, or that read the JSX as
text. Adding a JS test stack to check a handful of invariants would cost more
than it returns.

Two kinds of check catch different things, and both are needed: the static tests
catch a missing dictionary key (`{undefined}` renders as nothing, so a browser
sweep cannot see it), and a browser sweep catches crashes and layout overflow
that no static check can predict.

## Commits

Domingo is the sole author. Never add `Co-Authored-By` or any AI attribution
trailer.
