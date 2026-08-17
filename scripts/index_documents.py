#!/usr/bin/env python3
"""Embed the generated knowledge base into `embeddings_cache.json`.

Reads `data/kb/*.md` — the entity documents produced by `scripts/build_kb.py` —
and writes one embedding per document. Run `build_kb.py` first; this script does
not read `data/profile.yml` and will not notice if the corpus is stale.

    export GOOGLE_API_KEY=...
    python scripts/build_kb.py
    python scripts/index_documents.py

Why there is no chunking: each document is already one entity (a role, a
project, a degree) and comfortably inside the model's input limit. Splitting them
again would reintroduce the duplication that made the previous corpus 25 chunks
with 8 near-duplicates, and would break `get_entity(id)`, which needs one
document to have one address.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
KB_DIR = ROOT_DIR / "data" / "kb"
CACHE_FILE_ROOT = ROOT_DIR / "embeddings_cache.json"
CACHE_FILE_BACKEND = ROOT_DIR / "backend" / "embeddings_cache.json"

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 3072


def _api_model(model: str) -> str:
    return f"models/{model}"


def load_documents(kb_dir: Path = KB_DIR) -> list[dict[str, str]]:
    """Read every entity document, keyed by its frontmatter id.

    The id becomes the chunk `source`, which is what makes a document
    addressable by the agent's `get_entity` tool. The previous indexer used the
    filename, so every chunk from `cv_rag.docx` shared one opaque source.
    """
    sys.path.insert(0, str(ROOT_DIR))
    from scripts.build_kb import parse_frontmatter

    if not kb_dir.exists():
        raise SystemExit(
            f"error: {kb_dir} does not exist. Run 'python scripts/build_kb.py' first."
        )

    documents: list[dict[str, str]] = []
    for path in sorted(kb_dir.glob("*.md")):
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        entity_id = meta.get("id")
        if not entity_id:
            raise SystemExit(f"error: {path.name} has no id in its frontmatter")
        text = body.strip()
        if not text:
            raise SystemExit(f"error: {path.name} has an empty body")
        documents.append(
            {
                "id": entity_id,
                "source": entity_id,
                "category": meta.get("category", ""),
                "title": meta.get("title", ""),
                "chunk": text,
            }
        )

    if not documents:
        raise SystemExit(f"error: no documents found in {kb_dir}")
    return documents


def embed_text(text: str, api_key: str, model: str = EMBEDDING_MODEL) -> list[float]:
    """Embed one document for retrieval."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    response = genai.embed_content(
        model=_api_model(model),
        content=text,
        task_type="RETRIEVAL_DOCUMENT",
    )
    return response["embedding"]


def build_cache(
    documents: list[dict[str, str]], api_key: str, model: str = EMBEDDING_MODEL
) -> dict:
    payload = []
    total = len(documents)
    for index, doc in enumerate(documents, start=1):
        print(f"  [{index}/{total}] {doc['id']} …", end=" ", flush=True)
        embedding = embed_text(doc["chunk"], api_key, model)
        payload.append(
            {
                "id": doc["id"],
                "source": doc["source"],
                "category": doc["category"],
                "title": doc["title"],
                "chunk": doc["chunk"],
                "embedding": embedding,
            }
        )
        print("ok")

    return {
        "model": model,
        "dimensions": len(payload[0]["embedding"]) if payload else EMBEDDING_DIMENSIONS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chunks": payload,
    }


def write_cache(cache: dict, targets: tuple[Path, ...]) -> None:
    """Write atomically to each target so a crash cannot truncate a live cache."""
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=EMBEDDING_MODEL)
    parser.add_argument("--kb-dir", type=Path, default=KB_DIR)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="load and report the corpus without calling the embedding API",
    )
    args = parser.parse_args(argv)

    documents = load_documents(args.kb_dir)
    print(f"loaded {len(documents)} documents from {args.kb_dir}")

    if args.dry_run:
        by_category: dict[str, int] = {}
        for doc in documents:
            by_category[doc["category"]] = by_category.get(doc["category"], 0) + 1
        for category, count in sorted(by_category.items()):
            print(f"  {category:<14} {count}")
        chars = sum(len(d["chunk"]) for d in documents)
        print(f"  {'total chars':<14} {chars}")
        return 0

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("error: GOOGLE_API_KEY is not set", file=sys.stderr)
        return 1

    print(f"embedding with {args.model} …")
    cache = build_cache(documents, api_key, args.model)
    write_cache(cache, (CACHE_FILE_ROOT, CACHE_FILE_BACKEND))

    print(f"\nwrote {len(cache['chunks'])} embeddings ({cache['dimensions']} dimensions)")
    print(f"  {CACHE_FILE_ROOT}")
    print(f"  {CACHE_FILE_BACKEND}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
