#!/usr/bin/env python3
# pyright: reportMissingImports=false
from __future__ import annotations

import os
from pathlib import Path

# Cargar variables de azure.env
env_file = Path(__file__).resolve().parents[1] / "infra" / "aca" / "azure.env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchField, SearchFieldDataType, SearchIndex, SimpleField
DOCS_DIR = Path(__file__).resolve().parents[1] / "documentos"


def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
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
    from docx import Document  # Lazy import to keep script optional until dependency is installed.

    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])


def ensure_index(endpoint: str, api_key: str, index_name: str) -> None:
    index_client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    names = [idx.name for idx in index_client.list_indexes()]
    if index_name in names:
        return

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="source", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
    ]
    index_client.create_index(SearchIndex(name=index_name, fields=fields))


def main() -> None:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

    if not endpoint or not api_key or not index_name:
        raise SystemExit("Missing AZURE_SEARCH_* environment variables")

    ensure_index(endpoint, api_key, index_name)
    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=AzureKeyCredential(api_key))

    payload = []
    for path in DOCS_DIR.glob("*.docx"):
        text = extract_docx(path)
        for i, chunk in enumerate(chunk_text(text), start=1):
            payload.append({
                "id": f"{path.stem}-{i}",
                "source": path.name,
                "content": chunk,
            })

    if not payload:
        raise SystemExit("No .docx documents found in /documentos")

    result = client.upload_documents(payload)
    ok = sum(1 for r in result if r.succeeded)
    print(f"Uploaded {ok}/{len(payload)} chunks to {index_name}")


if __name__ == "__main__":
    main()
