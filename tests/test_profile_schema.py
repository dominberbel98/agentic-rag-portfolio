from __future__ import annotations

import pytest

from backend.app.profile_schema import Profile, ProfileError, load_profile


def test_accepts_minimal_valid_profile(minimal_profile):
    p = Profile.from_mapping(minimal_profile)
    assert p.meta.name == "Domingo Berbel"
    assert len(p.roles) == 1


def test_rejects_duplicate_entity_ids(minimal_profile):
    minimal_profile["projects"][0]["id"] = minimal_profile["roles"][0]["id"]
    with pytest.raises(ProfileError, match="duplicate id"):
        Profile.from_mapping(minimal_profile)


def test_rejects_two_current_roles(minimal_profile):
    extra = dict(minimal_profile["roles"][0])
    extra["id"] = "second-current"
    extra["end"] = None
    minimal_profile["roles"].append(extra)
    with pytest.raises(ProfileError, match="exactly one current role"):
        Profile.from_mapping(minimal_profile)


def test_rejects_no_current_role(minimal_profile):
    minimal_profile["roles"][0]["end"] = "2026-01"
    with pytest.raises(ProfileError, match="exactly one current role"):
        Profile.from_mapping(minimal_profile)


def test_rejects_unknown_key(minimal_profile):
    minimal_profile["meta"]["nickname"] = "Domi"
    with pytest.raises(ProfileError, match="nickname"):
        Profile.from_mapping(minimal_profile)


def test_rejects_stack_entry_absent_from_skills(minimal_profile):
    minimal_profile["roles"][0]["stack"].append("Fortran")
    with pytest.raises(ProfileError, match="Fortran"):
        Profile.from_mapping(minimal_profile)


def test_rejects_project_stack_entry_absent_from_skills(minimal_profile):
    minimal_profile["projects"][0]["stack"].append("COBOL")
    with pytest.raises(ProfileError, match="COBOL"):
        Profile.from_mapping(minimal_profile)


def test_rejects_role_ending_before_it_starts(minimal_profile):
    minimal_profile["roles"][0]["end"] = "2020-01"
    minimal_profile["roles"][1:] = []
    with pytest.raises(ProfileError, match="ends before it starts"):
        Profile.from_mapping(minimal_profile)


def test_entity_ids_are_prefixed_by_category(minimal_profile):
    p = Profile.from_mapping(minimal_profile)
    ids = p.entity_ids()
    assert "role:data-equity" in ids
    assert "project:portfolio-chatbot" in ids
    assert "education:master-ucm" in ids
    assert "certification:snowflake-snowpro" in ids
    assert "narrative:resilience" in ids


def test_entity_ids_are_unique(minimal_profile):
    p = Profile.from_mapping(minimal_profile)
    ids = p.entity_ids()
    assert len(ids) == len(set(ids))


def test_vocabulary_includes_employers_and_technologies(minimal_profile):
    p = Profile.from_mapping(minimal_profile)
    vocab = p.vocabulary()
    assert "Data Equity" in vocab
    assert "Python" in vocab
    assert "Snowflake" in vocab
    assert "Universidad Complutense de Madrid" in vocab


def test_vocabulary_excludes_hallucinated_terms(minimal_profile):
    """Regression guard for the production hallucination this work exists to fix."""
    p = Profile.from_mapping(minimal_profile)
    vocab = p.vocabulary()
    assert "MongoDB" not in vocab
    assert "MLOps" not in vocab


def test_current_role_is_addressable(minimal_profile):
    p = Profile.from_mapping(minimal_profile)
    assert p.current_role().company == "Data Equity"


# --- against the real authored file -----------------------------------------


def test_load_profile_reads_the_real_file(repo_root):
    p = load_profile(repo_root / "data" / "profile.yml")
    assert p.meta.name == "Domingo Berbel"
    assert len(p.roles) >= 4
    assert len(p.certifications) == 6
    assert p.current_role().company == "Data Equity"


def test_real_profile_has_no_duplicate_ids(repo_root):
    p = load_profile(repo_root / "data" / "profile.yml")
    ids = p.entity_ids()
    assert len(ids) == len(set(ids))


def test_real_profile_covers_the_live_site_projects(repo_root):
    """The three projects that were live on the site but missing from the .docx."""
    p = load_profile(repo_root / "data" / "profile.yml")
    ids = {proj.id for proj in p.projects}
    assert {"portfolio-chatbot", "laliga-dashboard", "credit-scoring", "product-recommender"} <= ids


def test_load_profile_reports_the_offending_field(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("meta:\n  name: X\n", encoding="utf-8")
    with pytest.raises(ProfileError) as exc:
        load_profile(bad)
    assert "roles" in str(exc.value)


def test_load_profile_reports_a_missing_file(tmp_path):
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "nope.yml")
