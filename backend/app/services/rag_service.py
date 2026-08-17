"""Orchestration for the profile assistant.

This module used to be ~1,200 lines and did everything: seven keyword predicates
with ~400 lines of Spanish substring lists, query expansion, retrieval, prompt
construction with the facts baked in, generation, and streaming. It is now the
thin layer that owns the `ChatResponse` contract and the SSE wire format, so
`api/chat.py` and the frontend are unaffected by the rewrite underneath.

Retrieval lives in `retrieval.py`, the tool loop in `agent.py`, and the
fabricated-entity check in `grounding.py`.

What is deliberately kept: the pre-LLM safety filter, the `OUT_OF_SCOPE`
contract that drives `needs_contact_form`, the contact fast-path, and the
language detection that lets a Spanish visitor get a Spanish answer from an
English corpus.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from openai import OpenAI

from app.config import settings
from app.models import ChatResponse, Citation
from app.services.agent import AgentLimits, ProfileAgent
from app.services.retrieval import RetrievalIndex

logger = logging.getLogger(__name__)


class AgenticRAGService:
    """Shared index across requests; one agent per request."""

    _index: RetrievalIndex | None = None

    def __init__(self) -> None:
        self._client = self._build_client()
        self._model = settings.openai_model
        self._embedder_service = None

    # --- startup ------------------------------------------------------------

    @classmethod
    def initialize_cache(
        cls,
        cache_path: str | None = None,
        vocabulary_path: str | None = None,
    ) -> None:
        """Load the index at application startup (FastAPI lifespan).

        Falls back to the previous cache if the primary one is missing or
        unreadable, so publishing a bad index degrades retrieval rather than
        taking the service offline.
        """
        primary = Path(cache_path or settings.embeddings_cache_path)

        vocabulary = Path(vocabulary_path or settings.vocabulary_path)
        if not vocabulary.exists() and not vocabulary_path:
            # Container layout puts it beside the app; a checkout puts it under
            # data/kb/. Try both rather than silently losing grounding.
            fallback = Path(settings.vocabulary_path_fallback)
            if fallback.exists():
                vocabulary = fallback

        index = RetrievalIndex.load(primary, vocabulary)
        if index.is_empty:
            fallback = Path(settings.embeddings_cache_fallback)
            if fallback.exists():
                logger.warning("Primary index unusable; falling back to %s", fallback)
                index = RetrievalIndex.load(fallback, vocabulary)

        cls._index = index
        if index.is_empty:
            logger.error("Index is empty — the assistant cannot ground its answers")
        else:
            logger.info(
                "Index ready: %d documents, %d vocabulary terms, embedding model=%s",
                len(index),
                len(index.vocabulary),
                index.model,
            )

    @classmethod
    def _get_index(cls) -> RetrievalIndex:
        if cls._index is None:
            cls.initialize_cache()
        return cls._index  # type: ignore[return-value]

    # --- clients ------------------------------------------------------------

    @staticmethod
    def _build_client() -> OpenAI | None:
        """Direct OpenAI only.

        The AzureOpenAI branch that used to be here was unreachable — the API key
        took precedence — and pointed at a resource that no longer exists in the
        subscription.
        """
        if settings.openai_api_key:
            return OpenAI(api_key=settings.openai_api_key)
        logger.error("OPENAI_API_KEY is not set; the assistant cannot generate answers")
        return None

    def _embed_query(self, text: str) -> np.ndarray | None:
        """Embed a query, returning None so retrieval degrades to BM25 on failure."""
        if not settings.google_api_key:
            return None
        try:
            if self._embedder_service is None:
                from app.services.embedding_service import EmbeddingService

                self._embedder_service = EmbeddingService(
                    settings.google_api_key, settings.embedding_model
                )
            return np.asarray(self._embedder_service.embed_query(text), dtype=np.float32)
        except Exception as exc:
            logger.warning("Query embedding failed (%s); falling back to keyword search", exc)
            return None

    def _build_agent(self) -> ProfileAgent:
        return ProfileAgent(
            client=self._client,
            model=self._model,
            index=self._get_index(),
            embedder=self._embed_query,
            limits=AgentLimits(
                max_iterations=settings.agent_max_iterations,
                max_tool_calls=settings.agent_max_tool_calls,
                max_documents=settings.agent_max_documents,
                search_top_k=settings.retrieval_top_k,
            ),
        )

    # --- public API ---------------------------------------------------------

    def ask(
        self,
        question: str,
        top_k: int = 6,
        history: list[dict] | None = None,
        current_time: datetime | None = None,
    ) -> ChatResponse:
        history = history or []
        now = current_time or datetime.now(timezone.utc)
        language = detect_language(question, history)
        logger.info("[ASK] q=%r lang=%s turns=%d", question[:120], language, len(history))

        fast_path = self._fast_path(question, language)
        if fast_path is not None:
            return fast_path

        if self._client is None:
            return self._response(self._unavailable_message(language), [], needs_contact=False)

        result = self._build_agent().answer(question, history, language, now)
        if result.out_of_scope:
            logger.info("[ASK] out_of_scope")
            return self._response(out_of_scope_message(language), [], needs_contact=True)

        logger.info(
            "[ASK] documents=%s regenerated=%s",
            [d.id for d in result.documents],
            result.regenerated,
        )
        return self._response(result.answer, result.documents, needs_contact=False)

    def ask_stream(
        self,
        question: str,
        top_k: int = 6,
        history: list[dict] | None = None,
        current_time: datetime | None = None,
    ) -> Generator[str, None, None]:
        """Yield SSE frames. The wire format is what Chat.jsx parses; do not change it."""
        history = history or []
        now = current_time or datetime.now(timezone.utc)
        language = detect_language(question, history)

        fast_path = self._fast_path(question, language)
        if fast_path is not None:
            yield _sse_token(fast_path.answer)
            yield _sse_done(fast_path.needs_contact_form)
            return

        if self._client is None:
            yield _sse_token(self._unavailable_message(language))
            yield _sse_done(False)
            return

        try:
            result = self._build_agent().answer(question, history, language, now)
        except Exception as exc:
            logger.error("[STREAM] agent failed: %s", exc, exc_info=True)
            yield _sse_token(self._unavailable_message(language))
            yield _sse_done(False)
            return

        if result.out_of_scope:
            yield _sse_token(out_of_scope_message(language))
            yield _sse_done(True)
            return

        logger.info(
            "[STREAM] documents=%s regenerated=%s",
            [d.id for d in result.documents],
            result.regenerated,
        )
        for piece in _chunk(result.answer):
            yield _sse_token(piece)
        yield _sse_done(False)

    # --- fast paths ---------------------------------------------------------

    def _fast_path(self, question: str, language: str) -> ChatResponse | None:
        """Answers that need no model call, and the one safety filter kept pre-LLM."""
        if is_greeting(question):
            return self._response(greeting_message(language), [], needs_contact=False)
        if is_contact_request(question):
            return self._response(self._contact_message(language), [], needs_contact=False)
        if is_inappropriate(question):
            logger.info("[FILTER] inappropriate q=%r", question[:120])
            return self._response(out_of_scope_message(language), [], needs_contact=True)
        return None

    # --- response assembly --------------------------------------------------

    def _response(self, answer: str, documents, needs_contact: bool) -> ChatResponse:
        citations = (
            [Citation(source=d.id, chunk=d.text) for d in documents]
            if settings.show_citations
            else []
        )
        return ChatResponse(
            answer=answer,
            used_retrieval=bool(documents),
            citations=citations,
            needs_contact_form=needs_contact,
            contact_emails=contact_emails(),
            contact_linkedin=settings.professional_linkedin or None,
        )

    def _contact_message(self, language: str) -> str:
        lines = (
            ["You can reach Domingo Berbel through these professional channels:"]
            if language == "en"
            else ["Puedes contactar con Domingo Berbel por estos canales profesionales:"]
        )
        linkedin = (settings.professional_linkedin or "").strip()
        if linkedin:
            lines.append(f"- LinkedIn: {linkedin}")
        emails = contact_emails()
        if emails:
            lines.append("- Email: " + " / ".join(emails))
        return "\n".join(lines)

    @staticmethod
    def _unavailable_message(language: str) -> str:
        return (
            "The assistant is temporarily unavailable. Please try again in a moment."
            if language == "en"
            else "El asistente no está disponible temporalmente. Inténtalo de nuevo en un momento."
        )


# ── SSE helpers ─────────────────────────────────────────────────────────────


def _sse_token(text: str) -> str:
    return f"data: {json.dumps({'token': text})}\n\n"


def _sse_done(needs_contact: bool) -> str:
    payload = {
        "done": True,
        "needs_contact_form": needs_contact,
        "contact_emails": contact_emails(),
        "contact_linkedin": settings.professional_linkedin or None,
    }
    return f"data: {json.dumps(payload)}\n\n"


def _chunk(text: str, size: int = 24) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


# ── module-level helpers (pure, so they are testable) ───────────────────────


def contact_emails() -> list[str]:
    return [x.strip() for x in settings.contact_emails.split(",") if x.strip()]


def out_of_scope_message(language: str = "es") -> str:
    emails = contact_emails()
    contact = " / ".join(emails) if emails else ""
    linkedin = (settings.professional_linkedin or "").strip()
    if language == "en":
        text = "I can only answer questions about Domingo Berbel's professional background."
        if contact:
            text += f" For anything else, you can contact him at: {contact}."
    else:
        text = "Solo puedo responder sobre la trayectoria profesional de Domingo Berbel."
        if contact:
            text += f" Para otros temas, puedes contactar con él en: {contact}."
    if linkedin:
        text += f" LinkedIn: {linkedin}"
    return text


def greeting_message(language: str = "es") -> str:
    if language == "en":
        return (
            "Hi, I'm Domingo Berbel's assistant. Ask me about his experience, projects, "
            "education or how he might fit a role."
        )
    return (
        "Hola, soy el asistente de Domingo Berbel. Pregúntame por su experiencia, proyectos, "
        "formación o su encaje en un puesto."
    )


_GREETINGS = frozenset(
    {"hola", "buenas", "buenas tardes", "buenos dias", "buenos días", "buenas noches",
     "hello", "hi", "hey", "good morning", "good afternoon", "good evening"}
)


def is_greeting(question: str) -> bool:
    return question.strip().lower().rstrip("!.?¿¡,") in _GREETINGS


_CONTACT_PATTERNS = (
    "cómo contacto", "como contacto", "cómo puedo contactar", "como puedo contactar",
    "cómo le contacto", "como le contacto", "dónde contactar", "donde contactar",
    "información de contacto", "datos de contacto", "cómo me pongo en contacto",
    "como me pongo en contacto", "how to contact", "how can i contact",
    "how do i contact", "contact information", "contact details", "get in touch",
    "email de domingo", "correo de domingo", "linkedin de domingo",
)


def is_contact_request(question: str) -> bool:
    """Only short, explicit requests. A long recruiter pitch should reach the model
    so it can sell the profile rather than just returning an address."""
    if len(question.strip()) > 120:
        return False
    q = question.lower()
    return any(p in q for p in _CONTACT_PATTERNS)


# The one keyword list that survives, because it is a safety filter that must run
# before any model call rather than a routing heuristic.
_INAPPROPRIATE = (
    "gustan los hombre", "gustan los mujer", "gustan las mujer", "gustan las chica",
    "gustan los chico", "es gay", "es homosexual", "es hetero", "orientaci",
    "novia", "novio", "pareja", "casado", "soltero", "sexual", "follar", "sexo",
    "polla", "culo", "tetas", "pene", "vagina", "mierda", "puta", "hijo de",
    "gilipollas", "subnormal", "idiota", "imbecil", "imbécil", "maric", "bollera",
    "travesti", "transexual", "gordo", "feo", "guapo", "atractivo", "droga",
    "borracho", "racis", "suicid",
)


def is_inappropriate(question: str) -> bool:
    q = question.lower().strip()
    return any(p in q for p in _INAPPROPRIATE)


_ENGLISH_MARKERS = frozenset(
    {"what", "which", "where", "when", "why", "how", "who", "your", "you", "are", "is",
     "do", "does", "experience", "projects", "skills", "education", "career",
     "background", "currently", "work", "worked", "english", "speak", "tell", "about",
     "hello", "hi", "hey", "whats", "job", "role", "current", "the", "and", "his", "he"}
)
_SPANISH_MARKERS = frozenset(
    {"que", "qué", "donde", "dónde", "cuando", "cuándo", "como", "cómo", "quien",
     "quién", "trabaja", "experiencia", "proyectos", "habilidades", "formacion",
     "formación", "trayectoria", "actualmente", "idiomas", "habla", "sobre", "su",
     "es", "de", "en", "para", "cual", "cuál", "tiene", "sabe"}
)


def detect_language(question: str, history: list[dict] | None = None) -> str:
    """Pick the answer language from the question.

    The corpus is English; the assistant answers in whatever the visitor wrote,
    so a Spanish recruiter is not forced into English.
    """
    text = question.lower().strip()
    if not text and history:
        text = next(
            (m.get("content", "") for m in reversed(history) if m.get("role") == "user"), ""
        ).lower()

    normalized = text.replace("'", "").replace("?", " ").replace("!", " ").strip()
    if normalized in {"hello", "hi", "hey"}:
        return "en"
    if normalized.startswith(("whats ", "what is ", "what's ", "who is ", "where is ", "how is ")):
        return "en"

    # Spanish-only orthography is decisive.
    if any(ch in text for ch in ("¿", "¡", "ñ", "á", "é", "í", "ó", "ú")):
        return "es"

    tokens = re.findall(r"[a-zA-Z]+", text)
    if not tokens:
        return "es"
    english = sum(1 for t in tokens if t in _ENGLISH_MARKERS)
    spanish = sum(1 for t in tokens if t in _SPANISH_MARKERS)
    return "en" if english > spanish else "es"
