"""Retrieval over the generated profile corpus.

Owns the index and nothing else: no LLM calls, no prompt construction. It is
handed a query embedding rather than producing one, which keeps it testable
without an API key.

Each document is one profile entity — a role, a project, a degree — addressed by
the id from its frontmatter. That is what makes `get` meaningful; the previous
index keyed 25 overlapping chunks by source filename, so `cv_rag.docx` was the
address of thirteen different things.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Weight on the lexical half once both halves are normalised. Tuned against the
# golden questions in tests/test_golden_questions.py; see fuse_scores.
LEXICAL_WEIGHT = 0.25

# BM25 without stopword removal is close to useless on natural questions: the
# common words carry most of the term mass and BM25's length normalisation then
# hands the top ranks to whichever documents are shortest. "Does he have
# experience with PySpark?" retrieved an unrelated two-line internship entry
# before this was added. Both languages are stripped, because the corpus is
# English and visitors ask in Spanish too.
_STOPWORDS = frozenset(
    """
    a about after all also am an and any are as at be been being both but by can could
    did do does doing during each for from further had has have having he her here hers
    him his how i if in into is it its me more most my no nor not of off on once only or
    other our out over own same she should so some such than that the their them then
    there these they this those through to too under until up very was we were what when
    where which while who whom why will with would you your
    a al algo algun alguna algunas alguno algunos ante antes aquel aquella como con
    contra cual cuales cuando de del desde donde dos el ella ellas ellos en entre era
    eran es esa ese eso esta estan estas este esto estos ha hace hacia han hasta hay la
    las le les lo los mas me mi mucho muy nada ni no nos o os otra otro para pero poco
    por porque que quien quienes se sea segun ser si sin so sobre son su sus tambien
    tanto te tiene tienen todo todos tu tus un una uno unos y ya
    """.split()
)

# The subject's own name is a stopword in his own corpus. It appears in nearly
# every document, so it matches everything and discriminates nothing — a query
# for "que estudio domingo" scored an identical 1.009 against every entry purely
# on the name, which is what made the lexical ranking arbitrary.
_CORPUS_STOPWORDS = frozenset({"domingo", "berbel"})

_TOKEN = re.compile(r"[a-z0-9][a-z0-9.+#-]*")


def tokenize(text: str) -> list[str]:
    """Lexical tokens for BM25, shared by the corpus and the query.

    Accents are folded so 'formación' and 'formacion' agree, and dotted or hyphenated
    product names ('scikit-learn', 'node.js', 'c#') survive as single tokens.
    """
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return [
        t
        for t in _TOKEN.findall(folded)
        if t not in _STOPWORDS and t not in _CORPUS_STOPWORDS and len(t) > 1
    ]


@dataclass(frozen=True)
class Document:
    """One retrievable profile entity."""

    id: str
    category: str
    title: str
    text: str
    embedding: np.ndarray | None = None

    @property
    def bare_id(self) -> str:
        """'role:data-equity' → 'data-equity'."""
        return self.id.split(":", 1)[-1]


def normalize(scores: np.ndarray) -> np.ndarray:
    """Min-max a score array into [0, 1]. All-equal input becomes all-zero, so a
    retriever with no signal contributes nothing rather than an arbitrary order."""
    if scores.size == 0:
        return scores
    low = float(scores.min())
    high = float(scores.max())
    if high <= low:
        return np.zeros_like(scores, dtype=np.float64)
    return (scores.astype(np.float64) - low) / (high - low)


def fuse_scores(
    dense: np.ndarray | None,
    lexical: np.ndarray | None,
    lexical_weight: float = LEXICAL_WEIGHT,
) -> np.ndarray:
    """Combine dense and lexical scores after normalising each into [0, 1].

    Deliberately *not* Reciprocal Rank Fusion. RRF throws away magnitude and keeps
    only position, which is the right trade when combining systems whose scores are
    not comparable — but both retrievers here are ours and both are normalisable,
    and discarding magnitude measurably hurt.

    Measured over the 18 golden questions taken from production logs
    (recall@6 / MRR / worst rank):

        dense only               18/18   0.659   6
        RRF, unweighted          13/18   0.562   20
        RRF, lexical at 0.4      14/18   0.582   20
        score fusion at 0.25     18/18   0.696   6

    RRF's failure mode is visible in the worst rank. For "What is Domingo currently
    working on and at which company?" dense ranked the right entry first at 0.731,
    clearly ahead of the 0.695 runner-up — but RRF saw only "rank 1 versus rank 2"
    and a weak lexical ranking over 'currently/working/company' was enough to push
    it out of the top six entirely.
    """
    if dense is None and lexical is None:
        raise ValueError("at least one score array is required")
    if dense is None:
        return normalize(lexical)  # type: ignore[arg-type]
    if lexical is None:
        return normalize(dense)
    return normalize(dense) + lexical_weight * normalize(lexical)


class RetrievalIndex:
    """Hybrid dense + lexical index over the profile corpus."""

    def __init__(
        self,
        documents: list[Document],
        vocabulary: frozenset[str] = frozenset(),
        model: str = "unknown",
    ) -> None:
        self._documents = documents
        self._by_id: dict[str, Document] = {}
        for doc in documents:
            self._by_id[doc.id] = doc
            # Also index the bare id so a model that writes 'data-equity'
            # instead of 'role:data-equity' still resolves.
            self._by_id.setdefault(doc.bare_id, doc)

        self.vocabulary = vocabulary
        self.model = model
        self._matrix = self._build_matrix(documents)
        self._bm25 = self._build_bm25(documents)

    # --- construction -------------------------------------------------------

    @staticmethod
    def _build_matrix(documents: list[Document]) -> np.ndarray | None:
        vectors = [d.embedding for d in documents if d.embedding is not None]
        if not vectors or len(vectors) != len(documents):
            return None
        matrix = np.vstack(vectors).astype(np.float32)
        # Pre-normalise so similarity is one matrix product, not a Python loop
        # over documents computing norms per query as the old code did.
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    @staticmethod
    def _build_bm25(documents: list[Document]) -> Any | None:
        if not documents:
            return None
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank-bm25 is not installed; lexical search disabled")
            return None
        corpus = [tokenize(f"{d.title} {d.text}") for d in documents]
        return BM25Okapi(corpus)

    @classmethod
    def load(cls, cache_path: Path | str, vocabulary_path: Path | str) -> RetrievalIndex:
        """Load the index, degrading to empty rather than raising.

        A malformed cache must not take the service down — an empty index still
        answers, it just cannot ground itself, and that is visible in the logs.
        """
        documents: list[Document] = []
        model = "unknown"

        cache_path = Path(cache_path)
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            model = raw.get("model", "unknown")
            for item in raw.get("chunks", []):
                embedding = item.get("embedding")
                documents.append(
                    Document(
                        id=item.get("id") or item.get("source", ""),
                        category=item.get("category", ""),
                        title=item.get("title", ""),
                        text=item.get("chunk", ""),
                        embedding=(
                            np.asarray(embedding, dtype=np.float32) if embedding else None
                        ),
                    )
                )
            logger.info("Loaded %d documents from %s (model=%s)", len(documents), cache_path, model)
        except FileNotFoundError:
            logger.error("Embeddings cache not found at %s", cache_path)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.error("Embeddings cache at %s is unusable: %s", cache_path, exc)
            documents = []

        vocabulary: frozenset[str] = frozenset()
        try:
            terms = json.loads(Path(vocabulary_path).read_text(encoding="utf-8"))
            vocabulary = frozenset(str(t) for t in terms)
            logger.info("Loaded %d vocabulary terms", len(vocabulary))
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Vocabulary unavailable (%s); grounding will be permissive", exc)

        return cls(documents, vocabulary, model)

    # --- accessors ----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._documents)

    @property
    def is_empty(self) -> bool:
        return not self._documents

    def get(self, entity_id: str) -> Document | None:
        return self._by_id.get(entity_id.strip())

    def list_entities(self, category: str | None = None) -> list[tuple[str, str]]:
        return [
            (d.id, d.title)
            for d in self._documents
            if category is None or d.category == category
        ]

    def categories(self) -> list[str]:
        seen: list[str] = []
        for doc in self._documents:
            if doc.category and doc.category not in seen:
                seen.append(doc.category)
        return seen

    # --- search -------------------------------------------------------------

    def search(
        self,
        query: str,
        query_embedding: np.ndarray | None,
        top_k: int = 6,
        category: str | None = None,
    ) -> list[Document]:
        """Hybrid search over the allowed subset, truncated to `top_k`.

        `top_k` is a real limit here. The previous implementation defaulted to 35
        over a 25-chunk corpus, so every query returned everything and the fusion
        ranked a set that was already complete.
        """
        if self.is_empty:
            return []

        allowed = [
            i
            for i, doc in enumerate(self._documents)
            if category is None or doc.category == category
        ]
        if not allowed:
            return []

        dense: np.ndarray | None = None
        if query_embedding is not None and self._matrix is not None:
            vector = np.asarray(query_embedding, dtype=np.float32)
            magnitude = float(np.linalg.norm(vector))
            if magnitude > 0:
                dense = (self._matrix @ (vector / magnitude))[allowed]

        lexical: np.ndarray | None = None
        query_tokens = tokenize(query)
        if self._bm25 is not None and query_tokens:
            lexical = np.asarray(self._bm25.get_scores(query_tokens), dtype=np.float64)[allowed]

        if dense is None and lexical is None:
            # No signal at all (empty query, no embedding, no matching tokens):
            # fall back to document order so callers still get something coherent.
            return [self._documents[i] for i in allowed[:top_k]]

        fused = fuse_scores(dense, lexical)
        ranked = sorted(range(len(allowed)), key=lambda p: (-float(fused[p]), allowed[p]))
        return [self._documents[allowed[p]] for p in ranked[:top_k]]
