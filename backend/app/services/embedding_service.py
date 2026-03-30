"""Embedding service using Google Generative AI (Gemini)."""

from __future__ import annotations

import logging

import google.generativeai as genai

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Wrapper for Google Generative AI embeddings."""

    MODEL = "gemini-embedding-001"
    API_MODEL = f"models/{MODEL}"
    TASK_TYPE = "RETRIEVAL_DOCUMENT"
    DIMENSIONS = 3072

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set. Cannot initialize EmbeddingService.")
        genai.configure(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: The text to embed
            
        Returns:
            List of 3072 embedding dimensions
            
        Raises:
            Exception if API call fails
        """
        try:
            response = genai.embed_content(
                model=self.API_MODEL,
                content=text,
                task_type=self.TASK_TYPE,
                title="Document chunk",
            )
            embedding = response["embedding"]
            if len(embedding) != self.DIMENSIONS:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self.DIMENSIONS}, got {len(embedding)}"
                )
            return embedding
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding lists
        """
        embeddings = []
        for text in texts:
            embeddings.append(self.embed(text))
        return embeddings
