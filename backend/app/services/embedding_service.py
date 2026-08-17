"""Embedding service using Google Gemini.

Three things differ from the previous version.

It uses the `google-genai` SDK. The previous `google-generativeai` package is
discontinued — it emits a deprecation warning on import and no longer receives
updates or security fixes.

Queries are embedded with `RETRIEVAL_QUERY`, not `RETRIEVAL_DOCUMENT`. Gemini's
retrieval embeddings are asymmetric: the two task types project a query and a
passage into deliberately different roles in the same space, so embedding a query
as a document degrades matching. The old code embedded every query as a document,
and passed `title="Document chunk"` while doing it.

The client is constructed once. The old code built a new service and reconfigured
the SDK on every single question.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-embedding-2"


class EmbeddingService:
    """Wrapper for Gemini retrieval embeddings."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set. Cannot initialize EmbeddingService.")
        self.model = model
        self._client = genai.Client(api_key=api_key)

    def _embed(self, text: str, task_type: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        return list(response.embeddings[0].values)

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query."""
        return self._embed(text, "RETRIEVAL_QUERY")

    def embed_document(self, text: str) -> list[float]:
        """Embed a corpus document."""
        return self._embed(text, "RETRIEVAL_DOCUMENT")

    def embed(self, text: str) -> list[float]:
        """Backwards-compatible alias; indexing is the document path."""
        return self.embed_document(text)
