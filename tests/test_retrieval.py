from __future__ import annotations

import json

import numpy as np
import pytest

from app.services.retrieval import (
    Document,
    RetrievalIndex,
    fuse_scores,
    normalize,
    tokenize,
)

DIMS = 8


def _vec(seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(size=DIMS).tolist()


@pytest.fixture
def index_files(tmp_path):
    """A tiny hand-built index so retrieval is testable without an API key."""
    docs = [
        ("role:data-equity", "role", "Data Scientist at Data Equity",
         "Domingo Berbel has been Data Scientist at Data Equity since October 2025. "
         "He builds Power BI dashboards and customer scoring models."),
        ("role:suministros-medina", "role", "International Sales Representative",
         "Domingo Berbel was International Sales Representative at Suministros Medina. "
         "He built an OCR delivery note classifier."),
        ("project:portfolio-chatbot", "project", "Portfolio RAG assistant",
         "A retrieval augmented assistant built with FastAPI and React, deployed on Azure."),
        ("education:master-ucm", "education", "Master in Data Science",
         "Studied Data Science at Universidad Complutense de Madrid. "
         "Advanced Python 10, Deep Learning 9.75."),
        ("languages:spoken", "languages", "Spoken languages",
         "Spanish native. English professional working proficiency."),
    ]
    cache = {
        "model": "test-model",
        "dimensions": DIMS,
        "chunks": [
            {
                "id": doc_id,
                "source": doc_id,
                "category": category,
                "title": title,
                "chunk": text,
                "embedding": _vec(i),
            }
            for i, (doc_id, category, title, text) in enumerate(docs)
        ],
    }
    cache_path = tmp_path / "embeddings_cache.json"
    cache_path.write_text(json.dumps(cache), encoding="utf-8")

    vocab_path = tmp_path / "vocabulary.json"
    vocab_path.write_text(
        json.dumps(["Data Equity", "Suministros Medina", "Power BI", "FastAPI", "React", "Azure"]),
        encoding="utf-8",
    )
    return cache_path, vocab_path


@pytest.fixture
def index(index_files):
    cache_path, vocab_path = index_files
    return RetrievalIndex.load(cache_path, vocab_path)


# --- tokenize (pure) ---------------------------------------------------------


def test_tokenize_strips_stopwords_in_both_languages():
    assert tokenize("Does he have experience with PySpark?") == ["experience", "pyspark"]
    assert tokenize("¿Que formación tiene?") == ["formacion"]


def test_tokenize_folds_accents_so_spanish_spellings_agree():
    assert tokenize("formación") == tokenize("formacion")


def test_tokenize_keeps_dotted_and_hyphenated_product_names():
    tokens = tokenize("He uses scikit-learn and node.js")
    assert "scikit-learn" in tokens
    assert "node.js" in tokens


def test_tokenize_drops_the_subjects_own_name():
    """It appears in nearly every document, so it discriminates nothing."""
    assert tokenize("Que estudio Domingo Berbel") == ["estudio"]


# --- score fusion (pure) -----------------------------------------------------


def test_normalize_maps_into_unit_range():
    out = normalize(np.array([2.0, 4.0, 6.0]))
    assert out.min() == 0.0 and out.max() == 1.0


def test_normalize_returns_zeros_for_a_flat_array():
    """A retriever with no signal must contribute nothing, not an arbitrary order."""
    assert np.all(normalize(np.array([3.0, 3.0, 3.0])) == 0.0)


def test_fusion_preserves_a_clear_dense_win():
    """The RRF failure this replaced: a decisive dense score must survive a weak
    lexical ranking that happens to disagree."""
    dense = np.array([0.731, 0.695, 0.690])
    lexical = np.array([0.0, 1.1, 1.0])
    fused = fuse_scores(dense, lexical)
    assert int(np.argmax(fused)) == 0


def test_fusion_lets_a_decisive_lexical_match_win():
    """An exact proper-noun hit overtakes a dense near-tie.

    This is the other half of the trade-off: dense leads, but a document that
    lexical is certain about can still come first when dense cannot separate the
    candidates.
    """
    dense = np.array([0.60, 0.59, 0.30])
    lexical = np.array([0.0, 9.0, 0.0])
    fused = fuse_scores(dense, lexical)
    assert int(np.argmax(fused)) == 1


def test_normalisation_is_scale_free_by_design():
    """Min-max maps whatever spread exists onto [0, 1], so a small absolute gap
    between the best two documents becomes a large normalised one. That is
    acceptable over 32 documents, where the spread covers the whole corpus, but it
    is why the lexical weight is small: it cannot be allowed to routinely
    overturn dense ordering.
    """
    tight = normalize(np.array([0.501, 0.500]))
    wide = normalize(np.array([0.9, 0.1]))
    assert tight.tolist() == wide.tolist() == [1.0, 0.0]


def test_fusion_ignores_a_flat_lexical_ranking():
    dense = np.array([0.9, 0.5, 0.1])
    flat = np.array([0.0, 0.0, 0.0])
    assert list(np.argsort(-fuse_scores(dense, flat))) == [0, 1, 2]


def test_fusion_accepts_a_single_side():
    assert fuse_scores(np.array([0.1, 0.9]), None).tolist() == [0.0, 1.0]
    assert fuse_scores(None, np.array([0.1, 0.9])).tolist() == [0.0, 1.0]


def test_fusion_requires_at_least_one_side():
    with pytest.raises(ValueError):
        fuse_scores(None, None)


# --- loading -----------------------------------------------------------------


def test_load_reads_every_document(index):
    assert len(index) == 5


def test_load_exposes_the_vocabulary(index):
    assert "Data Equity" in index.vocabulary
    assert "MongoDB" not in index.vocabulary


def test_load_missing_cache_yields_an_empty_index(tmp_path):
    idx = RetrievalIndex.load(tmp_path / "nope.json", tmp_path / "nope-vocab.json")
    assert len(idx) == 0
    assert idx.is_empty


def test_load_malformed_cache_yields_an_empty_index(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    idx = RetrievalIndex.load(bad, tmp_path / "nope-vocab.json")
    assert idx.is_empty


# --- get / list --------------------------------------------------------------


def test_get_returns_the_addressed_document(index):
    doc = index.get("role:data-equity")
    assert isinstance(doc, Document)
    assert "Data Equity" in doc.text


def test_get_unknown_id_returns_none_rather_than_raising(index):
    assert index.get("role:does-not-exist") is None


def test_get_accepts_an_unprefixed_id(index):
    """A model that writes 'data-equity' instead of 'role:data-equity' should still work."""
    assert index.get("data-equity") is not None


def test_list_entities_returns_id_and_title(index):
    entries = index.list_entities()
    assert ("role:data-equity", "Data Scientist at Data Equity") in entries
    assert len(entries) == 5


def test_list_entities_filters_by_category(index):
    entries = index.list_entities(category="role")
    assert len(entries) == 2
    assert all(e[0].startswith("role:") for e in entries)


def test_categories_are_reported(index):
    assert set(index.categories()) == {"role", "project", "education", "languages"}


# --- search ------------------------------------------------------------------


def test_search_truncates_to_top_k(index):
    """The defect this block exists to fix: top_k used to exceed the corpus size."""
    results = index.search("data", query_embedding=None, top_k=2)
    assert len(results) == 2


def test_search_never_returns_more_than_the_corpus(index):
    results = index.search("data", query_embedding=None, top_k=100)
    assert len(results) == 5


def test_search_works_without_an_embedding(index):
    """Embedding failures must degrade to BM25, not return a placeholder document."""
    results = index.search("OCR delivery note classifier", query_embedding=None, top_k=1)
    assert results[0].id == "role:suministros-medina"


def test_search_finds_keyword_matches_via_bm25(index):
    results = index.search("Universidad Complutense", query_embedding=None, top_k=1)
    assert results[0].id == "education:master-ucm"


def test_search_restricts_to_a_category(index):
    results = index.search("Domingo", query_embedding=None, top_k=5, category="project")
    assert len(results) == 1
    assert results[0].category == "project"


def test_search_unknown_category_returns_nothing(index):
    assert index.search("Domingo", query_embedding=None, top_k=5, category="nope") == []


def test_search_on_an_empty_index_returns_nothing(tmp_path):
    idx = RetrievalIndex.load(tmp_path / "nope.json", tmp_path / "nope.json")
    assert idx.search("anything", query_embedding=None, top_k=5) == []


def test_search_uses_the_embedding_when_given_one(index):
    """A query embedding equal to a document's own vector should rank it first."""
    target = index.get("project:portfolio-chatbot")
    results = index.search("", query_embedding=target.embedding, top_k=1)
    assert results[0].id == "project:portfolio-chatbot"
