"""The English and Spanish dictionaries must stay in step.

Driven through `node` against the real ESM modules, for the same reason as the
other frontend guards: the repository has no JS test runner, node is already a
build dependency, and importing the shipped modules is honest in a way that
transcribing their contents into Python would not be.

Why this matters more than it looks. A key present in `en` and missing from `es`
does not fail the build — React renders the string `undefined` into the page. A
key that is a function in one tree and a plain string in the other is worse: the
component calls it and the whole section throws. Both are invisible until someone
switches language, which is exactly the moment nobody is watching.

The site was English-only until the two trees existed, so this file is the thing
standing between "bilingual" and "bilingual except the parts nobody clicked".
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; frontend checks need it"
)


def _node(repo_root, script: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=repo_root / "frontend",
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def trees(repo_root):
    """Every leaf path in both dictionaries, with the type of its value."""
    return _node(
        repo_root,
        """
        import en from "./src/i18n/en.js";
        import es from "./src/i18n/es.js";
        const walk = (node, prefix = "") =>
          Object.entries(node).flatMap(([key, value]) => {
            const path = prefix ? `${prefix}.${key}` : key;
            if (Array.isArray(value)) {
              // Arrays of objects (mascotSections) are walked; arrays of strings
              // are a leaf whose length has to match.
              return value.length && typeof value[0] === "object"
                ? value.flatMap((item, i) => walk(item, `${path}[${i}]`))
                : [[path, `array:${value.length}`]];
            }
            return value && typeof value === "object"
              ? walk(value, path)
              : [[path, typeof value]];
          });
        console.log(JSON.stringify({
          en: Object.fromEntries(walk(en)),
          es: Object.fromEntries(walk(es)),
        }));
        """,
    )


def test_both_dictionaries_define_the_same_keys(trees):
    english, spanish = set(trees["en"]), set(trees["es"])
    assert not english - spanish, f"missing from es.js: {sorted(english - spanish)}"
    assert not spanish - english, f"missing from en.js: {sorted(spanish - english)}"


def test_a_key_has_the_same_shape_in_both(trees):
    """A string where a component calls `tr.footer.index(4)` throws on render."""
    mismatched = {
        key: (kind, trees["es"][key])
        for key, kind in trees["en"].items()
        if key in trees["es"] and kind != trees["es"][key]
    }
    assert not mismatched, f"type or length differs: {mismatched}"


def test_no_entry_is_empty(trees):
    assert all(trees["en"].values()), "an English entry has no value"
    assert all(trees["es"].values()), "a Spanish entry has no value"


def test_the_english_tree_still_has_no_spanish(repo_root):
    """en.js is the source of truth; Spanish belongs in es.js only.

    Scoped to string values rather than the whole file, because the comments in
    en.js legitimately discuss Spanish.
    """
    values = _node(
        repo_root,
        """
        import en from "./src/i18n/en.js";
        const strings = [];
        const walk = (node) => Object.values(node).forEach((v) => {
          if (typeof v === "string") strings.push(v);
          else if (v && typeof v === "object") walk(v);
        });
        walk(en);
        console.log(JSON.stringify(strings));
        """,
    )
    import re

    # `ñ` and the inverted marks cannot appear in English UI copy. Accented
    # vowels can (a proper noun), so they are not swept here.
    offenders = [v for v in values if re.search(r"[ñÑ¿¡]", v)]
    assert not offenders, f"Spanish text in en.js: {offenders}"


def test_the_dictionaries_are_the_only_place_the_language_is_read(repo_root):
    """No component may import a dictionary directly.

    Importing `i18n/en.js` in a component pins it to English no matter what the
    switch says — which is precisely the bug the provider exists to prevent, and
    it would look like a partial translation rather than an error.
    """
    offenders = []
    for path in sorted((repo_root / "frontend/src/components").rglob("*.jsx")):
        source = path.read_text(encoding="utf-8")
        if "i18n/en" in source or "i18n/es" in source:
            offenders.append(str(path.relative_to(repo_root)))
    app = (repo_root / "frontend/src/App.jsx").read_text(encoding="utf-8")
    if "i18n/en" in app or "i18n/es" in app:
        offenders.append("frontend/src/App.jsx")
    assert not offenders, f"these read a dictionary directly instead of useT(): {offenders}"
