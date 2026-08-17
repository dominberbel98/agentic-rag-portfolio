# Block A — Single source of truth

**Date:** 2026-08-17
**Depends on:** nothing
**Blocks:** Block B (RAG index), Block C (certifications component)

## Problem

The knowledge base is three `.docx` files in the gitignored `documentos/`
directory, and they are in poor shape.

**Duplication.** `more_information.docx` (7,930 chars) is a verbatim copy of the
second half of `cv_rag.docx` (13,170 chars). Roughly 8k of 13k characters are
redundant, which is why 8 of the 25 indexed chunks are near-duplicates.

**Contradiction.** The MyES Sevilla tenure is "un periodo de once meses" in the
`cv_rag` narrative and "En 12 meses" in the copied section.

**Staleness that makes the bot lie about itself.** Both files describe the
chatbot's own architecture as "Azure AI Search (búsqueda híbrida semántica)" with
"chunking con solapamiento (1200 chars / 150 overlap)". Neither is true: the
Azure AI Search resource was deleted from the subscription, the code uses a local
embeddings cache with Google `gemini-embedding-001` + BM25 + RRF, and
`index_documents.py` chunks at 650/100.

**Missing content.** Three projects that are live on the site are absent from
the knowledge base entirely: the La Liga dashboard and PySpark pipeline, the
credit scoring model, and the product recommendation engine.

**Duplication across the stack.** The six certifications are hardcoded in
`frontend/src/components/Certificaciones.jsx` *and* listed in the documents. Two
places to edit, already drifting (the docs say "Power BI avanzado de linkedin",
the component says "Power BI Avanzado" with dates and skill tags the docs lack).

## Design

`data/profile.yml` becomes the only place the profile is authored. A generator
derives everything else from it.

```
data/profile.yml
      │
      ├── scripts/build_kb.py ──→ data/kb/*.md        (RAG documents, ~50)
      │                       └─→ embeddings_cache.json (via index_documents.py)
      │
      └── scripts/build_kb.py ──→ frontend/public/data/profile.json
                                   (certifications, skills — consumed by the UI)
```

### Schema

```yaml
meta:
  name: Domingo Berbel
  headline: ...
  location: Madrid, Spain
  emails: [...]
  linkedin: ...
  github: ...

roles:            # one entry per position, most recent first
  - id: data-equity
    company: Data Equity
    title: Data Scientist
    location: Madrid
    start: 2025-10
    end: null           # null means current
    summary: ...
    achievements: [...]
    stack: [...]

education:
  - id: master-ucm
    institution: Universidad Complutense de Madrid
    degree: Máster en Data Science, Big Data & Business Analytics
    start: 2024
    end: 2025
    grades: [{ subject: Python Avanzado, score: 10 }, ...]
    honours: [...]
    notes: ...

projects:
  - id: portfolio-chatbot
    name: ...
    year: 2026
    summary: ...
    problem: ...
    approach: ...
    stack: [...]
    outcome: ...
    repo: ...
    live_url: ...

certifications:
  - id: snowflake-snowpro
    title: "SnowPro Associate: Platform"
    issuer: Snowflake
    date: 2025-10
    expires: 2027-10
    image: /certs/snowflake-snowpro.png
    skills: [...]

skills:
  languages: [...]
  data: [...]
  cloud: [...]
  ml: [...]
  bi: [...]

narrative:          # prose from letter_rag.docx, kept as prose
  adaptability: ...
  resilience: ...
  teamwork: ...
  career_change: ...
```

Authored in **English**, since the frontend is English and the assistant
translates at answer time (see Block B).

### Generator

`scripts/build_kb.py` walks the YAML and emits one Markdown document per entity,
each with frontmatter carrying `id`, `category` and `title`. Entity granularity
is deliberate: it is what makes retrieval meaningful in Block B, where today
`top_k` exceeds the corpus size.

Naming follows the entity id: `role:data-equity`, `project:laliga-dashboard`,
`education:master-ucm`, `certification:snowflake-snowpro`, `narrative:resilience`.

The same pass writes `frontend/public/data/profile.json` with the certification
and skill arrays, so `Certificaciones.jsx` stops hardcoding them.

It also writes `data/kb/vocabulary.json`: the flat set of every technology,
employer, institution and credential named anywhere in the profile. Block B's
groundedness check consumes this to detect fabricated entities, which is only
possible because the YAML holds them as structured fields rather than prose.

### Content corrections

Beyond mechanical conversion, the migration fixes what the audit found:

- MyES tenure reconciled to a single figure.
- The `portfolio-chatbot` project entry describes the **actual** architecture:
  local embeddings cache with `gemini-embedding-2`, BM25 + RRF hybrid retrieval,
  LLM reranking, agentic tool-calling, FastAPI on Azure Container Apps, React on
  Azure Static Web Apps. No Azure AI Search.
- New entries for `laliga-dashboard`, `credit-scoring`, `product-recommender`.
- Grades and honours become structured data rather than prose baked into a
  prompt, which is what lets Block B stop hardcoding them.

The three `.docx` files move to `documentos/legacy/` — retained, still
gitignored, no longer read by any script.

## Isolation

The YAML is data with no behaviour. `build_kb.py` is a pure function from that
file to generated artefacts: given the same YAML it produces the same output, so
it is testable without network or API keys. Consumers depend only on the
generated artefacts, never on the YAML directly, so its internal shape can
change without touching the backend or the frontend.

## Error handling

- **Schema validation** runs before generation. A Pydantic model rejects unknown
  keys, missing required fields, and malformed dates, with the offending path
  named. Generating a partial KB from an invalid profile is worse than failing.
- **Referential integrity**: `project.stack` entries and `role.stack` entries
  must resolve against the `skills` lists, so a typo cannot silently create a
  skill that only exists in one place.
- **Uniqueness**: duplicate ids are a hard error, since ids are the retrieval
  addresses in Block B.
- **Non-destructive output**: generated files are written to a temp location and
  moved into place only after the whole pass succeeds, so a mid-run failure
  cannot leave a half-written KB that the backend would then load.
- **Currency check**: exactly one role may have `end: null`. More than one
  current job is a data error, and it is the field most likely to rot.

## Testing

- Schema validation accepts the real `profile.yml` and rejects fixtures with a
  missing required field, a duplicate id, two current roles, and an unresolvable
  stack entry.
- Generator output is deterministic: two runs over the same input produce
  byte-identical files.
- No generated document is empty or whitespace-only.
- Every `certifications[].image` path resolves to a file under
  `frontend/public/`.
- A content assertion that the corpus contains no term absent from the YAML —
  the guard against the class of drift that let "MongoDB" reach production (see
  Block B).

## Verification

Diff the generated corpus against the current 25 chunks and confirm: no
duplicated passage survives, every fact in the old corpus appears in the new one
or was deliberately dropped as false, and the three missing projects are present.
