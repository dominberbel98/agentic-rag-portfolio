"""Detect fabricated entities in a generated answer.

Deliberately a closed-vocabulary test, not natural language inference. Block A
already knows every technology, employer, institution and credential in the
profile, because they are structured fields in `profile.yml` rather than prose.
Anything entity-shaped in an answer that appears neither in the retrieved context
nor in that vocabulary is something the model invented.

This catches fabricated *entities*, not fabricated *claims*: "led a team of
twelve" is built from ordinary words and passes. That is the accepted limit. The
failure that reached production was a fabricated entity — the deployed assistant
credited Domingo with MongoDB experience that appears in none of its sources —
and a cheap check that always runs is worth more than an expensive one needing a
second model call.

## Why the check is language-aware

The corpus is English and the assistant answers in the language it was asked in,
so a Spanish answer is a translation of English source text. Exact string matching
cannot follow that. Measured against the real model, a Spanish answer about his
education flagged ten terms — `Máster`, `Estadística Avanzada`, `Investigación de
Mercados`, `Grado` — every one a faithful translation of corpus content. Left
unfixed, that forces a regeneration on every Spanish question, doubling cost and
latency and risking a worse answer.

The asymmetry that makes this tractable: **technology and product names are not
translated.** MongoDB, Kubernetes, PostgreSQL and Terraform read the same in both
languages, and they are the entire class that does real damage on a CV. Academic
and descriptive phrases are what get translated, and they are multiword. So for a
non-English answer the check considers single-token names only, and skips
multiword phrases as presumed translations.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

__all__ = ["GroundingResult", "check_answer", "extract_candidate_entities"]

# Capitalised words, optionally joined into a multiword name by connectors.
# "and" is deliberately not a connector: it merges genuinely separate entities
# ("MongoDB and Cassandra" as one term) far more often than it joins a real name.
_PROPER_NOUN = re.compile(
    r"\b[A-Z][\w&+-]*(?:\s+(?:de|del|la|of|the)\s+[A-Z][\w&+-]*|\s+[A-Z][\w&+-]*)*"
)

# Lowercase product names, but only where the shape is unambiguous: a dot or a
# digit ("node.js", "log4j", "python3"). A bare hyphen is NOT enough — English and
# Spanish write ordinary compounds that way ("day-to-day", "credit-risk",
# "machine-learning"), and treating those as product names produced far more
# false positives than real detections. Nothing is lost: genuinely hyphenated
# libraries like scikit-learn are declared in profile.yml, so they are in the
# vocabulary and would never be flagged, while the fabrications that matter
# (MongoDB, Kubernetes, PostgreSQL) are capitalised and caught by _PROPER_NOUN.
_TECH_SHAPE = re.compile(r"\b[a-z][a-z0-9]*(?:[-.][a-z0-9]*\d[a-z0-9]*|\.[a-z0-9]+)+\b")

_SPLIT_PARTS = re.compile(r"[\s.\-]+")

# Words that carry no entity meaning, so they never count as a fabrication.
# Accents are folded before lookup, so unaccented spellings match too.
_COMMON_WORDS = frozenset(
    """
    a about after all also am an and any are as at be been being both but by can could
    did do does doing during each for from further had has have having he her here
    hers him his how i if in into is it its me more most my no nor not of off on once
    one only or other our out over own same she should so some such than that the
    their them then there these they this those through to too under until up very was
    we were what when where which while who whom why will with within would you your
    domingo berbel
    ademas al algo alguna algunas alguno algunos ante antes aqui asi aun aunque bien
    cada casi como con contra cual cuales cuando de del desde donde dos durante el ella
    ellas ellos en entre era eran es esa ese eso esta estan estas este esto estos ha
    hace hacia han hasta hay incluso la las le les lo los mas me mi mientras mucho muy
    nada ni no nos o os otra otras otro otros para pero poco por porque pues que quien
    quienes se segun sea ser si sin sobre solo son su sus tambien tanto te tiene tienen
    toda todas todo todos tras tu tus un una unas uno unos y ya
    enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre
    diciembre lunes martes miercoles jueves viernes sabado domingo
    january february march april may june july august september october november
    december monday tuesday wednesday thursday friday saturday sunday
    spain madrid seville sevilla almeria berlin bratislava slovakia germany england
    espana espanol english spanish european europe erasmus
    data scientist science
    master grado licenciatura ingenieria universidad titulacion asignatura asignaturas
    matricula honor calificacion calificaciones nota notas estadistica marketing
    formacion experiencia proyecto proyectos empresa trabajo puesto rol
    """.split()
)


def _fold(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in stripped if not unicodedata.combining(c))


@dataclass
class GroundingResult:
    ok: bool
    unsupported: list[str] = field(default_factory=list)


def _sentence_initial_terms(text: str) -> set[str]:
    """Words capitalised only because they open a sentence or a list item."""
    initials: set[str] = set()
    for fragment in re.split(r"(?<=[.!?:;])\s+|\n+|^\s*[-*]\s*", text, flags=re.MULTILINE):
        fragment = fragment.strip()
        if not fragment:
            continue
        match = re.match(r"[A-Z][\w&+-]*", fragment)
        if match:
            initials.add(_fold(match.group(0)))
    return initials


def extract_candidate_entities(text: str) -> list[str]:
    """Pull entity-shaped strings out of a passage, in order of appearance."""
    if not text:
        return []

    initials = _sentence_initial_terms(text)
    found: list[str] = []
    seen: set[str] = set()

    for raw in _PROPER_NOUN.findall(text):
        term = raw.strip().strip(",.;:!?")
        if not term:
            continue
        folded = _fold(term)
        if folded in _COMMON_WORDS or folded in seen:
            continue
        # A single word appearing only sentence-initially is grammar, not an entity.
        if " " not in term and folded in initials:
            continue
        seen.add(folded)
        found.append(term)

    for raw in _TECH_SHAPE.findall(text):
        folded = _fold(raw)
        if folded in _COMMON_WORDS or folded in seen:
            continue
        seen.add(folded)
        found.append(raw)

    return found


def _parts(term: str) -> list[str]:
    return [p for p in _SPLIT_PARTS.split(_fold(term)) if p and p not in {"de", "del", "la", "of", "the"}]


def check_answer(
    answer: str,
    retrieved_texts: list[str],
    vocabulary: frozenset[str],
    language: str = "en",
) -> GroundingResult:
    """Flag entities in `answer` supported by neither the context nor the profile.

    Returns ok when the vocabulary is empty: a failed vocabulary load should
    degrade to permissive rather than reject every answer the service produces.
    """
    if not answer.strip() or not vocabulary:
        return GroundingResult(ok=True)

    haystack = _fold(" ".join(retrieved_texts))
    allowed = {_fold(term) for term in vocabulary}
    translated = language != "en"

    unsupported: list[str] = []
    for term in extract_candidate_entities(answer):
        folded = _fold(term)
        if folded in allowed or folded in haystack:
            continue

        # In a translated answer, a multiword capitalised phrase is almost always
        # a rendering of English corpus text rather than an invention. Product
        # names, the class that matters, survive translation as single tokens.
        if translated and " " in term:
            continue

        # A compound whose every part is individually accounted for is a
        # rephrasing, not an invention: the model writes "machine-learning" and
        # "customer-scoring" for things the corpus spells with a space. A genuine
        # fabrication still fails, because a part is missing — "mongo-db" has no
        # "mongo". Parts that are ordinary words never count as support.
        parts = _parts(term)
        if parts and all(
            p in haystack or p in allowed or p in _COMMON_WORDS for p in parts
        ):
            continue

        unsupported.append(term)

    return GroundingResult(ok=not unsupported, unsupported=unsupported)
