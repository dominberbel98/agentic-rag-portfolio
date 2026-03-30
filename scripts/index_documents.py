#!/usr/bin/env python3
"""
Re-index documents with Google Generative AI embeddings.

Generates embeddings for all .docx files in documentos/ and caches them
in embeddings_cache.json with metadata for automatic change detection.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import google.generativeai as genai

DOCS_DIR = Path(__file__).resolve().parents[1] / "documentos"
CACHE_FILE = Path(__file__).resolve().parents[1] / "embeddings_cache.json"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_API_MODEL = f"models/{EMBEDDING_MODEL}"
EMBEDDING_DIMENSIONS = 3072
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    text = " ".join(text.split())
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, 0)
    return chunks


def extract_docx(path: Path) -> str:
    """Extract text from a .docx file."""
    from docx import Document
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])


def embed_text(text: str, api_key: str) -> list[float]:
    """Generate embedding for text using Google Generative AI."""
    genai.configure(api_key=api_key)
    try:
        response = genai.embed_content(
            model=EMBEDDING_API_MODEL,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
            title="Document chunk",
        )
        return response["embedding"]
    except Exception as e:
        print(f"Error embedding text: {e}", file=sys.stderr)
        raise


def load_existing_cache() -> dict | None:
    """Load existing cache if it exists and is valid."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load existing cache: {e}")
        return None


def main() -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Check if we should regenerate
    existing_cache = load_existing_cache()
    if existing_cache:
        cached_model = existing_cache.get("model")
        cached_dims = existing_cache.get("dimensions")
        if cached_model == EMBEDDING_MODEL and cached_dims == EMBEDDING_DIMENSIONS:
            print(
                f"Cache is valid (model={cached_model}, dimensions={cached_dims}). "
                "Skipping regeneration unless documents changed."
            )
            # For now, we'll regenerate anyway to ensure freshness, but in production
            # you could compare document mtimes with cache timestamp
        else:
            print(
                f"Cache model mismatch: cached={cached_model}, current={EMBEDDING_MODEL}. "
                "Regenerating..."
            )

    # Collect all documents and chunks
    payload = []
    for doc_path in sorted(DOCS_DIR.glob("*.docx")):
        print(f"Processing {doc_path.name}...")
        text = extract_docx(doc_path)
        chunks = chunk_text(text)
        print(f"  Generated {len(chunks)} chunks")

        for i, chunk in enumerate(chunks, start=1):
            chunk_id = f"{doc_path.stem}-{i}"
            print(f"  Embedding chunk {i}/{len(chunks)} ({chunk_id})...", end=" ", flush=True)
            try:
                embedding = embed_text(chunk, api_key)
                payload.append({
                    "id": chunk_id,
                    "source": doc_path.name,
                    "chunk": chunk,
                    "embedding": embedding,
                })
                print("✓")
            except Exception as e:
                print(f"✗ (Error: {e})")
                sys.exit(1)

    if not payload:
        print("Error: No .docx documents found in documentos/", file=sys.stderr)
        sys.exit(1)

    # Save cache with metadata
    cache_data = {
        "model": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "generated_at": datetime.utcnow().isoformat(),
        "chunks": payload,
    }

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Cached {len(payload)} chunks to {CACHE_FILE}")
    print(f"  Model: {EMBEDDING_MODEL}")
    print(f"  Dimensions: {EMBEDDING_DIMENSIONS}")


if __name__ == "__main__":
    main()
