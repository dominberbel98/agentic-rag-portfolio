"""The answer language must follow the visitor, not the corpus.

Two defects put English speakers into Spanish answers in production:

1. `detect_language` counted markers from a closed ~37-word English list and
   resolved ties with `english > spanish`, so any English question built from
   words outside that list scored 0-0 and fell through to Spanish. "Give me a
   summary" and "Salary expectations?" are ordinary recruiter questions with
   not one word in the list.

2. A single accented character forced Spanish. Domingo's history is full of
   Spanish place names, so "Has he worked in Almería?" — English by every other
   measure — was answered in Spanish because of the í in a proper noun.

The real fix is upstream: the frontend knows which language the visitor picked
and now sends it. These tests pin the fallback used by direct API callers, and
pin the precedence so an explicit request can never be overridden by a guess.
"""

from __future__ import annotations

import pytest

from app.services.rag_service import detect_language, resolve_language

# Real recruiter phrasings. Every one of these was answered in Spanish before.
ENGLISH_QUESTIONS = [
    "Give me a summary",
    "Python or R?",
    "Any Azure certifications?",
    "Salary expectations?",
    "Data engineering or data science?",
    "Tell me about his work",
    "Does he speak English?",
    "What is his notice period?",
    "Show me his RAG project",
]

SPANISH_QUESTIONS = [
    "¿Qué experiencia tiene en Azure?",
    "Cuéntame su trayectoria",
    "Que proyectos ha hecho",
    "Dame un resumen de su perfil",
    "Habla ingles?",
    "En qué empresa trabaja actualmente",
]

# The accent belongs to a place name, not to the writer's language.
ENGLISH_WITH_SPANISH_PROPER_NOUNS = [
    "Has he worked in Almería?",
    "What did he study in España?",
    "Did he work in Málaga or Sevilla?",
    "Tell me about his time in León",
]


@pytest.mark.parametrize("question", ENGLISH_QUESTIONS)
def test_english_questions_are_detected_as_english(question):
    assert detect_language(question) == "en"


@pytest.mark.parametrize("question", SPANISH_QUESTIONS)
def test_spanish_questions_are_detected_as_spanish(question):
    assert detect_language(question) == "es"


@pytest.mark.parametrize("question", ENGLISH_WITH_SPANISH_PROPER_NOUNS)
def test_an_accent_in_a_place_name_does_not_flip_to_spanish(question):
    assert detect_language(question) == "en"


def test_inverted_punctuation_is_decisive_for_spanish():
    """No English keyboard produces ¿ or ¡ by accident."""
    assert detect_language("¿Azure?") == "es"
    assert detect_language("¡Azure!") == "es"


def test_a_signalless_follow_up_keeps_the_conversation_language():
    """The bug users actually saw: a long English question answered in English,
    then a short follow-up flipping to Spanish mid-conversation."""
    history = [
        {"role": "user", "content": "Tell me about his experience with Azure"},
        {"role": "assistant", "content": "He deployed a RAG service on Azure."},
    ]
    assert detect_language("Certifications?", history) == "en"


def test_history_does_not_override_a_question_with_its_own_signal():
    history = [{"role": "user", "content": "Tell me about his experience"}]
    assert detect_language("¿Y su formación?", history) == "es"


def test_marker_sets_share_no_token():
    """A token in both lists cancels itself out and silently weakens both sides."""
    from app.services.rag_service import _ENGLISH_MARKERS, _SPANISH_MARKERS

    assert not (_ENGLISH_MARKERS & _SPANISH_MARKERS)


class TestResolveLanguage:
    """Precedence: what the visitor chose beats what we guess."""

    def test_an_explicit_language_wins_over_the_heuristic(self):
        # Text that the heuristic would call Spanish, requested as English.
        assert resolve_language("¿Qué tal?", [], requested="en") == "en"

    def test_an_explicit_spanish_wins_too(self):
        assert resolve_language("Tell me about his work", [], requested="es") == "es"

    def test_falls_back_to_the_heuristic_when_absent(self):
        assert resolve_language("Tell me about his work", [], requested=None) == "en"

    @pytest.mark.parametrize("bogus", ["fr", "EN-GB", "", "  ", "klingon", "es-ES"])
    def test_an_unsupported_value_falls_back_instead_of_being_trusted(self, bogus):
        """The field is client-supplied; it must not be able to inject anything."""
        assert resolve_language("Tell me about his work", [], requested=bogus) == "en"

    def test_case_and_padding_are_tolerated(self):
        assert resolve_language("¿Qué tal?", [], requested=" EN ") == "en"
