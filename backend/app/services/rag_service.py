from __future__ import annotations

import json
import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI, OpenAI

from app.config import settings
from app.models import ChatResponse, Citation

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    source: str
    chunk: str


class AgenticRAGService:
    def __init__(self) -> None:
        self._search_client = self._build_search_client()
        self._llm_client = self._build_llm_client()
        self._chat_model = self._build_chat_model()

    def ask(self, question: str, top_k: int = 13, history: list[dict] | None = None) -> ChatResponse:
        history = history or []
        logger.info("[ASK] Q=%r  history_turns=%d", question[:120], len(history))

        if self._is_greeting_question(question):
            answer = self._greeting_answer()
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
            answer = self._contact_answer()
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
            answer = self._out_of_scope_message()
            logger.info("[ANSWER] inappropriate_filter=True Q=%r", question[:120])
            return ChatResponse(
                answer=answer,
                used_retrieval=False,
                citations=[],
                needs_contact_form=True,
                contact_emails=self._contact_emails(),
                contact_linkedin=settings.professional_linkedin or None,
            )

        use_retrieval = self._should_retrieve(question)
        chunks = self._retrieve(question, top_k, history) if use_retrieval else []
        logger.info("[RETRIEVE] chunks=%d sources=%s", len(chunks), [c.source for c in chunks])
        answer, out_of_scope = self._generate_answer(question, chunks, history)
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

    def ask_stream(self, question: str, top_k: int = 13, history: list[dict] | None = None) -> Generator[str, None, None]:
        """Yield SSE-formatted chunks for streaming responses."""
        history = history or []

        # Fast-path intents (no LLM needed)
        for fast_check, fast_fn in [
            (self._is_greeting_question, self._greeting_answer),
            (self._is_contact_question, self._contact_answer),
        ]:
            if fast_check(question):
                answer = fast_fn()
                yield f"data: {json.dumps({'token': answer})}\n\n"
                yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                return

        if self._is_inappropriate_question(question):
            answer = self._out_of_scope_message()
            yield f"data: {json.dumps({'token': answer})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': True, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        use_retrieval = self._should_retrieve(question)
        chunks = self._retrieve(question, top_k, history) if use_retrieval else []

        if not self._llm_client or not self._chat_model:
            fallback, out_of_scope = self._fallback_answer(question, chunks)
            yield f"data: {json.dumps({'token': fallback})}\n\n"
            yield f"data: {json.dumps({'done': True, 'needs_contact_form': out_of_scope, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
            return

        messages = self._build_messages(question, chunks, history)
        collected = []
        _OOS = "OUT_OF_SCOPE"
        buffering = True  # hold tokens while they could still spell OUT_OF_SCOPE
        buffer_tokens: list[str] = []
        try:
            stream = self._llm_client.chat.completions.create(
                model=self._chat_model,
                temperature=0.15,
                max_tokens=350,
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
                                fallback, _ = self._fallback_answer(question, chunks)
                                yield f"data: {json.dumps({'token': fallback})}\n\n"
                                yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                            else:
                                yield f"data: {json.dumps({'token': self._out_of_scope_message()})}\n\n"
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
                    fallback, _ = self._fallback_answer(question, chunks)
                    yield f"data: {json.dumps({'token': fallback})}\n\n"
                    yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                else:
                    yield f"data: {json.dumps({'token': self._out_of_scope_message()})}\n\n"
                    yield f"data: {json.dumps({'done': True, 'needs_contact_form': True, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"
                return
            for bt in buffer_tokens:
                yield f"data: {json.dumps({'token': bt})}\n\n"

        yield f"data: {json.dumps({'done': True, 'needs_contact_form': False, 'contact_emails': self._contact_emails(), 'contact_linkedin': settings.professional_linkedin or None})}\n\n"

    def _should_retrieve(self, question: str) -> bool:
        return bool(question.strip())

    def _retrieve(self, question: str, top_k: int, history: list[dict] | None = None) -> list[RetrievedChunk]:
        if not self._search_client:
            return [
                RetrievedChunk(
                    source="demo/doc-1",
                    chunk="No hay Azure AI Search configurado. Este es un contexto de ejemplo para pruebas locales.",
                )
            ]

        query = question.strip()
        effective_top_k = top_k

        if self._is_company_question(question):
            # Company/work questions need deeper retrieval because the relevant
            # employment chunks can rank below generic profile summaries.
            effective_top_k = max(top_k, 13)
            query = f"{query} experiencia laboral empresas trabajo actual Data Equity Suministros Medina"

        if self._is_language_question(question):
            effective_top_k = max(effective_top_k, 13)
            query = f"{query} idiomas ingles inglés nivel language skills bilingual communication"

        # For very short or anaphoric follow-up questions, enrich the search query
        # with relevant terms from the most recent history turn so Azure Search
        # can retrieve meaningful chunks even when the question uses pronouns or
        # vague references like "eso", "eso mismo", "más detalles", etc.
        if len(query.split()) < 5 and history:
            # Grab the last user message from history as additional context
            last_user = next(
                (m["content"] for m in reversed(history) if m.get("role") == "user"), ""
            )
            last_assistant = next(
                (m["content"] for m in reversed(history) if m.get("role") == "assistant"), ""
            )
            # Append key nouns from the prior exchange (first 60 chars keeps it focused)
            context_hint = f"{last_user[:60]} {last_assistant[:60]}".strip()
            if context_hint:
                query = f"{query} {context_hint}"

        # Fallback enrichment for very generic short queries with no history
        if len(query.split()) < 4:
            query = f"{query} perfil profesional experiencia proyectos habilidades trayectoria"

        results = self._search_client.search(search_text=query, top=effective_top_k)
        chunks: list[RetrievedChunk] = []
        for item in results:
            payload = self._map_result(item)
            if payload:
                chunks.append(payload)

        if self._is_company_question(question):
            # Prioritize CV chunks for employment-specific questions.
            chunks.sort(key=lambda c: (0 if "cv_rag" in c.source.lower() else 1))

        return chunks

    def _build_messages(self, question: str, chunks: list[RetrievedChunk], history: list[dict] | None = None) -> list[dict]:
        """Build the messages list shared by streaming and non-streaming paths."""
        from datetime import date as _date
        today_str = _date.today().strftime("%B %Y")  # e.g. "March 2026"

        context_block = "\n\n".join([f"[{i+1}] {c.source}: {c.chunk}" for i, c in enumerate(chunks)])
        system_prompt = (
            "You are an AI assistant for Domingo Berbel's professional profile. "
            f"Today's date is {today_str}. Use this to determine what is current vs. past. "
            "If a degree or role has an end date before today, treat it as completed, NOT ongoing. "
            "IMPORTANT: Base your answers strictly on the retrieved document context below. "
            "Quote specific facts, dates, roles, companies, technologies, and achievements from the documents. "
            "Do not invent facts, metrics, clients or roles that are not supported by the retrieved context. "
            "If the documents contain the answer, use that information with precision and detail. "
            "You must only answer about his professional trajectory, achievements, projects, skills, education, and ability "
            "to deliver AI and RAG systems in production, especially on Azure. "
            "Your job is to present him in a strong, credible, recruiter-friendly and commercially compelling way. "
            "Highlight business impact, ownership, adaptability, technical breadth, delivery mindset, and value for employers. "
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
            "You can answer in Spanish or English depending on the user language. "
            "Tone: polished, persuasive, concise, confident. "
            "ANSWER LENGTH: Match the depth of your answer to the complexity of the question. "
            "Simple questions get 40-80 words. Medium questions get 80-150 words. "
            "Only detailed or multi-part questions should reach 150-200 words. Never pad answers with filler."
        )

        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        for msg in (history or [])[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        user_prompt = f"Pregunta: {question}\n\nContexto:\n{context_block if context_block else 'Sin contexto recuperado.'}"
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _generate_answer(self, question: str, chunks: list[RetrievedChunk], history: list[dict] | None = None) -> tuple[str, bool]:
        if not self._llm_client or not self._chat_model:
            return self._fallback_answer(question, chunks)

        messages = self._build_messages(question, chunks, history)

        response = self._llm_client.chat.completions.create(
            model=self._chat_model,
            temperature=0.15,
            max_tokens=350,
            messages=messages,
        )
        content = (response.choices[0].message.content or "").strip()
        if content == "OUT_OF_SCOPE":
            # Guardrail: avoid false negatives for clearly professional questions.
            if self._is_professional_scope_question(question):
                fallback, _ = self._fallback_answer(question, chunks)
                return fallback, False
            return self._out_of_scope_message(), True
        return content, False

    def _fallback_answer(self, question: str, chunks: list[RetrievedChunk]) -> tuple[str, bool]:
        if not chunks:
            return self._out_of_scope_message(), True

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

    def _out_of_scope_message(self) -> str:
        emails = self._contact_emails()
        contact_text = " / ".join(emails) if emails else "sus correos profesionales"
        linkedin = settings.professional_linkedin.strip()
        linkedin_text = f" LinkedIn: {linkedin}." if linkedin else ""
        return (
            "Solo puedo responder sobre la trayectoria profesional de Domingo Berbel y su experiencia técnica. "
            f"Si necesitas más contexto profesional, puedes contactar por: {contact_text}.{linkedin_text}"
        )

    def _contact_emails(self) -> list[str]:
        return [x.strip() for x in settings.contact_emails.split(",") if x.strip()]

    def _is_contact_question(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "contact", "contacto", "contactar", "escribir", "email", "correo", "mail", "linkedin", "hablar con",
        ]
        return any(k in q for k in keywords)

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
        # Only match pure greetings — not "hola que estudio domingo"
        return q in greetings

    def _greeting_answer(self) -> str:
        return (
            "Hola, soy el asistente de Domingo Berbel. "
            "Puedo responder cualquier pregunta sobre su cualificación, experiencia, proyectos y trayectoria profesional."
        )

    def _contact_answer(self) -> str:
        emails = self._contact_emails()
        linkedin = settings.professional_linkedin.strip()
        lines: list[str] = ["Puedes contactar con Domingo Berbel por estos canales profesionales:"]
        if linkedin:
            lines.append(f"- LinkedIn: {linkedin}")
        if emails:
            lines.append("- Email: " + " / ".join(emails))
        if len(lines) == 1:
            lines.append("- Actualmente no hay un canal de contacto configurado.")
        return "\n".join(lines)

    def _is_professional_scope_question(self, question: str) -> bool:
        q = question.lower()
        keywords = [
            "trabaja",
            "trabajo",
            "empresa",
            "puesto",
            "experiencia",
            "proyecto",
            "habilidad",
            "tecnologia",
            "estudios",
            "formacion",
            "trayectoria",
            "candidato",
            "domingo berbel",
            "data scientist",
            "inglés",
            "ingles",
            "idioma",
            "idiomas",
            "habla",
            "nivel",
        ]
        return any(k in q for k in keywords)

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

    def _build_search_client(self) -> SearchClient | None:
        required = [
            settings.azure_search_endpoint,
            settings.azure_search_api_key,
            settings.azure_search_index_name,
        ]
        if not all(required):
            return None

        return SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_api_key),
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

    def _map_result(self, item: dict[str, Any]) -> RetrievedChunk | None:
        source = item.get("source") or item.get("id") or "unknown"
        chunk = item.get("content") or item.get("chunk") or item.get("text")
        if not chunk:
            return None
        return RetrievedChunk(source=str(source), chunk=str(chunk))
