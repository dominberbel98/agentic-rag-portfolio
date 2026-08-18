"""The tool-calling loop that answers questions about the profile.

The model is given search tools and decides what to look up, instead of a table
of Spanish keyword lists deciding for it and appending hand-written expansion
terms to the query. That table was roughly 400 lines, only matched phrasings
someone had thought of, and made the service bilingual by accident.

Facts are not in the prompt. The old system prompt hardcoded exact grades,
mandated project mentions and a numbered strengths list, which made the prompt
the real source of truth and the corpus decoration. Here the prompt carries role,
tone, scope and safety only; everything factual comes from the corpus.

Reranking is done by the model rather than a cross-encoder: the container is
0.25 vCPU / 0.5 GiB, where ~90 MB of weights plus onnxruntime alongside FastAPI
risks OOM and inference on a quarter core would be slow.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.services.grounding import check_answer
from app.services.retrieval import Document, RetrievalIndex

logger = logging.getLogger(__name__)

OUT_OF_SCOPE = "OUT_OF_SCOPE"

Embedder = Callable[[str], "np.ndarray | None"]


@dataclass
class AgentLimits:
    """Bounds on the loop. A model that keeps searching must not exhaust the
    daily token budget or hang the request."""

    max_iterations: int = 4
    max_tool_calls: int = 6
    max_documents: int = 8
    search_top_k: int = 6


@dataclass
class AgentResult:
    answer: str
    documents: list[Document] = field(default_factory=list)
    out_of_scope: bool = False
    regenerated: bool = False


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_profile",
            "description": (
                "Search Domingo Berbel's professional profile. Returns the most "
                "relevant entries. Use this first for most questions. Narrow with "
                "`category` when the question is clearly about one kind of thing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to look for, in natural language.",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["role", "education", "project", "certification", "languages", "narrative"],
                        "description": "Optional filter. Omit to search everything.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity",
            "description": (
                "Fetch one profile entry in full by its id, for example "
                "'role:data-equity' or 'project:portfolio-chatbot'. Use after "
                "search_profile or list_entities when you need the complete text."
            ),
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_entities",
            "description": (
                "List the ids and titles of everything in the profile, so you can "
                "see what exists before searching. Optionally filter by category."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["role", "education", "project", "certification", "languages", "narrative"],
                    }
                },
            },
        },
    },
]


def build_system_prompt(language: str, now: datetime, categories: list[str]) -> str:
    """Role, tone, scope and safety. Deliberately no facts."""
    language_rule = (
        "Answer in English."
        if language == "en"
        else "Answer in Spanish, because the user wrote in Spanish."
    )
    return (
        "You are the assistant for Domingo Berbel's professional portfolio. Your only "
        "role is to present his professional profile to recruiters, hiring managers and "
        "engineers who are evaluating him.\n\n"
        f"Today is {now.strftime('%Y-%m-%d')}. Use this when asked about his current "
        "situation, recency or timelines. Treat anything with an end date in the past as "
        "completed, not ongoing.\n\n"
        "HOW TO ANSWER\n"
        "Search the profile before answering. You have three tools; call them as often as "
        "you need, and search again with different wording if the first result is thin. "
        f"Available categories: {', '.join(categories)}.\n\n"
        "GROUNDING — this matters more than anything else here.\n"
        "State only what the retrieved entries support. Never name a technology, employer, "
        "client, institution, metric or credential that does not appear in them. If the "
        "profile does not cover something, say so plainly rather than filling the gap: an "
        "invented skill is worse than an admitted gap, because he would have to answer for "
        "it in an interview.\n\n"
        "SCOPE\n"
        "You are not a general assistant, tutor, or coder. If asked a generic technical "
        "question (how to install something, fix an error, explain a concept, write code, "
        "solve maths), or about news, history, recipes or anything unrelated to his "
        "professional profile, do not answer it even partially.\n"
        "Never answer personal, sexual, romantic, political or religious questions about "
        "him or anyone else.\n"
        f"If the message is out of professional scope, inappropriate, or is a statement "
        f"rather than a question about his profile (sports cheers, jokes, random remarks), "
        f"reply with exactly: {OUT_OF_SCOPE}\n"
        "Do not try to connect an unrelated remark back to his profile.\n\n"
        "STYLE\n"
        f"{language_rule} Write clean prose with no citation markers, no bracketed "
        "references and no footnotes. Be polished, specific and confident. Match length to "
        "the question: a simple one deserves 50-90 words, a broad or multi-part one "
        "150-280. Quote concrete facts — dates, employers, grades, technologies, outcomes — "
        "from what you retrieved. Vary your phrasing across turns.\n\n"
        "If someone sends a job offer or recruiting message, acknowledge it, name two or "
        "three specifics from the profile that match what they describe, and mention that "
        "he can be reached via LinkedIn or email."
    )


class ProfileAgent:
    def __init__(
        self,
        client: Any,
        model: str,
        index: RetrievalIndex,
        embedder: Embedder,
        limits: AgentLimits | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.index = index
        self.embedder = embedder
        self.limits = limits or AgentLimits()
        # Parameter names diverge across model generations. Probed from the name
        # rather than by catching a 400 mid-conversation, which would cost a
        # wasted round trip on every request.
        family = (model or "").lower()
        self._uses_completion_tokens = family.startswith(("gpt-5", "o1", "o3", "o4"))
        self._supports_temperature = not family.startswith(("o1", "o3", "o4"))
        # The GPT-5 family reasons by default, and /v1/chat/completions refuses to
        # combine reasoning with function tools: "To use function tools, use
        # /v1/responses or set reasoning_effort to 'none'". Tool calling is the
        # whole design here and the SSE contract is built on chat.completions, so
        # reasoning is switched off rather than migrating the transport. The tool
        # loop supplies the structure that reasoning would otherwise provide.
        self._disable_reasoning = family.startswith("gpt-5")

    # --- tool execution -----------------------------------------------------

    def _run_tool(self, name: str, arguments: str, collected: list[Document]) -> str:
        """Execute one tool call, returning a string for the model.

        Every failure path returns a message rather than raising: the model can
        correct a bad id or a bad category if we tell it what went wrong.
        """
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            return "Error: arguments were not valid JSON. Retry with a valid JSON object."

        if not isinstance(args, dict):
            return "Error: arguments must be a JSON object."

        if name == "search_profile":
            query = str(args.get("query", "")).strip()
            category = args.get("category")
            if not query:
                return "Error: 'query' is required."
            if category is not None and category not in self.index.categories():
                return (
                    f"Error: unknown category '{category}'. "
                    f"Valid categories: {', '.join(self.index.categories())}."
                )
            docs = self.index.search(
                query,
                query_embedding=self.embedder(query),
                top_k=self.limits.search_top_k,
                category=category,
            )
            self._collect(docs, collected)
            if not docs:
                return "No entries matched. Try different wording or omit the category."
            return self._format_documents(docs)

        if name == "get_entity":
            entity_id = str(args.get("id", "")).strip()
            if not entity_id:
                return "Error: 'id' is required."
            doc = self.index.get(entity_id)
            if doc is None:
                available = ", ".join(i for i, _ in self.index.list_entities()[:12])
                return f"Error: no entry with id '{entity_id}'. Valid ids include: {available}."
            self._collect([doc], collected)
            return self._format_documents([doc])

        if name == "list_entities":
            category = args.get("category")
            entries = self.index.list_entities(category=category)
            if not entries:
                return f"No entries in category '{category}'."
            return "\n".join(f"- {entity_id}: {title}" for entity_id, title in entries)

        return (
            f"Error: '{name}' is not a tool. Available: "
            "search_profile, get_entity, list_entities."
        )

    def _collect(self, docs: list[Document], collected: list[Document]) -> None:
        """Accumulate what was retrieved, for grounding and citations."""
        known = {d.id for d in collected}
        for doc in docs:
            if doc.id not in known and len(collected) < self.limits.max_documents:
                collected.append(doc)
                known.add(doc.id)

    @staticmethod
    def _format_documents(docs: list[Document]) -> str:
        return "\n\n".join(f"[{d.id}] {d.title}\n{d.text}" for d in docs)

    # --- the loop -----------------------------------------------------------

    def _messages(
        self, question: str, history: list[dict], language: str, now: datetime
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": build_system_prompt(language, now, self.index.categories()),
            }
        ]
        for msg in (history or [])[-20:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": question})
        return messages

    def _complete(self, messages: list[dict[str, Any]], *, with_tools: bool) -> Any:
        # The GPT-5 family rejects `max_tokens` and requires
        # `max_completion_tokens`; older models accept only the former.
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens" if self._uses_completion_tokens else "max_tokens": 900,
        }
        if self._supports_temperature:
            kwargs["temperature"] = 0.2
        if self._disable_reasoning:
            kwargs["reasoning_effort"] = "none"
        if with_tools:
            kwargs["tools"] = TOOLS
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def _run_loop(
        self, question: str, history: list[dict], language: str, now: datetime
    ) -> tuple[str, list[dict[str, Any]], list[Document]]:
        """Drive tool calls until the model produces prose or the caps trip."""
        messages = self._messages(question, history, language, now)
        collected: list[Document] = []
        tool_calls_used = 0

        for iteration in range(self.limits.max_iterations):
            allow_tools = tool_calls_used < self.limits.max_tool_calls
            completion = self._complete(messages, with_tools=allow_tools)
            message = completion.choices[0].message
            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                return (message.content or "").strip(), messages, collected

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tool_call in tool_calls:
                if tool_calls_used >= self.limits.max_tool_calls:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "Error: tool call budget exhausted. Answer with what you have.",
                        }
                    )
                    continue
                tool_calls_used += 1
                output = self._run_tool(
                    tool_call.function.name, tool_call.function.arguments, collected
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": output}
                )

            logger.info(
                "[AGENT] iteration=%d tool_calls=%d documents=%d",
                iteration + 1,
                tool_calls_used,
                len(collected),
            )

        # Caps tripped while the model was still calling tools. Ask once more
        # without tools so the request returns prose rather than nothing.
        completion = self._complete(messages, with_tools=False)
        return (completion.choices[0].message.content or "").strip(), messages, collected

    # --- public API ---------------------------------------------------------

    def answer(
        self,
        question: str,
        history: list[dict] | None = None,
        language: str = "es",
        now: datetime | None = None,
    ) -> AgentResult:
        now = now or datetime.now(timezone.utc)
        text, messages, documents = self._run_loop(question, history or [], language, now)

        if text.strip() == OUT_OF_SCOPE:
            return AgentResult(answer="", documents=documents, out_of_scope=True)

        grounding = check_answer(
            text, [d.text for d in documents], self.index.vocabulary, language
        )
        if grounding.ok:
            return AgentResult(answer=text, documents=documents)

        logger.warning("[AGENT] ungrounded terms=%s — regenerating once", grounding.unsupported)
        messages = messages + [
            {"role": "assistant", "content": text},
            {
                "role": "user",
                "content": (
                    "These terms are not supported by anything you retrieved: "
                    f"{', '.join(grounding.unsupported)}. "
                    "Rewrite the answer without them. Do not substitute other names — "
                    "if the profile does not cover it, leave it out."
                ),
            },
        ]
        retry = self._complete(messages, with_tools=False)
        retried = (retry.choices[0].message.content or "").strip()
        return AgentResult(
            answer=retried or text,
            documents=documents,
            out_of_scope=False,
            regenerated=True,
        )

