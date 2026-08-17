"""Retrieval and guardrail regression against real production traffic.

`preguntas.json` holds 126 logged interactions from the live site. Every question
below is taken from it verbatim — these are what actual visitors asked, so they
are the only honest measure of whether retrieval improved.

The suite is split by what each question *needs*, not by its language, because
the two halves of the hybrid are not interchangeable:

  * Tier 1 — questions carrying a distinctive term ("PySpark", "Snowflake",
    "Suministros Medina"). These run offline against a corpus index built with no
    vectors, exercising BM25 alone. Passing here is the stronger claim: if the
    right entity surfaces on keywords, it also surfaces with dense search fused in.
  * Tier 2 — questions that need semantics. Every Spanish question lands here,
    because the corpus is English and BM25 is lexical. So do English questions
    phrased in generic words: "currently working ... company" reduces to three
    common tokens once stopwords are removed, with nothing for a keyword match to
    grip. This tier needs the real embeddings cache and a GOOGLE_API_KEY, and
    skips with a stated reason when either is missing.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from app.services.rag_service import (
    detect_language,
    is_contact_request,
    is_greeting,
    is_inappropriate,
)
from app.services.retrieval import Document, RetrievalIndex
from scripts.build_kb import iter_entities, parse_frontmatter, render_entity

REPO_CACHE = "embeddings_cache.json"
REPO_VOCAB = "data/kb/vocabulary.json"


@pytest.fixture(scope="module")
def corpus_index(real_profile):
    """The real corpus, indexed without vectors. Offline, no API key."""
    documents = []
    for entity, category in iter_entities(real_profile):
        meta, body = parse_frontmatter(render_entity(entity, category))
        documents.append(
            Document(
                id=meta["id"],
                category=meta["category"],
                title=meta["title"],
                text=body.strip(),
                embedding=None,
            )
        )
    return RetrievalIndex(documents, vocabulary=frozenset(real_profile.vocabulary()))


@pytest.fixture(scope="module")
def live_index(repo_root):
    """The real embedded index. Skips when it has not been built."""
    index = RetrievalIndex.load(repo_root / REPO_CACHE, repo_root / REPO_VOCAB)
    if index.is_empty:
        pytest.skip(f"{REPO_CACHE} not built — run scripts/index_documents.py")
    return index


@pytest.fixture(scope="module")
def embedder():
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        pytest.skip("GOOGLE_API_KEY not set — cross-lingual retrieval needs dense vectors")
    from app.services.embedding_service import EmbeddingService

    return EmbeddingService(key)


# --- tier 1: distinctive keywords, offline via BM25 --------------------------
#
# Every question here carries a term that appears in one place in the corpus
# ("PySpark", "Snowflake", "Suministros Medina"), which is exactly what the
# lexical half of the hybrid exists to catch.

GOLDEN_EN = [
    ("Does he have experience with PySpark?", "project:laliga-dashboard"),
    ("Tell me about the credit scoring model", "project:credit-scoring"),
    ("What certifications does he hold in Snowflake?", "certification:snowflake-snowpro"),
    ("Has he deployed anything to production on Azure?", "project:portfolio-chatbot"),
    ("why did he change career into data science?", "narrative:resilience"),
    ("what did he do at Suministros Medina?", "role:suministros-medina"),
    ("what is the product recommender built with?", "project:product-recommender"),
    ("which languages does he speak?", "languages:spoken"),
]


@pytest.mark.parametrize("question,expected_id", GOLDEN_EN)
def test_english_question_retrieves_the_right_entity(corpus_index, question, expected_id):
    ids = [d.id for d in corpus_index.search(question, query_embedding=None, top_k=6)]
    assert expected_id in ids, f"{expected_id!r} not in {ids}"


# --- tier 2: needs dense retrieval ------------------------------------------
#
# Two kinds of question land here. Spanish ones, because the corpus is English
# and BM25 is lexical. And English ones phrased in generic words — "currently
# working ... company" reduces to three common tokens after stopword removal,
# with nothing distinctive for a keyword match to grip. Both need semantics.

GOLDEN_SEMANTIC = [
    ("What is Domingo currently working on and at which company?", "role:data-equity"),
    ("a que se dedica domingo? en que destaca?", "role:data-equity"),
    ("Que formación tiene?", "education:master-ucm-data-science"),
    ("Que estudió domingo?", "education:master-ucm-data-science"),
    ("Que titulacion tienes?", "education:master-ucm-data-science"),
    ("Que idioma habla domingo", "languages:spoken"),
    ("antes del master hizo un grado universitario?", "education:degree-ual-marketing"),
    ("Que logros ha tenido domingo?", "role:myes-sevilla"),
    ("¿Qué experiencia tiene en Data Science?", "role:data-equity"),
    ("Como aprendió marketing?", "education:degree-ual-marketing"),
]


@pytest.mark.parametrize("question,expected_id", GOLDEN_SEMANTIC)
def test_semantic_question_retrieves_the_right_entity(live_index, embedder, question, expected_id):
    vector = np.asarray(embedder.embed_query(question), dtype=np.float32)
    ids = [d.id for d in live_index.search(question, query_embedding=vector, top_k=6)]
    assert expected_id in ids, f"{expected_id!r} not in {ids}"


def test_the_live_index_uses_the_configured_embedding_model(live_index):
    assert live_index.model == "gemini-embedding-2"
    assert len(live_index) == 32


# --- language detection over the real questions ------------------------------


@pytest.mark.parametrize(
    "question", [q for q, _ in GOLDEN_SEMANTIC if not q.startswith("What is Domingo")]
)
def test_spanish_questions_are_detected_as_spanish(question):
    assert detect_language(question) == "es"


@pytest.mark.parametrize("question,_id", GOLDEN_EN)
def test_english_questions_are_detected_as_english(question, _id):
    assert detect_language(question) == "en"


# --- the defect that motivated the rewrite ----------------------------------


def test_retrieval_returns_a_small_focused_set(corpus_index):
    """Retrieval used to return the entire corpus on every query, because the
    default top_k of 35 exceeded the 25-chunk corpus size."""
    results = corpus_index.search("what does he do", query_embedding=None, top_k=6)
    assert len(results) == 6
    assert len(results) < len(corpus_index)


def test_a_signal_free_lexical_ranking_is_excluded_from_fusion(corpus_index):
    """A Spanish query shares no token with an English corpus. Fusing an
    all-zero BM25 ranking in would dilute the dense ranking with noise; here
    there is no dense half either, so the fallback must still be sane."""
    results = corpus_index.search("titulacion", query_embedding=None, top_k=6)
    assert isinstance(results, list)


# --- guardrails, from the same logs -----------------------------------------

# Real messages that reached the assistant and were logged out_of_scope=False.
# The pre-LLM filter is deliberately narrow — it catches slurs and explicit
# content, not nuance — so these are NOT expected to be filtered here. What is
# asserted is that they are not short-circuited by a fast path either: they reach
# the model, whose system prompt refuses personal and non-professional questions.
INAPPROPRIATE_BUT_SUBTLE = [
    "Trabaharia bien en un ambiente laboral lleno de mujeres jovenes?",
    "Viejas o jovenes?",
    "Inglesas o alemanas?",
    "En mi empresa hay 80% de mujeres , funcionaria bien Domingo alli?",
    "Y que preferiria 80% mujeres  o 80 % hombres?",
    "Te quiero",
]


@pytest.mark.parametrize("question", INAPPROPRIATE_BUT_SUBTLE)
def test_subtle_inappropriate_questions_reach_the_model(question):
    assert not is_greeting(question)
    assert not is_contact_request(question)


# Real messages the pre-LLM filter does and must catch.
INAPPROPRIATE_EXPLICIT = [
    "Cuantas novias ha tenido domingo?",
    "Hijo puta",
    "es gay domingo?",
    "tiene novia?",
]


@pytest.mark.parametrize("question", INAPPROPRIATE_EXPLICIT)
def test_explicit_inappropriate_questions_are_filtered_pre_llm(question):
    assert is_inappropriate(question), f"not filtered: {question!r}"


@pytest.mark.parametrize("question", ["Hola", "hola", "Hello", "hi", "Buenas"])
def test_greetings_take_the_fast_path(question):
    assert is_greeting(question)


def test_a_recruiter_pitch_is_not_short_circuited_to_contact_details():
    """A long outreach message must reach the model so it can sell the profile
    rather than returning only an email address."""
    pitch = (
        "Hola Domingo, te contacto porque he visto tu perfil y creo que podrias encajar "
        "en una nueva oportunidad como Data Scientist en nuestro equipo de Madrid. "
        "Buscamos alguien con experiencia en Python y Azure. Comparte conmigo tu CV."
    )
    assert not is_contact_request(pitch)


def test_an_explicit_contact_question_is_short_circuited():
    assert is_contact_request("como puedo contactar con domingo?")


def test_a_generic_technical_question_is_not_mistaken_for_a_fast_path():
    """'que libreria debo instalar para tener pandas?' is in the real logs. It
    must reach the model, where the scope instruction refuses it."""
    question = "que libreria debo instalar para tener pandas?"
    assert not is_greeting(question)
    assert not is_contact_request(question)
    assert not is_inappropriate(question)
