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
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((repo_root / COMPONENTS).glob("*.jsx"))
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
