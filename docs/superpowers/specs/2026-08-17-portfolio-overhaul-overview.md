# Portfolio overhaul — overview and decomposition

**Date:** 2026-08-17
**Status:** approved (design), pending implementation plans

## Context

`agentic-rag-portfolio` is a personal portfolio site: a React frontend on Azure
Static Web Apps, a FastAPI RAG backend on Azure Container Apps, and a scheduled
GitHub Actions job that publishes La Liga data as static JSON.

Four improvements were requested:

1. Frontend fully in English.
2. Modernise the RAG, which has aged badly.
3. Consolidate the documents the RAG reads into a single source of truth.
4. Fix the broken La Liga pipeline and improve the visualisations (the standings
   table shows no Conference zone).

The estate constraint throughout: **keep the CRT/phosphor-green aesthetic, keep
the analytics logging, and keep the Azure deployment working.**

## Findings that reshaped the work

Investigation turned up several things that were not visible from the request.

**The local checkout was stale, not the remote.** Local `HEAD` was a direct
ancestor of `origin/main`, 1570 commits behind (nearly all automated
`chore: update La Liga data` commits). Fast-forwarded; nothing was lost.

**Retrieval is a no-op.** The knowledge base holds 25 chunks and the effective
`top_k` is 35-45, so every query retrieves the entire corpus. The hybrid
vector+BM25 Reciprocal Rank Fusion is decorative — it re-ranks a set that is
already complete.

**The prompt is the real source of truth.** Exact grades, project descriptions
and strength lists are hardcoded into a ~70-line system prompt. The documents
are decoration, which is why the corpus and the answers drift apart.

**The documents duplicate and contradict each other.** `more_information.docx`
is a verbatim copy of the second half of `cv_rag.docx` (~8k of its 13k
characters). They disagree on the MyES tenure ("once meses" vs "12 meses").

**The chatbot misdescribes itself.** The documents claim "Azure AI Search
(búsqueda híbrida semántica)" and "chunking 1200/150". Neither is true: the
service was deleted from the subscription, and the code uses a local embeddings
cache with Google `gemini-embedding-001` + BM25 + RRF.

**Two Azure resources are dead config.** `AZURE_SEARCH_*` and
`AZURE_OPENAI_*` env vars point at resources that no longer exist in the
subscription. The entire `AzureOpenAI` branch of `_build_llm_client` is
unreachable; production runs on OpenAI `gpt-4.1-mini` directly. No wasted
spend, but the config lies about the architecture.

**All API keys are plaintext env vars.** See spec 0 — this is the urgent item.

**La Liga had three separate faults**, not one. Detailed in spec D.

## Decomposition

The work splits into four independently deliverable blocks. Ordering is driven
by one dependency: `profile.yml` feeds both the RAG index and the frontend's
certification component, so block A gates B and C.

| Block | Scope | Depends on |
|-------|-------|------------|
| **0** | Secret rotation, move to Container Apps secrets, delete dead config | — |
| **A** | `profile.yml` single source of truth + KB generator | — |
| **B** | Agentic RAG rebuilt on the generated KB | A |
| **C** | Frontend English + La Liga visualisation improvements | A (certs) |
| **D** | La Liga pipeline correctness | — (hotfix shipped) |

Each block gets its own spec and implementation plan.

**Ownership note.** The Conference League zone, the derived form column and the
fixtures/results panels appear in both spec C and spec D, because each is a
pipeline change plus a frontend change. **Block C owns their implementation
end to end**, including the `pipeline_laliga.py` edits they require; spec D
documents them only as the pipeline-side rationale. Spec D's own deliverable is
phase 2, the prediction cold start.

## Decisions taken

| Question | Decision |
|----------|----------|
| Sequencing | La Liga hotfix first, then design the rest |
| Source of truth format | Structured YAML feeding both RAG and frontend |
| RAG target | Structured KB + real retrieval + reranking + agentic tool-calling |
| Embeddings | Stay on Google, upgrade to `gemini-embedding-2` |
| Chat model | `gpt-4.1-mini` → `gpt-5.6-luna` |
| Reranker | LLM-based (container is 0.25 vCPU / 0.5 GiB — a local cross-encoder would risk OOM) |
| Assistant language | Bilingual; answers in the language of the question, KB written in English |
| Predictions at matchday 1 | Left as-is for now, addressed in spec D phase 2 |

## Azure estate to preserve

The whole footprint is five resources:

- `cae-rag-domingo` — Container Apps environment (spaincentral)
- `rag-backend` — Container App, 0.25 vCPU / 0.5 GiB, min=max=1 replica
- `rag-frontend-swa` — Static Web App, Free plan (westeurope)
- `workspace-rgragdomingoprod8d03` — Log Analytics
- `mc-cae-rag-doming-api-domingoberbe-8417` — managed certificate

There is **no** scale-to-zero (min replicas = 1), which is what rules the
reranker decision. There is **no** Azure AI Search and **no** Azure OpenAI
resource.

## Related specs

- [Block 0 — secrets and config hygiene](2026-08-17-secrets-and-config-hygiene-design.md)
- [Block A — single source of truth](2026-08-17-single-source-of-truth-design.md)
- [Block B — agentic RAG](2026-08-17-agentic-rag-design.md)
- [Block C — frontend English and visualisations](2026-08-17-frontend-english-and-viz-design.md)
- [Block D — La Liga pipeline](2026-08-17-laliga-pipeline-design.md)
