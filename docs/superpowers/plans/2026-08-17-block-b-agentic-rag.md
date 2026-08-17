# Block B — Agentic RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace a 1,200-line keyword-routed service whose retrieval returns the whole corpus with a tool-calling agent over addressable entity documents, and stop it fabricating credentials.

**Architecture:** Four focused modules replace one monolith. `retrieval.py` owns the index and hybrid search with no LLM involvement. `agent.py` gives the model three tools and runs a bounded loop. `grounding.py` checks named entities in the answer against the profile vocabulary. `rag_service.py` shrinks to orchestration and the response contract, so `chat.py` and the frontend are untouched.

**Tech Stack:** Python 3.11, OpenAI Python SDK (function calling + streaming), Google Generative AI embeddings, rank-bm25, numpy, pytest.

## Global Constraints

- The `ChatResponse` model and the SSE wire format **must not change** — `frontend/src/components/Chat.jsx` parses `{token}` / `{done, needs_contact_form, contact_emails, contact_linkedin}` and is out of scope here.
- Keep working, untouched: `analytics_store` (SQLite + JSON export), `captcha_service`, `RequestGuards` (per-IP rate limit, daily token budget), the admin endpoints, and deployment on Azure Container Apps.
- Container budget is **0.25 vCPU / 0.5 GiB**. No in-process ML model may be loaded. Reranking is done by the LLM.
- Embedding model: `gemini-embedding-2`. Its space is **incompatible** with `gemini-embedding-001`, so the cache must be rebuilt wholesale.
- Chat model: `gpt-5.6-luna` ($0.20/$0.02/$1.20 per 1M input/cached/output).
- Answer in the language of the question. The corpus is English.
- Agent loop is bounded: hard caps on iterations and total tool calls per question.
- Safety behaviour is preserved: inappropriate and off-topic questions still return the out-of-scope message and the `OUT_OF_SCOPE` contract still drives `needs_contact_form`.

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/services/retrieval.py` | Create. Index load, hybrid vector+BM25+RRF search, `get`/`list`. No LLM, no network beyond the query embedding it is handed. |
| `backend/app/services/agent.py` | Create. Tool schemas, bounded tool-calling loop, LLM rerank, streaming. |
| `backend/app/services/grounding.py` | Create. Vocabulary-backed fabricated-entity detection. |
| `backend/app/services/rag_service.py` | Rewrite. Orchestration + `ChatResponse`. Target under 250 lines, from ~1,200. |
| `backend/app/services/embedding_service.py` | Modify. Add `RETRIEVAL_QUERY` support and model selection; reuse one client. |
| `backend/app/config.py` | Modify. Model names, agent limits, cache paths. |
| `backend/app/main.py` | Modify. Load the index and vocabulary at startup. |
| `tests/test_retrieval.py` | Create. Fixture index, no network. |
| `tests/test_agent.py` | Create. Stubbed LLM. |
| `tests/test_grounding.py` | Create. Pure. |
| `tests/test_golden_questions.py` | Create. Real production traffic as a retrieval regression suite. |

## Deleted, with reasons

- Seven `_is_*_question` predicates and ~400 lines of Spanish keyword lists. The model narrows by `category` instead.
- Hardcoded grades, mandated project mentions and the numbered strengths list in the system prompt. They live in `profile.yml` now.
- Duplicated ES/EN message pairs, replaced by one language instruction.
- The unreachable `AzureOpenAI` branch of `_build_llm_client` and the never-called `_language_answer`.

---

### Task 1: Retrieval index

**Files:** Create `backend/app/services/retrieval.py`, `tests/test_retrieval.py`

**Interfaces:**
- Consumes: `embeddings_cache.json` (Block A format: `id`, `source`, `category`, `title`, `chunk`, `embedding`).
- Produces:
  - `Document` — frozen dataclass: `id`, `category`, `title`, `text`, `embedding: np.ndarray`.
  - `RetrievalIndex.load(cache_path, vocabulary_path) -> RetrievalIndex`
  - `RetrievalIndex.search(query, query_embedding, top_k=6, category=None) -> list[Document]`
  - `RetrievalIndex.get(entity_id) -> Document | None`
  - `RetrievalIndex.list_entities(category=None) -> list[tuple[str, str]]` — `(id, title)`
  - `RetrievalIndex.categories() -> list[str]`
  - `RetrievalIndex.vocabulary -> frozenset[str]`
  - `rrf_fuse(rankings, k=60) -> list[int]` — pure, unit-testable.

Key behaviours to test: RRF ordering; `category` filtering; BM25-only degradation when `query_embedding is None`; `top_k` actually truncating (the bug this block exists to fix); unknown id returning `None` rather than raising.

- [ ] Step 1: Write failing tests against a fixture index built from `small_profile`.
- [ ] Step 2: Run — expect `ModuleNotFoundError`.
- [ ] Step 3: Implement. Vectorise cosine similarity as a single matrix product rather than a Python loop over documents — the old code looped per chunk.
- [ ] Step 4: Run — all pass.
- [ ] Step 5: Commit.

### Task 2: Grounding check

**Files:** Create `backend/app/services/grounding.py`, `tests/test_grounding.py`

**Interfaces:**
- Consumes: `RetrievalIndex.vocabulary`.
- Produces:
  - `GroundingResult` — `ok: bool`, `unsupported: list[str]`.
  - `check_answer(answer, retrieved_texts, vocabulary) -> GroundingResult`
  - `extract_candidate_entities(text) -> list[str]` — pure.

Closed-vocabulary, not NLI. Extract capitalised tokens and technology-shaped strings, drop sentence-initial words, common English capitals, and anything present in the retrieved text or the vocabulary. What remains is a fabricated entity.

Tests must include the real regression: an answer containing "MongoDB" is flagged; the same answer without it is clean; "Data Equity" and "PySpark" are never flagged; a sentence starting with "Domingo" or "The" produces no false positive.

- [ ] Steps 1-5 as above.

### Task 3: Agent loop

**Files:** Create `backend/app/services/agent.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: `RetrievalIndex`, `grounding.check_answer`.
- Produces:
  - `ProfileAgent(client, model, index, embedder, limits)`
  - `AgentResult` — `answer: str`, `documents: list[Document]`, `out_of_scope: bool`, `regenerated: bool`
  - `ProfileAgent.answer(question, history, language, now) -> AgentResult`
  - `ProfileAgent.stream(question, history, language, now) -> Iterator[str]` — yields answer text, not SSE frames; `rag_service` owns the wire format.
  - `AgentLimits` — `max_iterations`, `max_tool_calls`, `max_documents`.
- Tools exposed to the model: `search_profile(query, category?)`, `get_entity(id)`, `list_entities(category?)`.

Tests with a stubbed client: a tool call is dispatched and its result fed back; multi-hop issues a second search; the iteration cap terminates the loop; a malformed tool call returns a typed error to the model instead of raising; an unknown entity id is recoverable; `OUT_OF_SCOPE` is detected.

- [ ] Steps 1-5 as above.

### Task 4: Rewire `rag_service.py`

**Files:** Rewrite `backend/app/services/rag_service.py`, modify `embedding_service.py`, `config.py`, `main.py`

**Interfaces:**
- Preserves exactly: `AgenticRAGService.ask(question, top_k, history, current_time) -> ChatResponse`, `AgenticRAGService.ask_stream(...) -> Generator[str]`, `AgenticRAGService.initialize_cache(path)`.

`embedding_service.py` gains `task_type` selection. The current code embeds **queries** with `RETRIEVAL_DOCUMENT` and `title="Document chunk"`, which is wrong for asymmetric retrieval — queries must use `RETRIEVAL_QUERY`. It also constructs a fresh service per question; the client is configured once now.

- [ ] Steps 1-5, ending with the full suite green.

### Task 5: Reindex and verify against production traffic

**Files:** Create `tests/test_golden_questions.py`

`preguntas.json` holds 126 real logged interactions. Genuine profile questions become retrieval assertions (which entity ids must be retrieved); the off-topic and abusive rows become guardrail assertions (`out_of_scope` still holds without the keyword predicates).

- [ ] Step 1: Re-embed the corpus with `gemini-embedding-2`.
- [ ] Step 2: Assert the cache reports the new model and 32 documents.
- [ ] Step 3: Run the golden set locally.
- [ ] Step 4: Commit.

## Self-Review

**Spec coverage:** retrieval-is-a-noop → Task 1 (`top_k` truncation test); keyword predicates → Task 3 (`category` replaces them); facts-in-prompt → Task 4 (prompt keeps only role/tone/safety); hallucination → Task 2 + Task 5; dead code → Task 4; module split → Tasks 1-4; embedding upgrade → Task 5; model upgrade → Task 4 config; LLM rerank → Task 3; golden set → Task 5; guardrails preserved → Task 5.

Gap found and closed: the spec's error-handling section requires the new cache to be written under a new filename with fallback to the previous one. That is a `main.py`/`config.py` concern, folded into Task 4.

**Type consistency:** `Document` is the single retrieval unit across Tasks 1, 3 and 4. `RetrievalIndex.search` keeps the same signature everywhere. `check_answer(answer, retrieved_texts, vocabulary)` is identical in Tasks 2 and 3.
