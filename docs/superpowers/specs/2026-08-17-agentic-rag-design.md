# Block B — Agentic RAG

**Date:** 2026-08-17
**Depends on:** Block A (generated KB)

## Problem

`backend/app/services/rag_service.py` is ~1,200 lines. The retrieval it performs
does not function as retrieval, and the answers it produces are not reliably
grounded.

**Retrieval is a no-op.** The corpus holds 25 chunks. `ask()` defaults to
`top_k=35`, and the intent helpers raise the effective value to 40 or 45. Every
query therefore returns the entire corpus. The vector search, the BM25 index and
the Reciprocal Rank Fusion all run, then rank a set that was already complete.
The cosine similarity loop is pure overhead.

**Roughly 400 lines are Spanish keyword lists.** Seven predicates
(`_is_company_question`, `_is_language_question`, `_is_education_question`,
`_is_project_question`, `_is_professional_scope_question`,
`_is_allowed_profile_question`, `_is_occupation_question`) match hardcoded
substrings to decide routing and to append hand-written query expansion terms.
They are unmaintainable, they only cover phrasings someone thought of, and they
are why the service is bilingual by accident rather than by design.

**Facts live in the prompt, not the knowledge base.** The system prompt hardcodes
exact grades ("Python Avanzado 10, Deep Learning 9.75, Estadística 9.5, Apache
Spark 9.20"), mandated project mentions, and a numbered list of strengths. The
prompt is the real source of truth; retrieval is decoration. Any correction has
to be made in Python.

**It hallucinates skills.** Verified against production on 2026-08-17. Asked
"What is Domingo currently working on and at which company?", the deployed
service answered that he applies expertise in "Python, PySpark, SQL, Snowflake,
**MongoDB**, and cloud infrastructure" and frames the role around "**MLOps**"
and "**observability**". None of those three terms appears anywhere in the source
documents. For a CV chatbot this is the most serious defect in the system: it
invents credentials the owner would have to answer for in an interview.

**Dead code.** `_build_llm_client` has an `AzureOpenAI` branch that is
unreachable because `OPENAI_API_KEY` is set, pointing at a resource that no
longer exists. `_language_answer` is never called from anywhere.

## Design

```
question
   │
   ├─ guardrails (kept)  ── inappropriate / off-topic / rate limit / token budget
   │
   └─ agent loop (gpt-5.6-luna, tool-calling)
         │
         ├── list_entities(category?)      →  the index, so the model can orient
         ├── search_profile(query, category?) →  hybrid vector + BM25 + RRF, top 12
         └── get_entity(id)                →  one full document, verbatim
         │
         ├─ LLM rerank of candidates → top 5-8 into context
         ├─ multi-hop: the model may search again if the first pass is thin
         └─ groundedness check before returning
   │
answer, in the language of the question
```

The model decides what to retrieve instead of a keyword table deciding for it.
This is what the repository name has promised since it was created and what the
current code does not do.

### What is removed

- All seven `_is_*_question` predicates and their keyword lists (~400 lines).
- Hardcoded facts in the system prompt. It keeps role, tone, scope and safety
  instructions only — target ~40 lines, down from ~70 dense ones.
- The duplicated ES/EN message pairs, replaced by a single instruction to answer
  in the question's language.
- The unreachable `AzureOpenAI` branch and `_language_answer`.

### What is kept, deliberately

The owner's constraint is that logging and Azure keep working:

- `analytics_store` — SQLite question analytics and JSON export, untouched.
- The pre-LLM safety guardrails and the `OUT_OF_SCOPE` contract.
- `captcha_service` (Turnstile), per-IP rate limiting, daily token budget.
- SSE streaming, so the frontend contract does not change.
- Deployment on Azure Container Apps.

### Retrieval

Hybrid stays — vector plus BM25 — but now over 32 entity documents with `top_k`
in the 5-8 range, where the ranking actually discriminates.

**Amended during implementation: RRF was replaced.** Measured over 18 golden
questions from the production logs, Reciprocal Rank Fusion was worse than not
fusing at all — 13/18 recall@6 at 0.562 MRR against dense-alone's 18/18 at 0.659.
RRF discards score magnitude and keeps only rank, so a decisive dense win
(0.731 against a 0.695 runner-up) became "rank 1 versus rank 2" and weak keyword
noise displaced it entirely. Normalised weighted score fusion scores 18/18 at
0.696, beating dense alone. Two further defects surfaced in the same measurement:
BM25 ran without stopword removal, and the subject's own name matched every
document in his own corpus, making the lexical ranking arbitrary.

`search_profile` accepts an optional `category` filter (`role`, `project`,
`education`, `certification`, `narrative`), which replaces hand-written query
expansion: the model narrows the search itself instead of the service appending
"experiencia laboral empresas trabajo actual Data Equity" to the query string.

### Models

**Embeddings: `gemini-embedding-001` → `gemini-embedding-2`.** GA as of April
2026, multimodal, 8,192 input tokens against the previous 2,048, 3,072 dimensions
by default with Matryoshka truncation, and custom task instructions. The
embedding spaces are **incompatible**, so the whole corpus must be re-embedded —
trivial at ~50 documents.

**Chat: `gpt-4.1-mini` → `gpt-5.6-luna`.** Cheaper on all three axes and a
generation newer, with the native tool-calling the agent loop needs:

| | input /1M | cached input /1M | output /1M |
|---|---|---|---|
| gpt-4.1-mini (current) | $0.40 | $0.10 | $1.60 |
| gpt-5.6-luna | $0.20 | $0.02 | $1.20 |

Cached input at 5× cheaper matters here because the system prompt repeats on
every turn of every conversation. Against the existing 50,000 tokens/day cap the
worst case is a few euros a month.

**Reranking: LLM-based, not a local cross-encoder.** Decided by the real
container spec: `rag-backend` runs on **0.25 vCPU / 0.5 GiB**. A cross-encoder
would add ~90 MB of weights plus onnxruntime and a tokenizer into 0.5 GiB
alongside FastAPI and the embedding matrix, risking OOM, and would be very slow
on a quarter of a core. Scale-to-zero is not a factor — min replicas is 1 — but
memory and CPU are.

### Groundedness

The hallucination is a design requirement, not a tuning problem. Two mechanisms:

1. **Retrieved-only instruction with an explicit refusal path.** The prompt
   states that any technology, employer, metric or credential not present in the
   retrieved documents must not be named, and that the correct response to a gap
   is to say the profile does not cover it.
2. **A post-generation check**, implemented as a closed-vocabulary test rather
   than open-ended NLI, and **language-aware** (added during implementation:
   the corpus is English and answers are not, so a Spanish answer flagged ten
   translated terms and forced a regeneration on every Spanish question;
   technology names do not translate, which is the class that matters, so
   multiword phrases are skipped for non-English). Block A already knows every technology, employer,
   institution and credential in the profile, because they are structured fields
   in `profile.yml`. The generator emits that set as a vocabulary file. After
   generation, `grounding.py` extracts candidate entity tokens from the answer —
   capitalised terms and known technology-shaped strings — and flags any that
   appear in neither the retrieved context nor the vocabulary. A flagged term
   triggers one regeneration with the offending term quoted back to the model.

   This is deliberately narrow. It cannot catch a fabricated *claim* built from
   real words ("led a team of twelve"), only a fabricated *entity* — which is the
   class that produced "MongoDB" and the class that does concrete damage on a CV.
   Broader claim-level verification is out of scope; a false-negative-prone check
   that is cheap and always runs is worth more here than an expensive one.

### Structure

`rag_service.py` at 1,200 lines is doing too much. It splits along its actual
seams:

| Module | Responsibility |
|--------|----------------|
| `retrieval.py` | Index loading, hybrid search, RRF. No LLM. |
| `agent.py` | Tool definitions, the agent loop, reranking. |
| `guardrails.py` | Existing safety filters (already separate, kept). |
| `grounding.py` | Post-generation support check. |
| `rag_service.py` | Thin orchestration and the `ChatResponse` contract. |

Each is independently testable; `retrieval.py` in particular becomes testable
without an API key.

## Error handling

- **Embedding failure** on a query: fall back to BM25-only rather than returning
  the "no hay embeddings cacheados" placeholder that currently reaches users.
- **Index load failure**: the new cache is written under a new filename and the
  service falls back to the previous one if the new file is absent or malformed,
  so a bad reindex cannot take the bot down.
- **Tool-loop bounds**: hard cap on iterations and on total tool calls per
  question, so a model that keeps searching cannot exhaust the token budget.
- **Malformed tool arguments**: an unknown `id` or `category` returns a typed
  error to the model rather than raising, letting it correct itself.
- **LLM unavailable**: the existing fallback path stays, but returns an honest
  "temporarily unavailable" rather than the current canned profile summary, which
  is indistinguishable from a real answer.

## Testing

The repository has no tests today. The highest-value additions:

- **A golden question set.** `preguntas.json` holds 126 logged interactions of
  *real production traffic* — question, answer, `out_of_scope` flag and user
  agent per row. Roughly 20 of the genuine profile questions, spanning Spanish
  and English, become the regression suite for retrieval: for each, assert which
  entity ids must appear in the retrieved set. The off-topic and abusive rows in
  the same file ("Hala Madrid", insults, questions about his private life) become
  the guardrail regression suite, asserting `out_of_scope` still holds after the
  keyword predicates are deleted. The file stays gitignored — it contains
  visitor IP addresses.
- **Groundedness regression.** The exact production query that produced the
  MongoDB hallucination becomes a test asserting that no unsupported technology
  appears in the answer.
- **Retrieval unit tests** with a fixture index, no network: RRF ordering,
  category filtering, BM25-only degradation.
- **Agent loop tests** with a stubbed LLM: multi-hop triggers a second search;
  the iteration cap holds; a malformed tool call is recovered from.
- **Language behaviour**: a Spanish question yields a Spanish answer and an
  English question an English one, with the KB in English either way.

## Verification

Run the golden set against the deployed service before and after. The bar is:
retrieval precision improves (fewer than 8 documents in context instead of all
25), no unsupported term appears in any answer, and the answers to the questions
real visitors asked are at least as good as today's.
