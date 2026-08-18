"""Guards on the frontend that do not need a JS test runner.

Two kinds of drift are worth catching, and both caused real defects:

* The zone boundaries existed as magic numbers in two Python files and two
  components, and they disagreed. That is how the Conference League zone stayed
  missing — seventh place was painted as mid-table and the legend showed three
  tiers. There is now one definition on each side of the language boundary, and
  this asserts they agree.
* A `t.foo.bar` reference to a key that does not exist in the dictionary renders
  as `undefined` rather than failing the build, so it reaches the user.

Written in pytest rather than as a JS suite because the repository has no JS test
infrastructure, and adding one to check two invariants would cost more than it
returns.
"""

from __future__ import annotations

import json
import re

import pytest

from scripts.laliga_transform import (
    CHAMPIONS_LEAGUE_SLOTS,
    CONFERENCE_LEAGUE_SLOTS,
    EUROPA_LEAGUE_SLOTS,
    RELEGATION_FROM,
    ZONES,
    zone_for_position,
)

COMPONENTS = "frontend/src/components"
DICTIONARY = "frontend/src/i18n/en.js"
LALIGA_LIB = "frontend/src/lib/laliga.js"


@pytest.fixture(scope="module")
def laliga_js(repo_root):
    return (repo_root / LALIGA_LIB).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dictionary_js(repo_root):
    return (repo_root / DICTIONARY).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def component_sources(repo_root):
    """Every component, including the ones in subdirectories.

    The glob used to be flat, so `components/futboard/*.jsx` escaped the Spanish
    sweep and the contrast check entirely — the two guards this module exists
    for. Keyed by path relative to the components directory rather than by bare
    filename, so a name reused in two folders cannot silently drop one of them.
    """
    root = repo_root / COMPONENTS
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.jsx"))
    }


# --- zone definitions agree across the language boundary ---------------------


def _js_const(source: str, name: str) -> int:
    match = re.search(rf"export const {name} = (\d+);", source)
    assert match, f"{name} not found in {LALIGA_LIB}"
    return int(match.group(1))


@pytest.mark.parametrize(
    "name,expected",
    [
        ("CHAMPIONS_LEAGUE_SLOTS", CHAMPIONS_LEAGUE_SLOTS),
        ("EUROPA_LEAGUE_SLOTS", EUROPA_LEAGUE_SLOTS),
        ("CONFERENCE_LEAGUE_SLOTS", CONFERENCE_LEAGUE_SLOTS),
        ("RELEGATION_FROM", RELEGATION_FROM),
    ],
)
def test_zone_boundaries_match_the_python_definition(laliga_js, name, expected):
    assert _js_const(laliga_js, name) == expected


def test_every_zone_has_a_colour(laliga_js):
    for zone in ZONES:
        assert re.search(rf"\b{zone}:", laliga_js), f"{zone} has no colour in {LALIGA_LIB}"


def test_every_zone_has_a_label(dictionary_js):
    zones_block = re.search(r"zones: \{(.*?)\}", dictionary_js, re.S)
    assert zones_block
    for zone in ZONES:
        assert f"{zone}:" in zones_block.group(1), f"{zone} has no label"


def test_the_legend_omits_mid_but_lists_the_rest(laliga_js):
    """`mid` is the absence of a zone, not a zone, so it is not in the legend."""
    match = re.search(r"export const LEGEND_ZONES = \[(.*?)\]", laliga_js, re.S)
    assert match
    legend = set(re.findall(r'"(\w+)"', match.group(1)))
    assert legend == set(ZONES) - {"mid"}


def test_conference_colour_is_distinct_from_the_others(laliga_js):
    """It has to read as its own tier next to green, cyan and red.

    Scoped to the ZONE_COLORS block: FORM_COLORS reuses the same green and red on
    purpose, so a document-wide uniqueness check would fail for the wrong reason.
    """
    block = re.search(r"export const ZONE_COLORS = \{(.*?)\};", laliga_js, re.S)
    assert block
    colours = dict(re.findall(r"(\w+): \"([^\"]+)\"", block.group(1)))
    assert "conference" in colours
    assert len(set(colours.values())) == len(colours), f"duplicate zone colours: {colours}"


def test_python_zone_function_covers_a_full_table():
    assert {zone_for_position(p) for p in range(1, 21)} == set(ZONES)


# --- dictionary completeness -------------------------------------------------


def _dictionary_paths(source: str) -> set[str]:
    """Every dotted path defined in en.js, e.g. 'laliga.standings.title'."""
    paths: set[str] = set()
    stack: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        # `key: {` opens a nested object
        opener = re.match(r"(\w+): \{$", stripped)
        if opener:
            stack.append(opener.group(1))
            paths.add(".".join(stack))
            continue
        if stripped.startswith("}"):
            if stack:
                stack.pop()
            continue
        # `key: value` on one line, including `key: (args) => ...` and arrays
        leaf = re.match(r"(\w+):", stripped)
        if leaf and stack:
            paths.add(".".join(stack + [leaf.group(1)]))
        # `key: {a: 1, b: 2}` inline objects
        inline = re.match(r"(\w+): \{(.+)\},?$", stripped)
        if inline and stack:
            base = ".".join(stack + [inline.group(1)])
            for key in re.findall(r"(\w+):", inline.group(2)):
                paths.add(f"{base}.{key}")
    return paths


def test_every_referenced_dictionary_key_exists(component_sources, dictionary_js):
    defined = _dictionary_paths(dictionary_js)
    # Array and function entries are invoked, so the reference carries a trailing
    # method name that is not part of the dictionary path.
    METHODS = {"map", "join", "length", "slice", "filter", "forEach", "toLocaleString"}
    missing: list[str] = []
    for name, source in component_sources.items():
        # The dictionary is imported as `tr` everywhere. It is deliberately not
        # `t`: components use `t` as a lambda parameter for a team or item, and
        # the collision made this very check report phantom failures.
        for reference in re.findall(r"(?<![\w.])tr\.((?:\w+\.)*\w+)", source):
            parts = reference.split(".")
            if parts[-1] in METHODS:
                parts = parts[:-1]
            path = ".".join(parts)
            if path and path not in defined:
                missing.append(f"{name}: {path}")
    assert not missing, "dictionary keys referenced but not defined:\n" + "\n".join(missing)


def test_the_dictionary_has_no_spanish_left(dictionary_js):
    """The whole point of the block. Proper nouns in data are fine; UI copy is not."""
    offenders = [
        line.strip()
        for line in dictionary_js.splitlines()
        if re.search(r"[áéíóúñÁÉÍÓÚÑ¿¡]", line)
    ]
    assert not offenders, "Spanish characters in the dictionary:\n" + "\n".join(offenders)


# --- no untranslated strings left in the components -------------------------


def test_no_spanish_characters_remain_in_any_component(component_sources):
    offenders = []
    for name, source in component_sources.items():
        for number, line in enumerate(source.splitlines(), start=1):
            if re.search(r"[áéíóúñÁÉÍÓÚÑ¿¡]", line):
                offenders.append(f"{name}:{number}: {line.strip()}")
    assert not offenders, "Spanish text left in components:\n" + "\n".join(offenders)


# Searching for accents alone is not enough, and missed real strings: "Temporada
# {season} · Jornada {matchday} · {n} simulaciones" carries no accented character,
# so an accent sweep reported the file clean while it was still Spanish.
_SPANISH_WORDS = re.compile(
    r"\b(temporada|jornadas?|simulaciones|modelo|partidos?|puntos|equipos?|goles"
    r"|clasificacion|descenso|victorias|empates|derrotas|selecciona|seleccionados"
    r"|cargando|productos|categorias|catalogo|prestamo|ingresos|vivienda|nombre"
    r"|mensaje|enviar|contacto|normalizadas|media|rango|mayor|menor|ninguno"
    r"|siguiente|anterior|buscar|ver|mas|menos)\b",
    re.IGNORECASE,
)

# Lines that legitimately contain one of those substrings for non-Spanish reasons.
_ALLOWED = re.compile(r"className|^\s*(//|\*|/\*)|import |activeSection|data-|aria-")


def test_no_unaccented_spanish_words_remain_in_any_component(component_sources):
    offenders = []
    for name, source in component_sources.items():
        for number, line in enumerate(source.splitlines(), start=1):
            if _ALLOWED.search(line):
                continue
            match = _SPANISH_WORDS.search(line)
            if match:
                offenders.append(f"{name}:{number}: [{match.group(0)}] {line.strip()}")
    assert not offenders, "Spanish words left in components:\n" + "\n".join(offenders)


def test_the_dictionary_has_no_unaccented_spanish_either(dictionary_js):
    offenders = []
    for number, line in enumerate(dictionary_js.splitlines(), start=1):
        if _ALLOWED.search(line):
            continue
        match = _SPANISH_WORDS.search(line)
        if match:
            offenders.append(f"{number}: [{match.group(0)}] {line.strip()}")
    assert not offenders, "Spanish words in the dictionary:\n" + "\n".join(offenders)


def test_components_do_not_hardcode_zone_colours(component_sources):
    """They must come from lib/laliga.js, or they drift again."""
    offenders = [
        name
        for name, source in component_sources.items()
        if re.search(r"^const ZONE_COLORS = \{", source, re.M)
    ]
    assert not offenders, f"components defining their own ZONE_COLORS: {offenders}"


# --- generated data the components depend on --------------------------------


def test_profile_json_shape_matches_what_the_certifications_page_reads(repo_root):
    payload = json.loads(
        (repo_root / "frontend" / "public" / "data" / "profile.json").read_text(encoding="utf-8")
    )
    assert payload["certifications"], "no certifications to render"
    for cert in payload["certifications"]:
        assert {"id", "title", "issuer", "date", "image", "skills"} <= set(cert)


def test_la_liga_data_carries_the_fields_the_dashboard_renders(repo_root):
    payload = json.loads(
        (repo_root / "frontend" / "public" / "data" / "la_liga_data.json").read_text(encoding="utf-8")
    )
    assert {"standings", "results", "fixtures", "state"} <= set(payload)
    for team in payload["standings"]:
        # `form` and `teamId` are what the new column and the React key need.
        assert "form" in team
        assert team.get("teamId") is not None
        assert team.get("zone") in ZONES


# --- contrast ----------------------------------------------------------------
#
# The CRT palette is fixed, so contrast is governed entirely by the opacity the
# text is drawn at. Measured against the #0e0e0e background: phosphor green needs
# /55 to clear WCAG AA for normal text (4.79:1), and the red #FF4136 only reaches
# 5.57:1 at full strength, so any reduction on red fails. Most text on this site
# is 0.55-0.7rem, which is "normal" for WCAG purposes, not "large".

_SURFACE = (14, 14, 14)
MIN_RATIO = 4.5


def _relative_luminance(rgb):
    def channel(value):
        v = value / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground, background=_SURFACE):
    high, low = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)), reverse=True
    )
    return (high + 0.05) / (low + 0.05)


def _blend(hex_colour: str, opacity: float, background=_SURFACE):
    fg = tuple(int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return tuple(round(f * opacity + b * (1 - opacity)) for f, b in zip(fg, background))


def test_the_contrast_helper_agrees_with_known_values():
    """Sanity-check the maths before trusting it: white on black is 21:1."""
    assert contrast_ratio((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio((0, 255, 65)) == pytest.approx(14.14, abs=0.01)


def test_every_text_colour_clears_wcag_aa(component_sources):
    offenders = []
    for name, source in component_sources.items():
        for number, line in enumerate(source.splitlines(), start=1):
            for hex_colour, opacity in re.findall(
                r"text-\[(#[0-9A-Fa-f]{6})\]/(\d+)", line
            ):
                ratio = contrast_ratio(_blend(hex_colour, int(opacity) / 100))
                if ratio < MIN_RATIO:
                    offenders.append(
                        f"{name}:{number}: {hex_colour}/{opacity} = {ratio:.2f}:1"
                    )
    assert not offenders, (
        f"text below {MIN_RATIO}:1 against the surface:\n" + "\n".join(offenders)
    )


def test_full_strength_palette_colours_are_all_usable_as_text():
    """A colour that fails even at 100% could not be fixed by raising opacity."""
    for hex_colour in ("#00FF41", "#FFD700", "#FF4136", "#00BFFF"):
        rgb = tuple(int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
        assert contrast_ratio(rgb) >= MIN_RATIO, f"{hex_colour} fails even at full opacity"
