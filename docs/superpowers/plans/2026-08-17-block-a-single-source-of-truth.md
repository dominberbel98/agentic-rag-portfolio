# Block A — Single Source of Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace three duplicated, partly-false `.docx` files with a single validated `data/profile.yml` that generates the RAG corpus, a groundedness vocabulary, and the frontend's certification data.

**Architecture:** `profile.yml` is authored by hand and is the only place profile facts live. A Pydantic model validates it. `scripts/build_kb.py` is a pure function from that file to three generated artefacts: `data/kb/*.md` (one document per entity, for retrieval), `data/kb/vocabulary.json` (every named entity, for Block B's groundedness check), and `frontend/public/data/profile.json` (certifications and skills, for the UI). Nothing downstream reads the YAML directly.

**Tech Stack:** Python 3.12, PyYAML, Pydantic v2, pytest.

## Global Constraints

- Profile content is authored in **English**. The assistant translates at answer time.
- Generation must be **deterministic**: two runs over the same input produce byte-identical output.
- Generation must be **atomic**: write to a temp directory, move into place only on full success. A half-written KB must never be loadable.
- Exactly **one** role may have `end: null`.
- Entity `id` values are the retrieval addresses used by Block B. They must be unique across the whole file and stable — renaming one invalidates Block B's tests.
- The `.docx` files are **archived, not deleted** — moved to `documentos/legacy/`, which stays gitignored.
- No secret, API key or personal contact detail beyond what is already public (the two published emails and the LinkedIn URL) enters a tracked file.
- `data/profile.yml` is **tracked**. It contains only what the site already publishes.

## File Structure

| File | Responsibility |
|------|----------------|
| `data/profile.yml` | Create. The single source of truth. Hand-authored. |
| `backend/app/profile_schema.py` | Create. Pydantic models + `load_profile(path)`. Validation only, no generation. Lives in `backend/app` so the backend can import it too. |
| `scripts/build_kb.py` | Create. Pure generator: YAML → `kb/*.md`, `vocabulary.json`, `profile.json`. Imports the schema, owns no validation rules. |
| `tests/conftest.py` | Create. Shared fixtures: repo root path, a minimal valid profile dict. |
| `tests/test_profile_schema.py` | Create. Validation acceptance and rejection cases. |
| `tests/test_build_kb.py` | Create. Determinism, atomicity, output shape. |
| `pytest.ini` | Create. Test discovery config, so `pytest` works from the repo root. |
| `data/kb/*.md` | Generated. Gitignored. |
| `data/kb/vocabulary.json` | Generated. Gitignored. |
| `frontend/public/data/profile.json` | Generated. **Tracked** — the SWA build serves it statically. |

Rationale for splitting schema from generator: the schema is imported by the backend at runtime (Block B validates the corpus it loads), while the generator is a build-time script the backend never imports. Keeping them separate stops build-time dependencies leaking into the container image.

---

### Task 1: Schema and validation

**Files:**
- Create: `backend/app/profile_schema.py`
- Create: `tests/conftest.py`
- Create: `tests/test_profile_schema.py`
- Create: `pytest.ini`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Profile` — Pydantic model, the root document.
  - `Role`, `Education`, `Project`, `Certification`, `Skills`, `Meta`, `Grade` — nested models.
  - `load_profile(path: Path) -> Profile` — reads YAML, validates, raises `ProfileError` with the offending field path on failure.
  - `ProfileError(Exception)`.
  - `Profile.entity_ids() -> list[str]` — every id in document order.
  - `Profile.vocabulary() -> set[str]` — every technology, employer, institution and credential name.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_profile_schema.py
import pytest
from backend.app.profile_schema import Profile, ProfileError, load_profile


def test_accepts_minimal_valid_profile(minimal_profile):
    p = Profile.model_validate(minimal_profile)
    assert p.meta.name == "Domingo Berbel"
    assert len(p.roles) == 1


def test_rejects_duplicate_entity_ids(minimal_profile):
    minimal_profile["projects"][0]["id"] = minimal_profile["roles"][0]["id"]
    with pytest.raises(ProfileError, match="duplicate id"):
        Profile.model_validate(minimal_profile)


def test_rejects_two_current_roles(minimal_profile):
    extra = dict(minimal_profile["roles"][0])
    extra["id"] = "second-current"
    extra["end"] = None
    minimal_profile["roles"].append(extra)
    with pytest.raises(ProfileError, match="exactly one current role"):
        Profile.model_validate(minimal_profile)


def test_rejects_unknown_key(minimal_profile):
    minimal_profile["meta"]["nickname"] = "Domi"
    with pytest.raises(ProfileError, match="nickname"):
        Profile.model_validate(minimal_profile)


def test_rejects_stack_entry_absent_from_skills(minimal_profile):
    minimal_profile["roles"][0]["stack"].append("Fortran")
    with pytest.raises(ProfileError, match="Fortran"):
        Profile.model_validate(minimal_profile)


def test_entity_ids_are_prefixed_by_category(minimal_profile):
    p = Profile.model_validate(minimal_profile)
    assert "role:data-equity" in p.entity_ids()
    assert "project:portfolio-chatbot" in p.entity_ids()


def test_vocabulary_includes_employers_and_technologies(minimal_profile):
    p = Profile.model_validate(minimal_profile)
    vocab = p.vocabulary()
    assert "Data Equity" in vocab
    assert "Python" in vocab
    assert "MongoDB" not in vocab


def test_load_profile_reads_the_real_file(repo_root):
    p = load_profile(repo_root / "data" / "profile.yml")
    assert p.meta.name
    assert len(p.roles) >= 4
    assert len(p.certifications) == 6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_profile_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.profile_schema'`

- [ ] **Step 3: Write `pytest.ini` and `tests/conftest.py`**

`pytest.ini` puts the repo root on `sys.path` so `backend.app.*` imports resolve without installing a package.

- [ ] **Step 4: Implement `backend/app/profile_schema.py`**

Models use `model_config = ConfigDict(extra="forbid")` so unknown keys are rejected. Cross-field rules (`duplicate id`, `exactly one current role`, unresolvable stack entries) go in a `@model_validator(mode="after")` on `Profile`. `load_profile` catches `ValidationError` and re-raises `ProfileError` with the joined field path, so a typo names its own location.

- [ ] **Step 5: Run tests — all but `test_load_profile_reads_the_real_file` pass**

Run: `.venv/bin/pytest tests/test_profile_schema.py -v`
Expected: 7 pass, 1 fail (`data/profile.yml` does not exist yet)

- [ ] **Step 6: Commit**

```bash
git add pytest.ini tests/conftest.py tests/test_profile_schema.py backend/app/profile_schema.py
git commit -m "feat(kb): add profile schema with cross-field validation"
```

---

### Task 2: Author `data/profile.yml`

**Files:**
- Create: `data/profile.yml`
- Modify: `.gitignore` (add `data/kb/`)

**Interfaces:**
- Consumes: `Profile` schema from Task 1.
- Produces: the validated source document every later task reads.

Content is migrated from `documentos/cv_rag.docx`, `letter_rag.docx` and
`more_information.docx`, with these corrections applied (from the spec's audit):

1. `more_information.docx` contributes nothing new — it is a verbatim copy of the
   second half of `cv_rag.docx`. Migrate once.
2. MyES Sevilla tenure: the sources say both "once meses" and "12 meses". Use the
   dated range (May 2023 – May 2024) and state the achievement without a
   contradicting duration.
3. The `portfolio-chatbot` project describes the **real** architecture. The
   sources claim Azure AI Search and 1200/150 chunking; neither is true.
4. Add the three projects that are live on the site but absent from the sources:
   `laliga-dashboard`, `credit-scoring`, `product-recommender`.
5. Grades and honours become structured `grades:` entries, not prose — this is
   what lets Block B delete them from the system prompt.

- [ ] **Step 1: Write the file**
- [ ] **Step 2: Validate it**

Run: `.venv/bin/pytest tests/test_profile_schema.py -v`
Expected: 8 passed

- [ ] **Step 3: Cross-check nothing was lost**

Run a diff script that extracts every proper noun, number and year from the three
`.docx` files and reports any that appear in none of the YAML values. Every
report must be either present in the YAML or a deliberate drop (a falsehood from
correction 3, or duplicated text from correction 1).

- [ ] **Step 4: Commit**

```bash
git add data/profile.yml .gitignore
git commit -m "feat(kb): author profile.yml as the single source of truth"
```

---

### Task 3: KB generator

**Files:**
- Create: `scripts/build_kb.py`
- Create: `tests/test_build_kb.py`

**Interfaces:**
- Consumes: `load_profile`, `Profile` from Task 1; `data/profile.yml` from Task 2.
- Produces:
  - `build(profile: Profile, out_dir: Path, frontend_dir: Path) -> BuildResult`
  - `BuildResult` — dataclass with `documents: list[Path]`, `vocabulary_size: int`.
  - `render_entity(entity, category: str) -> str` — one entity to Markdown with
    frontmatter. Pure, no I/O, so it is unit-testable.
  - CLI: `python scripts/build_kb.py [--check]`. `--check` validates and reports
    without writing, for CI.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build_kb.py
import json
from scripts.build_kb import build, render_entity


def test_render_entity_emits_frontmatter_with_id_and_category(sample_role):
    md = render_entity(sample_role, "role")
    assert md.startswith("---\n")
    assert "id: role:data-equity" in md
    assert "category: role" in md


def test_build_is_deterministic(real_profile, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    fa, fb = tmp_path / "fa", tmp_path / "fb"
    build(real_profile, a, fa)
    build(real_profile, b, fb)
    for pa in sorted(a.rglob("*")):
        if pa.is_file():
            assert pa.read_bytes() == (b / pa.relative_to(a)).read_bytes()


def test_build_emits_one_document_per_entity(real_profile, tmp_path):
    result = build(real_profile, tmp_path / "kb", tmp_path / "fe")
    assert len(result.documents) == len(real_profile.entity_ids())


def test_no_document_is_empty(real_profile, tmp_path):
    result = build(real_profile, tmp_path / "kb", tmp_path / "fe")
    for doc in result.documents:
        body = doc.read_text().split("---", 2)[-1]
        assert body.strip(), f"{doc.name} has no body"


def test_vocabulary_excludes_terms_not_in_profile(real_profile, tmp_path):
    build(real_profile, tmp_path / "kb", tmp_path / "fe")
    vocab = json.loads((tmp_path / "kb" / "vocabulary.json").read_text())
    assert "MongoDB" not in vocab
    assert "MLOps" not in vocab
    assert "Data Equity" in vocab


def test_build_writes_frontend_profile_json(real_profile, tmp_path):
    build(real_profile, tmp_path / "kb", tmp_path / "fe")
    data = json.loads((tmp_path / "fe" / "profile.json").read_text())
    assert len(data["certifications"]) == 6
    assert data["skills"]


def test_build_is_atomic_on_failure(real_profile, tmp_path, monkeypatch):
    out = tmp_path / "kb"
    monkeypatch.setattr("scripts.build_kb._write_vocabulary", _boom)
    with pytest.raises(RuntimeError):
        build(real_profile, out, tmp_path / "fe")
    assert not out.exists(), "partial KB was left behind"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_build_kb.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.build_kb'`

- [ ] **Step 3: Implement the generator**

Determinism comes from sorting every collection before rendering and from
`json.dump(..., sort_keys=True, indent=2)`. Atomicity comes from building into
`out_dir.parent / f".{out_dir.name}.tmp"` and `os.replace`-ing it into position
only after every write succeeds.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_build_kb.py -v`
Expected: all pass

- [ ] **Step 5: Generate and inspect the real corpus**

Run: `.venv/bin/python scripts/build_kb.py`
Expected: ~50 documents, printed count and vocabulary size. Read three of them
by hand to confirm they read as coherent prose, not as dumped YAML.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_kb.py tests/test_build_kb.py frontend/public/data/profile.json
git commit -m "feat(kb): generate RAG corpus, vocabulary and frontend profile.json"
```

---

### Task 4: Point the indexer at the generated corpus

**Files:**
- Modify: `scripts/index_documents.py`
- Modify: `documentos/` → move the three `.docx` into `documentos/legacy/`

**Interfaces:**
- Consumes: `data/kb/*.md` from Task 3.
- Produces: `embeddings_cache.json` built from Markdown rather than `.docx`.

Note: the embedding **model change** to `gemini-embedding-2` belongs to Block B,
not here. This task only changes the input source, so the two changes stay
independently revertable.

- [ ] **Step 1: Replace `extract_docx` with `extract_markdown`**

Frontmatter is parsed out and its `id` becomes the chunk `source`, replacing the
current filename-based source. This is what makes Block B's `get_entity(id)`
addressable.

- [ ] **Step 2: Drop the chunking**

Entity documents are already the right retrieval unit and each is well under the
8,192-token input limit. Chunking them again would recreate the duplication
problem the block exists to remove. One document, one embedding.

- [ ] **Step 3: Archive the `.docx` sources**

```bash
mkdir -p documentos/legacy && git mv --force documentos/*.docx documentos/legacy/ 2>/dev/null || mv documentos/*.docx documentos/legacy/
```

- [ ] **Step 4: Verify no script still reads `.docx`**

Run: `grep -rn "docx" scripts/ backend/ --include=*.py`
Expected: only `documentos/legacy` references, or none.

- [ ] **Step 5: Commit**

```bash
git add scripts/index_documents.py
git commit -m "refactor(kb): index the generated corpus instead of .docx files"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `data/profile.yml` schema | 1, 2 |
| Deduplicate the three `.docx` | 2 (correction 1) |
| Fix MyES contradiction | 2 (correction 2) |
| Correct the self-description | 2 (correction 3) |
| Add the three missing projects | 2 (correction 4) |
| Structured grades | 2 (correction 5) |
| `build_kb.py` → entity documents | 3 |
| `vocabulary.json` for Block B | 3 |
| `profile.json` for the frontend | 3 |
| Schema validation, referential integrity, uniqueness, one current role | 1 |
| Atomic non-destructive output | 3 |
| Determinism | 3 |
| Certification images resolve | 3 (add to `test_build_writes_frontend_profile_json`) |
| Archive `.docx` to `legacy/` | 4 |

Gap found and closed: the spec requires every `certifications[].image` to resolve
to a real file; folded into Task 3's frontend test rather than a separate task,
since it needs the same fixture.

**Type consistency:** `load_profile` / `Profile` / `ProfileError` are named
identically in Tasks 1–4. `build(profile, out_dir, frontend_dir)` keeps the same
three-argument signature everywhere it appears. `render_entity(entity, category)`
is consistent between its definition and its test.

**Note on `Certificaciones.jsx`:** consuming `profile.json` is Block C's work,
not this plan's — Task 3 only produces the file. Recorded here so the dependency
is not lost.
