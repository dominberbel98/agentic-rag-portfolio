from __future__ import annotations

from app.services.grounding import (
    check_answer,
    extract_candidate_entities,
)

VOCAB = frozenset(
    {
        "Data Equity",
        "Suministros Medina",
        "Python",
        "PySpark",
        "SQL",
        "Snowflake",
        "Power BI",
        "scikit-learn",
        "Azure",
        "FastAPI",
        "Universidad Complutense de Madrid",
    }
)

CONTEXT = [
    "Domingo Berbel has been Data Scientist at Data Equity in Madrid since October 2025.",
    "Technologies used in this role: Python, SQL, PySpark, Power BI, scikit-learn and Azure.",
]


# --- extraction (pure) -------------------------------------------------------


def test_extract_ignores_sentence_initial_words():
    found = extract_candidate_entities("The model was trained. However it failed.")
    assert "The" not in found
    assert "However" not in found


def test_extract_finds_a_capitalised_technology_mid_sentence():
    assert "MongoDB" in extract_candidate_entities("He uses MongoDB for storage.")


def test_extract_finds_multiword_proper_nouns():
    found = extract_candidate_entities("He worked at Data Equity on dashboards.")
    assert "Data Equity" in found


def test_extract_ignores_common_english_capitals():
    found = extract_candidate_entities("He works on Monday and in January in Spain.")
    for word in ("Monday", "January"):
        assert word not in found


def test_extract_catches_dotted_lowercase_product_names():
    assert "node.js" in extract_candidate_entities("He uses node.js daily.")


def test_extract_ignores_plain_hyphenated_compounds():
    """A bare hyphen is how both languages write ordinary compounds. Treating them
    as product names caused far more false positives than real detections; legitimate
    hyphenated libraries are declared in profile.yml and so sit in the vocabulary."""
    found = extract_candidate_entities("He works day-to-day on credit-risk and machine-learning.")
    assert found == []


# --- check_answer ------------------------------------------------------------


def test_flags_a_fabricated_technology():
    """The exact production failure: MongoDB appears nowhere in the profile."""
    answer = (
        "Domingo applies expertise in Python, PySpark, SQL, Snowflake, MongoDB, "
        "and cloud infrastructure."
    )
    result = check_answer(answer, CONTEXT, VOCAB)
    assert not result.ok
    assert "MongoDB" in result.unsupported


def test_accepts_the_same_answer_without_the_fabrication():
    answer = "Domingo applies expertise in Python, PySpark, SQL and Snowflake."
    result = check_answer(answer, CONTEXT, VOCAB)
    assert result.ok, result.unsupported


def test_accepts_entities_present_in_the_vocabulary():
    answer = "He works at Data Equity building Power BI dashboards with scikit-learn."
    assert check_answer(answer, CONTEXT, VOCAB).ok


def test_accepts_entities_present_only_in_the_retrieved_context():
    """Context is authoritative even for terms absent from the vocabulary."""
    answer = "He has been in Madrid since October 2025."
    assert check_answer(answer, CONTEXT, VOCAB).ok


def test_does_not_flag_his_own_name():
    assert check_answer("Domingo Berbel is a Data Scientist.", CONTEXT, VOCAB).ok


def test_flags_a_fabricated_employer():
    result = check_answer("He previously worked at Globex Corporation.", CONTEXT, VOCAB)
    assert not result.ok
    assert any("Globex" in term for term in result.unsupported)


def test_is_permissive_when_the_vocabulary_is_empty():
    """A failed vocabulary load must not block every answer."""
    result = check_answer("He uses MongoDB.", CONTEXT, frozenset())
    assert result.ok


def test_reports_every_unsupported_term():
    answer = "He uses MongoDB and Cassandra in production."
    result = check_answer(answer, CONTEXT, VOCAB)
    assert {"MongoDB", "Cassandra"} <= set(result.unsupported)


def test_an_empty_answer_is_grounded():
    assert check_answer("", CONTEXT, VOCAB).ok


def test_does_not_flag_terms_differing_only_by_case():
    answer = "He uses python and fastapi."
    assert check_answer(answer, CONTEXT, VOCAB).ok


# --- false positives observed against the real model -------------------------


def test_hyphenated_compounds_of_known_words_are_not_fabrications():
    """gpt-5.6-luna writes 'machine-learning' and 'customer-scoring' for things the
    corpus spells with a space. Flagging them forced a regeneration that dropped
    real content from the answer."""
    context = [
        "Domingo Berbel has been Data Scientist at Data Equity since October 2025.",
        "Builds and ships data science for international clients.",
        "He builds customer scoring models with machine learning to optimise campaigns.",
        "He works on the orchestration and execution of AI agents for companies.",
    ]
    answer = (
        "He applies machine-learning to customer-scoring, works on AI-agent "
        "orchestration, and has a data-science background."
    )
    result = check_answer(answer, context, VOCAB)
    assert result.ok, result.unsupported


def test_a_hyphenated_fabrication_is_still_caught():
    result = check_answer("He uses Mongo-DB for storage.", CONTEXT, VOCAB)
    assert not result.ok
    assert any("Mongo" in term for term in result.unsupported)


# --- language awareness ------------------------------------------------------


SPANISH_CONTEXT = [
    "Domingo Berbel completed the Bachelor's in Marketing and Market Research at "
    "Universidad de Almeria. Advanced Statistics: 10 out of 10 — Matricula de Honor.",
    "Domingo Berbel completed the Master's in Data Science, Big Data & Business "
    "Analytics at Universidad Complutense de Madrid. Advanced Python: 10 out of 10.",
]


def test_a_spanish_answer_is_not_flagged_for_translating_corpus_terms():
    """Measured against the real model: a Spanish answer about his education
    flagged ten terms, every one a faithful translation of English corpus text."""
    answer = (
        "Domingo tiene un Máster en Data Science por la Universidad Complutense de "
        "Madrid y un Grado en Marketing e Investigación de Mercados. Obtuvo "
        "Matrícula de Honor en Estadística Avanzada y un 10 en Python Avanzado."
    )
    result = check_answer(answer, SPANISH_CONTEXT, VOCAB, language="es")
    assert result.ok, result.unsupported


def test_a_fabricated_technology_is_still_caught_in_a_spanish_answer():
    """Product names survive translation, so the class that matters stays covered."""
    answer = "Domingo utiliza MongoDB y Kubernetes en su trabajo diario."
    result = check_answer(answer, SPANISH_CONTEXT, VOCAB, language="es")
    assert not result.ok
    assert "MongoDB" in result.unsupported
    assert "Kubernetes" in result.unsupported


def test_spanish_sentence_openers_are_not_entities():
    answer = "Además trabaja en Madrid. También habla inglés. Sin embargo, no más."
    assert check_answer(answer, SPANISH_CONTEXT, VOCAB, language="es").ok


def test_hyphenated_common_words_are_not_entities():
    """'day-to-day' and 'credit-risk' both triggered pointless regenerations."""
    answer = "He works with data day-to-day on credit-risk models."
    assert check_answer(answer, CONTEXT, VOCAB).ok
