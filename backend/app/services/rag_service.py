from __future__ import annotations

import json
import logging
import re
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from openai import AzureOpenAI, OpenAI

from app.config import settings
from app.models import ChatResponse, Citation

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    source: str
    chunk: str


@dataclass
class CachedEmbedding:
    """In-memory representation of a cached embedding chunk."""
    chunk_id: str
    source: str
    chunk_text: str
    embedding: np.ndarray  # 3072-dimensional vector


class AgenticRAGService:
    # Class variable: shared cache loaded at startup
    _cached_embeddings: list[CachedEmbedding] | None = None
    _embedding_model: str | None = None
    _embedding_dimensions: int | None = None
    _bm25: Any | None = None

    def __init__(self) -> None:
        self._llm_client = self._build_llm_client()
        self._chat_model = self._build_chat_model()

    @classmethod
    def initialize_cache(cls, cache_path: str = "embeddings_cache.json") -> None:
        """Load embeddings cache at application startup (FastAPI lifespan event)."""
        try:
            cache_file = Path(cache_path)
            if not cache_file.exists():
                logger.warning(f"Embeddings cache not found at {cache_path}")
                cls._cached_embeddings = []
                return

            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            cls._embedding_model = data.get("model", "unknown")
            cls._embedding_dimensions = data.get("dimensions", 3072)
            logger.info(
                f"Loaded embedding metadata: model={cls._embedding_model}, "
                f"dimensions={cls._embedding_dimensions}"
            )

            cls._cached_embeddings = []
            for item in data.get("chunks", []):
                embedding_vector = np.array(item["embedding"], dtype=np.float32)
                cached = CachedEmbedding(
                    chunk_id=item["id"],
                    source=item["source"],
                    chunk_text=item["chunk"],
                    embedding=embedding_vector,
                )
                cls._cached_embeddings.append(cached)

            logger.info(f"Loaded {len(cls._cached_embeddings)} embedding chunks from cache")

            # Build BM25 index over cached chunks
            try:
                from rank_bm25 import BM25Okapi
                tokenized = [item.chunk_text.lower().split() for item in cls._cached_embeddings]
                cls._bm25 = BM25Okapi(tokenized)
                logger.info(f"Built BM25 index over {len(tokenized)} chunks")
            except ImportError:
                logger.warning("rank-bm25 not installed, hybrid search disabled")
                cls._bm25 = None
        except Exception as e:
            logger.error(f"Failed to load embeddings cache: {e}")
            cls._cached_embeddings = []
            cls._bm25 = None

    def ask(
        self,
        question: str,
        top_k: int = 35,
        history: list[dict] | None = None,
        current_time: datetime | None = None,
    ) -> ChatResponse:
        history = history or []
        current_time = current_time or datetime.now(timezone.utc)
        language = self._detect_user_language(question, history)
        logger.info("[ASK] Q=%r  history_turns=%d", question[:120], len(history))

        if self._is_greeting_question(question):
            answer = self._greeting_answer(language)
            logger.info("[ANSWER] greeting_intent=True preview=%r", answer[:150])
            return ChatResponse(
                answer=answer,
                used_retrieval=False,
                citations=[],
                needs_contact_form=False,
                contact_emails=self._contact_emails(),
                contact_linkedin=settings.professional_linkedin or None,
            )

        if self._is_contact_question(question):
            answer = self._contact_answer(language)
            logger.info("[ANSWER] contact_intent=True preview=%r", answer[:150])
            return ChatResponse(
                answer=answer,
                used_retrieval=False,
                citations=[],
                needs_contact_form=False,
                contact_emails=self._contact_emails(),
                contact_linkedin=settings.professional_linkedin or None,
            )

        if self._is_inappropriate_question(question):
            answer = self._out_of_scope_message(language)
            logger.info("[ANSWER] inappropriate_filter=True Q=%r", question[:120])
            return ChatResponse(
                answer=answer,
                used_retrieval=False,
                citations=[],
                needs_contact_form=True,
                contact_emails=self._contact_emails(),
                contact_linkedin=settings.professional_linkedin or None,
            )

        if self._is_generic_technical_help_question(question) or self._is_clearly_offtopic_question(question):
            answer = self._out_of_scope_message(language)
            logger.info("[ANSWER] offtopic_filter=True Q=%r", question[:120])
            return ChatResponse(
                answer=answer,
                used_retrieval=False,
                citations=[],
                needs_contact_form=False,
                contact_emails=self._contact_emails(),
                contact_linkedin=settings.professional_linkedin or None,
            )

        use_retrieval = self._should_retrieve(question)
        chunks = self._retrieve(question, top_k, history) if use_retrieval else []
        logger.info("[RETRIEVE] chunks=%d sources=%s", len(chunks), [c.source for c in chunks])
        answer, out_of_scope = self._generate_answer(question, chunks, history, current_time, language)
        logger.info("[ANSWER] out_of_scope=%s preview=%r", out_of_scope, answer[:150])
        citations = [Citation(source=c.source, chunk=c.chunk) for c in chunks] if settings.show_citations else []
        return ChatResponse(
            answer=answer,
            used_retrieval=use_retrieval,
            citations=citations,
            needs_contact_form=out_of_scope,
            contact_emails=self._contact_emails(),
            contact_linkedin=settings.professional_linkedin or None,
        )

    def ask_stream(
        self,
        question: str,
        top_k: int = 35,
        history: list[dict] | None = None,
        current_time: datetime | None = None,
    ) -> Generator[str, None, None]:
        """Yield SSE-formatted chunks for streaming responses."""
        history = history or []
        current_time = current_time or datetime.now(timezone.utc)
        language = self._detect_user_language(question, history)

        # Fast-path intents (no LLM needed)
        if self._is_greeting_question(question):
            answer = self._greeting_answer(language)
            yield f"data: {json.dumps({'token': answer})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        if self._is_contact_question(question):
            answer = self._contact_answer(language)
            yield f"data: {json.dumps({'token': answer})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        if self._is_inappropriate_question(question):
            answer = self._out_of_scope_message(language)
            yield f"data: {json.dumps({'token': answer})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': True, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        if self._is_generic_technical_help_question(question) or self._is_clearly_offtopic_question(question):
            answer = self._out_of_scope_message(language)
            logger.info("[STREAM] offtopic_filter=True Q=%r", question[:120])
            yield f"data: {json.dumps({'token': answer})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        use_retrieval = self._should_retrieve(question)
        chunks = self._retrieve(question, top_k, history) if use_retrieval else []

        if not self._llm_client or not self._chat_model:
            fallback, out_of_scope = self._fallback_answer(question, chunks, language)
            yield f"data: {json.dumps({'token': fallback})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': out_of_scope, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        messages = self._build_messages(question, chunks, history, current_time, language)
        collected = []
        _OOS = "OUT_OF_SCOPE"
        buffering = True  # hold tokens while they could still spell OUT_OF_SCOPE
        buffer_tokens: list[str] = []
        try:
            stream = self._llm_client.chat.completions.create(
                model=self._chat_model,
                temperature=0.05,
                max_tokens=800,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected.append(delta.content)
                    if buffering:
                        buffer_tokens.append(delta.content)
                        so_far = "".join(buffer_tokens).strip()
                        if so_far == _OOS:
                            # Confirmed OUT_OF_SCOPE — replace entirely
                            if self._is_professional_scope_question(question):
                                fallback, _ = self._fallback_answer(question, chunks, language)
                                yield f"data: {json.dumps({'token': fallback})}\n\n"
                                yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                            else:
                                yield f"data: {json.dumps({'token': self._out_of_scope_message(language)})}\n\n"
                                yield f"data: {json.dumps({'done': True, 'needs_contact_form': True, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                            return
                        elif not _OOS.startswith(so_far):
                            # Diverged — flush buffer and switch to direct streaming
                            buffering = False
                            for bt in buffer_tokens:
                                yield f"data: {json.dumps({'token': bt})}\n\n"
                    else:
                        yield f"data: {json.dumps({'token': delta.content})}\n\n"
        except Exception as exc:
            logger.error("[STREAM] LLM error: %s", exc)
            yield f"data: {json.dumps({'token': 'Error generando respuesta.'})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        # Flush any remaining buffer (response ended before diverging from OOS prefix)
        if buffering and buffer_tokens:
            text = "".join(buffer_tokens).strip()
            if text == _OOS:
                if self._is_professional_scope_question(question):
                    fallback, _ = self._fallback_answer(question, chunks, language)
                    yield f"data: {json.dumps({'token': fallback})}\n\n"
                    yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                else:
                    yield f"data: {json.dumps({'token': self._out_of_scope_message(language)})}\n\n"
                    yield f"data: {json.dumps({'done': True, 'needs_contact_form': True, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                return
            for bt in buffer_tokens:
                yield f"data: {json.dumps({'token': bt})}\n\n"

        yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"

    def _should_retrieve(self, question: str) -> bool:
        return bool(question.strip())

    def _retrieve(self, question: str, top_k: int, history: list[dict] | None = None) -> list[RetrievedChunk]:
        """Retrieve chunks using cosine similarity over cached embeddings."""
        if not self._cached_embeddings:
            logger.warning("No cached embeddings available")
            return [
                RetrievedChunk(
                    source="demo/doc-1",
                    chunk="No hay embeddings cacheados. Ejecuta 'python scripts/index_documents.py' primero.",
                )
            ]

        query = question.strip()
        effective_top_k = top_k

        if self._is_allowed_profile_question(question):
            effective_top_k = max(effective_top_k, 40)

        if self._is_company_question(question):
            effective_top_k = max(top_k, 35)
            query = f"{query} experiencia laboral empresas trabajo actual Data Equity Suministros Medina"

        if self._is_language_question(question):
            effective_top_k = max(effective_top_k, 35)
            query = f"{query} idiomas ingles inglés nivel language skills bilingual communication"

        if self._is_project_question(question):
            effective_top_k = max(effective_top_k, 40)
            query = (
                f"{query} proyectos portfolio chatbot rag react fastapi azure ai search openai "
                "sistema recomendacion turistica tui deep learning tensorflow "
                "power bi dashboards scoring clientes machine learning "
                "desplegado produccion docker container apps"
            )

        if self._is_education_question(question):
            effective_top_k = max(effective_top_k, 45)
            query = (
                f"{query} formacion estudios educacion calificaciones notas matricula de honor "
                "python avanzado 10 deep learning 9.75 estadistica 9.5 apache spark 9.20 "
                "tfm maxima calificacion tercera posicion competicion becas master "
                "soft skills adaptabilidad resiliencia trabajo en equipo comunicacion "
                "proyecto chatbot rag react fastapi azure ai search"
            )

        if len(query.split()) < 5 and history:
            last_user = next(
                (m["content"] for m in reversed(history) if m.get("role") == "user"), ""
            )
            last_assistant = next(
                (m["content"] for m in reversed(history) if m.get("role") == "assistant"), ""
            )
            context_hint = f"{last_user[:60]} {last_assistant[:60]}".strip()
            if context_hint:
                query = f"{query} {context_hint}"

        if len(query.split()) < 4:
            query = f"{query} perfil profesional experiencia proyectos habilidades trayectoria"

        # Generate embedding for the query using Google API (or fallback to demo if not available)
        query_embedding = self._embed_query(query)
        if query_embedding is None:
            # Fallback if embedding fails
            return [RetrievedChunk(source="demo", chunk="No hay modelo de embeddings configurado.")]

        # Compute cosine similarity between query and all cached chunks
        vector_scores: list[tuple[int, float]] = []
        for idx, cached in enumerate(self._cached_embeddings):
            similarity = self._cosine_similarity(query_embedding, cached.embedding)
            vector_scores.append((idx, similarity))
        vector_scores.sort(key=lambda x: x[1], reverse=True)

        # BM25 keyword scores
        bm25_scores: list[tuple[int, float]] = []
        if self._bm25 is not None:
            raw_bm25 = self._bm25.get_scores(query.lower().split())
            bm25_scores = sorted(enumerate(raw_bm25), key=lambda x: x[1], reverse=True)

        # Reciprocal Rank Fusion (RRF) — combine vector + BM25 rankings
        RRF_K = 60
        rrf: dict[int, float] = {}
        for rank, (idx, _) in enumerate(vector_scores):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)
        for rank, (idx, _) in enumerate(bm25_scores):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)

        ranked = sorted(rrf.items(), key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in ranked[:effective_top_k]]

        chunks: list[RetrievedChunk] = []
        for idx in top_indices:
            cached = self._cached_embeddings[idx]
            chunks.append(RetrievedChunk(source=cached.source, chunk=cached.chunk_text))

        if self._is_company_question(question):
            chunks.sort(key=lambda c: (0 if "cv_rag" in c.source.lower() else 1))

        return chunks

    def _embed_query(self, query: str) -> np.ndarray | None:
        """Embed a query string using Google API if available, else return None."""
        if not settings.google_api_key:
            logger.warning("GOOGLE_API_KEY not set, cannot embed query")
            return None

        try:
            from app.services.embedding_service import EmbeddingService
            embedder = EmbeddingService(settings.google_api_key)
            embedding = embedder.embed(query)
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return None

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def _build_messages(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[dict] | None = None,
        current_time: datetime | None = None,
        language: str = "es",
    ) -> list[dict]:
        """Build the messages list shared by streaming and non-streaming paths."""
        current_time = current_time or datetime.now(timezone.utc)
        today_date = current_time.strftime("%Y-%m-%d")
        now_utc = current_time.strftime("%Y-%m-%d %H:%M UTC")

        context_block = "\n\n".join([f"- {c.source}:\n{c.chunk}" for c in chunks])
        language_rule = (
            "Always respond in English because the user's question is in English. "
            if language == "en"
            else "Always respond in Spanish because the user's question is in Spanish. "
        )
        system_prompt = (
            "You are an AI assistant for Domingo Berbel's professional profile. "
            "Your ONLY role is to present and sell Domingo Berbel's professional profile. "
            "You are NOT a general-purpose assistant, technical support, tutor, or coder. "
            "If the user asks a generic technical question (how to install a library, fix an error, explain a concept, "
            "write code, solve math, historical facts, news, recipes, or anything not about Domingo's skills or experience), "
            "refuse politely and redirect: 'Solo puedo responder sobre el perfil profesional de Domingo Berbel. "
            "Si quieres saber si Domingo tiene experiencia con X, pregúntame.' "
            "Never answer the technical question itself, even partially. "
            "NEVER include citation markers like [1], [2], [3], (1), footnote numbers, or any bracketed/parenthesized "
            "reference tokens in your answer. Write clean prose only, with no inline source references. "
            f"Current date is {today_date} and current time reference is {now_utc}. "
            "Use this temporal reference whenever the user asks about current status, present role, recency, or timeline. "
            "If a degree or role has an end date before today, treat it as completed, NOT ongoing. "
            "IMPORTANT: Base your answers strictly on the retrieved document context below. "
            "Quote specific facts, dates, roles, companies, technologies, and achievements from the documents. "
            "Do not use generic placeholders like 'no hay informacion especifica' when there is relevant context. "
            "If context exists, provide the best precise answer from it. "
            "Do not invent facts, metrics, clients or roles that are not supported by the retrieved context. "
            "If the documents contain the answer, use that information with precision and detail. "
            "Your job is to present him in a strong, credible, recruiter-friendly and commercially compelling way. "
            "Highlight business impact, ownership, adaptability, technical breadth, delivery mindset, and value for employers. "
            "Avoid repetitive phrasing across turns: vary sentence openings and structure while keeping facts unchanged. "
            "NEVER answer personal, sexual, romantic, political, religious, or offensive questions about Domingo or anyone else. "
            "Questions about sexual orientation, relationships, physical appearance, personal life, or any non-professional topic must be rejected. "
            "CRITICAL: If the user sends a statement, exclamation, or opinion that is NOT a question about Domingo's professional profile "
            "(e.g. sports cheers, random comments, greetings to third parties, jokes, memes, off-topic remarks), "
            "reply with exactly: OUT_OF_SCOPE. Do NOT try to connect unrelated statements to Domingo's profile. "
            "Only answer if the user is genuinely asking about or can reasonably be connected to Domingo's professional value. "
            "Only provide contact information if it is one of the configured professional emails. "
            "If the question is outside professional scope OR is inappropriate/offensive, reply with exactly: OUT_OF_SCOPE. "
            "Use the conversation history to maintain coherent, contextual responses across turns. "
            "If the user refers to something discussed earlier, use the history to answer accurately. "
            + language_rule +
            "Tone: polished, persuasive, concise, confident. "
            "ANSWER LENGTH: Match the depth of your answer to the complexity of the question. "
            "Simple questions get 50-90 words. Medium questions get 100-180 words. "
            "Detailed or multi-part questions should reach 180-280 words — use the full space when the question warrants it. "
            "Never pad answers with filler, but do NOT truncate relevant detail when the question is complex. "
            "EDUCATION DEPTH: Questions about education, studies, or academic background are ALWAYS treated as medium-to-detailed "
            "(minimum 140 words). You MUST cite exact grades and distinctions from context, never vague summaries. "
            "Mandatory when available in context: Matrículas de Honor (10) in Estadística Avanzada and Investigación de Mercados; "
            "Máster grades Python Avanzado 10, Deep Learning 9.75, Estadística 9.5, Apache Spark 9.20; and the TFM máxima calificación "
            "plus tercera posición en la competición de becas del máster. "
            "For education answers, include at least 2 soft skills evidenced by trajectory (adaptabilidad, resiliencia, trabajo en equipo, "
            "comunicación, orientación a negocio) tied to real examples from context. "
            "If the user asks broadly about formation/perfil/proyectos, also explain briefly the portfolio chatbot project itself "
            "(RAG con React + FastAPI + Azure AI Search + OpenAI, desplegado en Azure) and why it demonstrates applied capability. "
            "PROJECTS: When the user asks about projects, you MUST mention the portfolio chatbot project as one of Domingo's key projects. "
            "This chatbot (the one answering the question) is itself a project built by Domingo: a full-stack RAG system "
            "with React frontend, FastAPI backend, Azure AI Search for document retrieval, OpenAI for generation, "
            "deployed on Azure Container Apps with Docker, custom domain, and HTTPS. It demonstrates end-to-end capability "
            "from architecture to production deployment. Always mention it alongside other projects like the TUI recommendation system. "
            "GRADES: When the user asks about grades, calificaciones, or notas, you MUST cite ALL of these specific grades from context: "
            "Grado: Matrícula de Honor (10) en Estadística Avanzada, Matrícula de Honor (10) en Investigación de Mercados, Estadística 9.2. "
            "Máster Data Science: Python Avanzado 10, Deep Learning 9.75, Estadística 9.5, Apache Spark 9.20. "
            "TFM con máxima calificación y tercera posición en la competición de becas del máster. "
            "Never omit available grades — list them all explicitly. "
            "STRENGTHS / PUNTOS FUERTES: When asked about Domingo's strengths, strong points, or differentiators, "
            "highlight: (1) end-to-end technical ownership from data ingestion to production deployment; "
            "(2) strong statistical and ML foundation combined with business orientation; "
            "(3) experience with RAG, LLMs, and generative AI in production on Azure; "
            "(4) fast learner with proven adaptability (Erasmus, Berlín, multiple tech stacks); "
            "(5) communication skills to present results to non-technical stakeholders. "
            "Always ground these in concrete examples from the retrieved context. "
            "RECRUITER MESSAGES: When someone sends a job offer, outreach message, or recruitment pitch, "
            "do NOT just return contact information. Instead: "
            "(1) Briefly acknowledge the opportunity positively; "
            "(2) Highlight 2-3 specific skills from the retrieved context that directly match the role described; "
            "(3) Mention that Domingo is open to opportunities and can be reached via LinkedIn or email; "
            "(4) Keep the tone professional, confident, and concise (100-150 words). "
            "Treat recruiter messages as an opportunity to sell Domingo's profile, not just redirect to contact channels."
        )

        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        for msg in (history or [])[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        prompt_label_question = "Question" if language == "en" else "Pregunta"
        prompt_label_context = "Context" if language == "en" else "Contexto"
        prompt_empty_context = "No retrieved context." if language == "en" else "Sin contexto recuperado."
        user_prompt = f"{prompt_label_question}: {question}\n\n{prompt_label_context}:\n{context_block if context_block else prompt_empty_context}"
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _generate_answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[dict] | None = None,
        current_time: datetime | None = None,
        language: str = "es",
    ) -> tuple[str, bool]:
        if not self._llm_client or not self._chat_model:
            return self._fallback_answer(question, chunks, language)

        messages = self._build_messages(question, chunks, history, current_time, language)

        response = self._llm_client.chat.completions.create(
            model=self._chat_model,
            temperature=0.05,
            max_tokens=800,
            messages=messages,
        )
        content = (response.choices[0].message.content or "").strip()
        if content == "OUT_OF_SCOPE":
            if self._is_professional_scope_question(question):
                fallback, _ = self._fallback_answer(question, chunks, language)
                return fallback, False
            return self._out_of_scope_message(language), True

        low_signal_patterns = [
            "no hay información específica en el contexto",
            "no hay informacion especifica en el contexto",
            "por favor, proporcione más detalles",
            "por favor, proporcione mas detalles",
        ]
        if chunks and any(p in content.lower() for p in low_signal_patterns):
            fallback, _ = self._fallback_answer(question, chunks, language)
            return fallback, False

        return content, False

    def _fallback_answer(self, question: str, chunks: list[RetrievedChunk], language: str = "es") -> tuple[str, bool]:
        if not chunks:
            return self._out_of_scope_message(language), True

        if self._is_occupation_question(question):
            return self._occupation_answer(language), False

        snippets: list[str] = []
        for item in chunks[:4]:
            text = " ".join(item.chunk.split())
            if not text:
                continue
            if len(text) > 240:
                text = text[:240].rsplit(" ", 1)[0] + "..."
            if text not in snippets:
                snippets.append(text)

        if snippets:
            if self._is_project_question(question):
                intro = (
                    "Based on the documentation, Domingo delivers strong business value in applied AI projects. "
                    if language == "en"
                    else "En base a la documentación, Domingo aporta valor real en proyectos de IA aplicada con impacto de negocio. "
                )
            elif self._is_education_question(question):
                intro = (
                    "Based on the documentation, his education combines strong academic rigor with practical application. "
                    if language == "en"
                    else "En base a la documentación, su formación combina base académica sólida con aplicación práctica en entornos reales. "
                )
            else:
                intro = (
                    "Based on the available documentation, this is the most precise summary for your question: "
                    if language == "en"
                    else "En base a la documentación disponible, este es el resumen más preciso para tu pregunta: "
                )
            return (intro + " ".join(snippets[:2]), False)

        if language == "en":
            return (
                "With the available information, Domingo Berbel shows a strong profile for Data Science, applied AI, "
                "and business-oriented RAG solutions. He combines technical depth, practical judgment, and a proven "
                "delivery mindset to bring AI projects into production.",
                False,
            )
        return (
            "Con la informacion disponible, Domingo Berbel presenta un perfil sólido para roles de Data Science, IA aplicada "
            "y soluciones RAG orientadas a negocio. Combina capacidad técnica, criterio práctico y foco en llevar proyectos "
            "a producción con impacto real.",
            False,
        )

    @staticmethod
    def _is_inappropriate_question(question: str) -> bool:
        """Pre-LLM filter: reject clearly inappropriate/personal/offensive questions."""
        q = question.lower().strip()
        inappropriate_patterns = [
            "gustan los hombre", "gustan los mujer", "gustan las mujer", "gustan las chica",
            "gustan los chico", "es gay", "es homosexual", "es hetero", "orientaci",
            "novia", "novio", "pareja", "casado", "soltero", "sexual",
            "relaci", "follar", "sexo", "polla", "culo", "tetas",
            "pene", "vagina", "mierda", "puta", "hijo de",
            "gilipollas", "subnormal", "idiota", "imbecil", "imbécil",
            "maric", "bollera", "travesti", "transexual",
            "gordo", "feo", "guapo", "atractivo",
            "religión", "religion", "político", "politico", "partido",
            "votar", "votó", "droga", "alcohol", "borracho",
            "raza", "racis", "matar", "morir", "suicid",
        ]
        return any(p in q for p in inappropriate_patterns)

    def _out_of_scope_message(self, language: str = "es") -> str:
        emails = self._contact_emails()
        contact_text = " / ".join(emails) if emails else "sus correos profesionales"
        linkedin = settings.professional_linkedin.strip()
        linkedin_text = f" LinkedIn: {linkedin}." if linkedin else ""
        if language == "en":
            return (
                "I can only answer questions about Domingo Berbel's professional trajectory and technical experience. "
                f"For more professional context, you can contact him at: {contact_text}.{linkedin_text}"
            )
        return (
            "Solo puedo responder sobre la trayectoria profesional de Domingo Berbel y su experiencia técnica. "
            f"Si necesitas más contexto profesional, puedes contactar por: {contact_text}.{linkedin_text}"
        )

    def _contact_emails(self) -> list[str]:
        return [x.strip() for x in settings.contact_emails.split(",") if x.strip()]

    def _is_contact_question(self, question: str) -> bool:
        """Only intercept short, explicit requests for contact info.
        Long messages (>120 chars) go to the LLM so it can pitch Domingo AND provide contact info."""
        q = question.lower().strip()

        # Long messages (recruiter pitches, job offers, detailed questions) go to RAG
        if len(question.strip()) > 120:
            return False

        explicit_patterns = [
            "cómo contacto", "como contacto",
            "cómo puedo contactar", "como puedo contactar",
            "cómo le contacto", "como le contacto",
            "dónde contactar", "donde contactar",
            "información de contacto", "datos de contacto",
            "cómo me pongo en contacto", "como me pongo en contacto",
            "how to contact", "how can i contact", "how do i contact",
            "contact information", "contact details",
            "reach domingo", "get in touch",
            "email de domingo", "correo de domingo",
            "linkedin de domingo",
        ]
        return any(p in q for p in explicit_patterns)

    def _is_greeting_question(self, question: str) -> bool:
        q = question.strip().lower().rstrip("!.?¿¡,")
        greetings = [
            "hola",
            "buenas",
            "buenas tardes",
            "buenos dias",
            "buenos días",
            "buenas noches",
            "hello",
            "hi",
            "hey",
        ]
        return q in greetings

    def _greeting_answer(self, language: str = "es") -> str:
        if language == "en":
            return (
                "Hi, I'm Domingo Berbel's assistant. "
                "I can answer questions about his qualifications, experience, projects, and professional trajectory."
            )
        return (
            "Hola, soy el asistente de Domingo Berbel. "
            "Puedo responder cualquier pregunta sobre su cualificación, experiencia, proyectos y trayectoria profesional."
        )

    def _contact_answer(self, language: str = "es") -> str:
        emails = self._contact_emails()
        linkedin = settings.professional_linkedin.strip()
        lines: list[str] = (
            ["You can contact Domingo Berbel through these professional channels:"]
            if language == "en"
            else ["Puedes contactar con Domingo Berbel por estos canales profesionales:"]
        )
        if linkedin:
            lines.append(f"- LinkedIn: {linkedin}")
        if emails:
            lines.append("- Email: " + " / ".join(emails))
        if len(lines) == 1:
            lines.append(
                "- There is currently no configured contact channel."
                if language == "en"
                else "- Actualmente no hay un canal de contacto configurado."
            )
        return "\n".join(lines)

    @staticmethod
    def _normalize_question(question: str) -> str:
        q = question.lower().strip()
        # Common typo variants from real traffic.
        q = q.replace("ha que", "a que")
        q = q.replace("ha qué", "a qué")
        return q

    def _is_occupation_question(self, question: str) -> bool:
        q = self._normalize_question(question)
        keywords = [
            "a que se dedica",
            "a qué se dedica",
            "en que se dedica",
            "en qué se dedica",
            "se dedica domingo",
            "a que se dedica domingo",
            "a qué se dedica domingo",
            "en que trabaja",
            "en qué trabaja",
            "donde trabaja",
            "dónde trabaja",
            "trabaja domingo",
            "que trabajo tiene",
            "qué trabajo tiene",
        ]
        return any(k in q for k in keywords)

    def _occupation_answer(self, language: str = "es") -> str:
        if language == "en":
            return (
                "Domingo Berbel is a Data Scientist specialized in applying data science and AI to real business problems. "
                "He combines statistical rigor, commercial mindset, and end-to-end technical execution: from data ingestion and "
                "modeling to production deployment, including RAG systems on Azure."
            )
        return (
            "Domingo Berbel es Data Scientist especializado en aplicar ciencia de datos e IA a problemas reales de negocio. "
            "Combina base estadística, visión comercial y ejecución técnica end-to-end: desde ingesta y modelado hasta despliegue "
            "de soluciones en producción, incluyendo sistemas RAG sobre Azure."
        )

    def _detect_user_language(self, question: str, history: list[dict] | None = None) -> str:
        text = question.lower().strip()
        if not text and history:
            last_user = next((m.get("content", "") for m in reversed(history) if m.get("role") == "user"), "")
            text = last_user.lower().strip()

        normalized = text.replace("'", "").replace("?", " ").replace("!", " ").strip()

        # Explicit short English intents that were misclassified in production logs.
        if normalized in {"hello", "hi", "hey"}:
            return "en"
        if normalized.startswith(("whats ", "what is ", "what's ", "who is ", "where is ", "how is ")):
            return "en"

        if any(ch in text for ch in ("¿", "¡", "ñ", "á", "é", "í", "ó", "ú")):
            return "es"

        english_markers = {
            "what", "which", "where", "when", "why", "how", "who", "your", "you", "are", "is", "do", "does",
            "experience", "projects", "skills", "education", "career", "background", "currently", "work", "worked",
            "english", "speak", "tell", "about", "hello", "hi", "hey", "whats", "job", "role", "current",
        }
        spanish_markers = {
            "que", "qué", "donde", "dónde", "cuando", "cuándo", "como", "cómo", "quien", "quién", "trabaja",
            "experiencia", "proyectos", "habilidades", "formacion", "formación", "trayectoria", "actualmente",
            "idiomas", "habla", "sobre",
        }

        tokens = re.findall(r"[a-zA-Z]+", text)
        if not tokens:
            return "es"

        en_score = sum(1 for t in tokens if t in english_markers)
        es_score = sum(1 for t in tokens if t in spanish_markers)
        if en_score > es_score:
            return "en"
        return "es"

    def _is_professional_scope_question(self, question: str) -> bool:
        q = self._normalize_question(question)
        keywords = [
            "trabaja",
            "trabajo",
            "empresa",
            "puesto",
            "experiencia",
            "proyecto",
            "habilidad",
            "habilidades",
            "tecnologia",
            "tecnologías",
            "estudios",
            "formacion",
            "formación",
            "academica",
            "académica",
            "trayectoria",
            "laboral",
            "profesional",
            "donde ha trabajado",
            "dónde ha trabajado",
            "ha trabajado",
            "trabajado",
            "experiencia laboral",
            "candidato",
            "recruiter",
            "headhunter",
            "head hunters",
            "encaje",
            "fit",
            "aportar valor",
            "valor aporta",
            "logros",
            "puntos fuertes",
            "puntos debiles",
            "puntos débiles",
            "fortalezas",
            "debilidades",
            "cualidades",
            "caracteristicas",
            "características",
            "virtudes",
            "valor que aporta",
            "puede aportar",
            "aportaria",
            "aportaría",
            "buen candidato",
            "encaja",
            "adecuado",
            "strengths",
            "weaknesses",
            "value",
            "assets",
            "se diferencia",
            "diferenciador",
            "destacable",
            "destacar",
            "lo mejor de",
            "domingo berbel",
            "data scientist",
            "inglés",
            "ingles",
            "idioma",
            "idiomas",
            "habla",
            "nivel",
            "a que se dedica",
            "a qué se dedica",
            "se dedica",
            "dedica",
            # Skill / knowledge inquiry verbs
            "sabe",
            "conoce",
            "maneja",
            "domina",
            "utiliza",
            "ha usado",
            "ha utilizado",
            "trabaja con",
            "ha trabajado con",
            # Professional profile nouns
            "conocimientos",
            "competencias",
            "aptitudes",
            "capacidades",
            "herramientas",
            "tools",
            "stack",
            "tech stack",
            "skills",
            "certificacion",
            "certificaciones",
            "certificación",
            "curriculum",
            "cv",
            "perfil",
            "portafolio",
            "portfolio",
        ]
        return any(k in q for k in keywords)

    def _is_allowed_profile_question(self, question: str) -> bool:
        q = self._normalize_question(question)

        if "domingo" not in q and "he" not in q and "his" not in q and "su" not in q:
            # Allow direct professional-profile category questions even without explicit name.
            category_triggers = [
                "trayectoria",
                "experiencia",
                "formacion",
                "formación",
                "estudios",
                "academica",
                "académica",
                "laboral",
                "donde ha trabajado",
                "dónde ha trabajado",
                "ha trabajado",
                "trabajado",
                "experiencia laboral",
                "proyectos",
                "project",
                "projects",
                "idiomas",
                "idioma",
                "ingles",
                "inglés",
                "candidato",
                "recruiter",
                "headhunter",
                "head hunters",
                "a que se dedica",
                "a qué se dedica",
                "en que trabaja",
                "en qué trabaja",
                # Skill / knowledge inquiry verbs
                "sabe",
                "conoce",
                "maneja",
                "domina",
                "utiliza",
                "ha usado",
                "ha utilizado",
                "trabaja con",
                "ha trabajado con",
                # Professional profile nouns
                "conocimientos",
                "competencias",
                "aptitudes",
                "capacidades",
                "herramientas",
                "tools",
                "stack",
                "tech stack",
                "skills",
                "certificacion",
                "certificaciones",
                "certificación",
                "curriculum",
                "cv",
                "perfil",
                "portafolio",
                "portfolio",
                "habilidad",
                "habilidades",
                "tecnologia",
                "tecnologías",
                "puntos fuertes",
                "puntos debiles",
                "puntos débiles",
                "fortalezas",
                "debilidades",
                "cualidades",
                "caracteristicas",
                "características",
                "virtudes",
                "valor que aporta",
                "puede aportar",
                "buen candidato",
                "encaja",
                "adecuado",
                "strengths",
                "weaknesses",
                "se diferencia",
                "lo mejor de",
            ]
            if not any(t in q for t in category_triggers):
                return False

        return self._is_professional_scope_question(question)

    def _is_generic_technical_help_question(self, question: str) -> bool:
        q = self._normalize_question(question)

        if self._is_professional_scope_question(q):
            return False

        if any(ref in q for ref in ["domingo", "domingo berbel", "su perfil", "his profile", "su experiencia", "his experience"]):
            return False

        command_patterns = [
            r"\bpip\s+install\b",
            r"\bpython\s+-m\s+pip\b",
            r"\bconda\s+install\b",
            r"\bpoetry\s+add\b",
            r"\bnpm\s+install\b",
            r"\byarn\s+add\b",
        ]
        help_patterns = [
            r"\bcomo\s+instal[oa]r?\b",
            r"\bc[oó]mo\s+instal[oa]r?\b",
            r"\bhow\s+do\s+i\s+install\b",
            r"\bhow\s+to\s+install\b",
            r"\binstall\b.*\bvenv\b",
            r"\binstalar\b.*\bvenv\b",
            r"\bvirtualenv\b",
            r"\bvenv\b",
            r"\brequirements\.txt\b",
        ]

        return any(re.search(pattern, q) for pattern in command_patterns + help_patterns)

    def _is_clearly_offtopic_question(self, question: str) -> bool:
        q = self._normalize_question(question)
        if self._is_professional_scope_question(q):
            return False

        historical_patterns = [
            "que ocurrio",
            "qué ocurrió",
            "guerra civil",
            "segunda guerra mundial",
            "primera guerra mundial",
            "franquismo",
            "dictadura",
            "historia de",
        ]
        if any(p in q for p in historical_patterns):
            return True

        if re.search(r"\b(1[6-9]\d{2}|20\d{2})\b", q):
            return True

        return False

    def _is_company_question(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "empresa",
            "empresas",
            "trabaja",
            "trabajado",
            "trabajo actual",
            "donde trabaja",
            "dónde trabaja",
            "puesto",
            "empleo",
            "laboral",
        ]
        return any(k in q for k in keywords)

    def _is_language_question(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "inglés",
            "ingles",
            "idioma",
            "idiomas",
            "habla inglés",
            "habla ingles",
            "language",
            "languages",
            "nivel de inglés",
            "nivel ingles",
            "bilingüe",
            "bilingue",
        ]
        return any(k in q for k in keywords)

    def _is_education_question(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "formacion",
            "formación",
            "educacion",
            "educación",
            "estudios",
            "academico",
            "académico",
            "calificaciones",
            "notas",
            "grado",
            "master",
            "máster",
            "universidad",
            "tfm",
            "donde estudio",
            "dónde estudió",
            "donde estudió",
        ]
        return any(k in q for k in keywords)

    def _is_recruiter_message(self, question: str) -> bool:
        """Detect when a recruiter/headhunter is sending a job offer or outreach message."""
        q = question.lower()
        recruiter_signals = [
            "te contacto porque",
            "me pongo en contacto",
            "me dirijo a ti",
            "he visto tu experiencia",
            "he visto tu perfil",
            "he visto tu trayectoria",
            "creo que podrías encajar",
            "podrias encajar",
            "nuevo proyecto",
            "nueva oportunidad",
            "oportunidad laboral",
            "oferta de trabajo",
            "oferta laboral",
            "rol enfocado",
            "posicion de",
            "posición de",
            "buscamos alguien",
            "buscamos a alguien",
            "estamos buscando",
            "senior consultant",
            "it business solutions",
            "connecting professionals",
            "tenemos una llamada",
            "comparte tu cv",
            "comparte conmigo tu cv",
            "i'm reaching out",
            "i am reaching out",
            "i wanted to reach out",
            "new opportunity",
            "job opportunity",
            "great fit",
            "you could be a great fit",
        ]
        return any(p in q for p in recruiter_signals)

    def _is_project_question(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "proyecto",
            "proyectos",
            "project",
            "projects",
            "portfolio",
            "chatbot",
            "ha construido",
            "ha desarrollado",
            "que ha hecho",
            "qué ha hecho",
        ]
        return any(k in q for k in keywords)

    def _language_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        q = question.lower()

        if "como" in q and ("aprendi" in q or "aprendio" in q or "aprendió" in q):
            return (
                "Domingo ha reforzado su inglés a través de su experiencia internacional, "
                "trabajando y adaptándose a entornos multiculturales en distintos países y ciudades."
            )

        if "nivel" in q:
            return (
                "Domingo habla español como idioma nativo y se desenvuelve en inglés en contextos profesionales "
                "internacionales, según refleja su trayectoria internacional."
            )

        if "idiomas" in q or "idioma" in q:
            return (
                "Domingo habla español como idioma nativo, y habla inglés como refleja su experiencia internacional."
            )

        return (
            "Domingo habla español como idioma nativo y utiliza inglés en contextos profesionales, "
            "como refleja su experiencia internacional."
        )

    def _build_llm_client(self) -> AzureOpenAI | OpenAI | None:
        if settings.openai_api_key:
            return OpenAI(api_key=settings.openai_api_key)

        required = [
            settings.azure_openai_endpoint,
            settings.azure_openai_api_key,
            settings.azure_openai_api_version,
        ]
        if not all(required):
            return None

        return AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    def _build_chat_model(self) -> str | None:
        if settings.openai_api_key and settings.openai_model:
            return settings.openai_model

        return settings.azure_openai_chat_deployment
