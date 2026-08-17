from __future__ import annotations

import json

import pytest

from scripts.build_kb import build, parse_frontmatter, render_entity


def _boom(*args, **kwargs):
    raise RuntimeError("simulated write failure")


# --- rendering ---------------------------------------------------------------


def test_render_entity_emits_frontmatter_with_id_and_category(sample_role):
    md = render_entity(sample_role, "role")
    meta, body = parse_frontmatter(md)
    assert meta["id"] == "role:data-equity"
    assert meta["category"] == "role"
    assert meta["title"]
    assert body.strip()


def test_render_entity_states_the_current_role_as_current(sample_role):
    md = render_entity(sample_role, "role")
    assert "current" in md.lower()


def test_render_entity_formats_dates_readably(sample_role):
    md = render_entity(sample_role, "role")
    assert "October 2025" in md
    assert "2025-10" not in md


def test_render_entity_includes_achievements_and_stack(sample_role):
    md = render_entity(sample_role, "role")
    assert "Power BI dashboards" in md
    assert "Python" in md


def test_render_entity_is_prose_not_dumped_yaml(sample_role):
    md = render_entity(sample_role, "role")
    body = parse_frontmatter(md)[1]
    assert "achievements:" not in body
    assert "stack:" not in body


# --- build -------------------------------------------------------------------


def test_build_emits_one_document_per_entity(small_profile, tmp_path):
    result = build(small_profile, tmp_path / "kb", tmp_path / "fe")
    assert len(result.documents) == len(small_profile.entity_ids())


def test_build_document_ids_match_entity_ids(small_profile, tmp_path):
    build(small_profile, tmp_path / "kb", tmp_path / "fe")
    ids = set()
    for doc in (tmp_path / "kb").glob("*.md"):
        ids.add(parse_frontmatter(doc.read_text(encoding="utf-8"))[0]["id"])
    assert ids == set(small_profile.entity_ids())


def test_build_is_deterministic(small_profile, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    build(small_profile, a, tmp_path / "fa")
    build(small_profile, b, tmp_path / "fb")
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel


def test_no_document_is_empty(real_profile, tmp_path):
    result = build(real_profile, tmp_path / "kb", tmp_path / "fe")
    for doc in result.documents:
        body = parse_frontmatter(doc.read_text(encoding="utf-8"))[1]
        assert body.strip(), f"{doc.name} has an empty body"


def test_vocabulary_excludes_hallucinated_terms(real_profile, tmp_path):
    """The production failure this whole block exists to prevent."""
    build(real_profile, tmp_path / "kb", tmp_path / "fe")
    vocab = json.loads((tmp_path / "kb" / "vocabulary.json").read_text(encoding="utf-8"))
    assert "MongoDB" not in vocab
    assert "MLOps" not in vocab
    assert "Data Equity" in vocab
    assert "Python" in vocab


def test_vocabulary_is_sorted(real_profile, tmp_path):
    build(real_profile, tmp_path / "kb", tmp_path / "fe")
    vocab = json.loads((tmp_path / "kb" / "vocabulary.json").read_text(encoding="utf-8"))
    assert vocab == sorted(vocab)


def test_build_writes_frontend_profile_json(real_profile, tmp_path):
    build(real_profile, tmp_path / "kb", tmp_path / "fe")
    data = json.loads((tmp_path / "fe" / "profile.json").read_text(encoding="utf-8"))
    assert len(data["certifications"]) == 6
    assert data["skills"]["programming"]
    assert data["meta"]["name"] == "Domingo Berbel"


def test_frontend_certifications_keep_the_shape_the_ui_expects(real_profile, tmp_path):
    """Certificaciones.jsx reads these keys directly."""
    build(real_profile, tmp_path / "kb", tmp_path / "fe")
    data = json.loads((tmp_path / "fe" / "profile.json").read_text(encoding="utf-8"))
    for cert in data["certifications"]:
        assert set(cert) >= {"id", "title", "issuer", "date", "image", "skills"}
        assert isinstance(cert["skills"], list)


def test_certification_images_resolve_to_real_files(real_profile, repo_root):
    for cert in real_profile.certifications:
        if cert.image is None:
            continue
        path = repo_root / "frontend" / "public" / cert.image.lstrip("/")
        assert path.exists(), f"{cert.id} image missing: {path}"


def test_build_is_atomic_on_failure(real_profile, tmp_path, monkeypatch):
    out = tmp_path / "kb"
    monkeypatch.setattr("scripts.build_kb._write_vocabulary", _boom)
    with pytest.raises(RuntimeError):
        build(real_profile, out, tmp_path / "fe")
    assert not out.exists(), "a partial KB was left behind"


def test_build_replaces_a_previous_corpus_cleanly(small_profile, tmp_path):
    out = tmp_path / "kb"
    build(small_profile, out, tmp_path / "fe")
    stale = out / "stale-entity.md"
    stale.write_text("---\nid: gone\n---\nremoved entity\n", encoding="utf-8")
    build(small_profile, out, tmp_path / "fe")
    assert not stale.exists(), "stale document survived a rebuild"


def test_real_corpus_covers_every_category(real_profile, tmp_path):
    build(real_profile, tmp_path / "kb", tmp_path / "fe")
    categories = set()
    for doc in (tmp_path / "kb").glob("*.md"):
        categories.add(parse_frontmatter(doc.read_text(encoding="utf-8"))[0]["category"])
    assert categories == {"role", "education", "project", "certification", "languages", "narrative"}
