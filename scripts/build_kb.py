#!/usr/bin/env python3
"""Generate everything downstream of `data/profile.yml`.

    data/profile.yml
          ├──→ data/kb/*.md                       one document per entity, for retrieval
          ├──→ data/kb/vocabulary.json            allowed proper nouns, for groundedness
          └──→ frontend/public/data/profile.json  certifications + skills, for the UI

Usage:
    python scripts/build_kb.py            # validate and write
    python scripts/build_kb.py --check    # validate and report, write nothing

The rendered documents are what gets embedded and what the model reads, so they
are written as prose rather than dumped YAML — a key-value dump retrieves badly
and reads worse in an answer.

Generation is deterministic (same input, byte-identical output) and atomic
(builds into a temp directory and moves it into place only on full success), so
a failed run can never leave a half-written corpus for the backend to load.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
# `backend` on the path so this imports `app.profile_schema` — the same name the
# container uses. Importing it as `backend.app.profile_schema` here and `app.
# profile_schema` there would give two distinct module objects for one file.
for _path in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.profile_schema import (  # noqa: E402
    Certification,
    Education,
    Profile,
    ProfileError,
    Project,
    Role,
    load_profile,
)

DEFAULT_PROFILE = REPO_ROOT / "data" / "profile.yml"
DEFAULT_KB_DIR = REPO_ROOT / "data" / "kb"
DEFAULT_FRONTEND_DIR = REPO_ROOT / "frontend" / "public" / "data"

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass
class BuildResult:
    documents: list[Path] = field(default_factory=list)
    vocabulary_size: int = 0
    frontend_file: Path | None = None


# ── formatting helpers ──────────────────────────────────────────────────────


def format_date(value: str | None, *, fallback: str = "present") -> str:
    """'2025-10' → 'October 2025'; '2025' → '2025'; None → fallback."""
    if value is None:
        return fallback
    parts = value.split("-")
    if len(parts) == 1:
        return parts[0]
    return f"{_MONTHS[int(parts[1]) - 1]} {parts[0]}"


def format_date_short(value: str | None) -> str | None:
    """'2025-10' → 'Oct 2025'. The UI is dense by design; long months break it."""
    if value is None:
        return None
    parts = value.split("-")
    if len(parts) == 1:
        return parts[0]
    return f"{_MONTHS[int(parts[1]) - 1][:3]} {parts[0]}"


def _period(start: str, end: str | None) -> str:
    if end is None:
        return f"from {format_date(start)} to the present"
    return f"from {format_date(start)} to {format_date(end)}"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _slug(entity_id: str) -> str:
    """'role:data-equity' → 'role--data-equity' (a safe filename)."""
    return entity_id.replace(":", "--")


def _frontmatter(entity_id: str, category: str, title: str) -> str:
    # Hand-rolled rather than yaml.dump so key order is fixed and output is
    # byte-stable across PyYAML versions.
    safe_title = title.replace('"', "'")
    return f'---\nid: {entity_id}\ncategory: {category}\ntitle: "{safe_title}"\n---\n'


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a rendered document into its frontmatter mapping and its body."""
    if not text.startswith("---\n"):
        return {}, text
    _, raw, body = text.split("---\n", 2)
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, body


# ── per-category rendering ──────────────────────────────────────────────────


def _render_role(role: Role) -> tuple[str, str]:
    title = f"{role.title} at {role.company}"
    lines = [f"# {title}", ""]
    tense = "has been" if role.is_current else "was"
    current = " This is his current role." if role.is_current else ""
    lines.append(
        f"Domingo Berbel {tense} {role.title} at {role.company} in {role.location}, "
        f"{_period(role.start, role.end)}.{current}"
    )
    lines += ["", role.summary]
    if role.achievements:
        heading = "What he does in this role" if role.is_current else "What he did in this role"
        lines += ["", f"{heading}:", "", _bullets(role.achievements)]
    if role.stack:
        lines += ["", f"Technologies used in this role: {_join(role.stack)}."]
    return title, "\n".join(lines) + "\n"


def _render_education(edu: Education) -> tuple[str, str]:
    title = f"{edu.degree} — {edu.institution}"
    lines = [f"# {title}", ""]
    where = f" in {edu.location}" if edu.location else ""
    verb = "has been studying" if edu.end is None else "completed"
    lines.append(
        f"Domingo Berbel {verb} the {edu.degree} at {edu.institution}{where}, "
        f"{_period(edu.start, edu.end)}."
    )
    if edu.notes:
        lines += ["", edu.notes]
    if edu.grades:
        lines += ["", "Grades achieved:", ""]
        for grade in edu.grades:
            score = f"{grade.score:g}"
            distinction = f" — {grade.distinction}" if grade.distinction else ""
            lines.append(f"- {grade.subject}: {score} out of 10{distinction}")
    if edu.honours:
        lines += ["", "Honours and distinctions:", "", _bullets(edu.honours)]
    return title, "\n".join(lines) + "\n"


def _render_project(project: Project) -> tuple[str, str]:
    title = f"{project.name} ({project.year})"
    lines = [f"# {title}", "", project.summary]
    lines += ["", "The problem it addressed:", "", project.problem]
    lines += ["", "How he built it:", "", project.approach]
    lines += ["", "The outcome:", "", project.outcome]
    if project.stack:
        lines += ["", f"Technologies used: {_join(project.stack)}."]
    if project.repo:
        lines += ["", f"Source code: {project.repo}"]
    if project.live_url:
        lines.append(f"Live at: {project.live_url}")
    return title, "\n".join(lines) + "\n"


def _render_certification(cert: Certification) -> tuple[str, str]:
    title = f"{cert.title} — {cert.issuer}"
    lines = [f"# {title}", ""]
    validity = (
        f" It is valid until {format_date(cert.expires)}."
        if cert.expires
        else " It does not expire."
    )
    lines.append(
        f"Domingo Berbel earned the {cert.title} certification from {cert.issuer} "
        f"in {format_date(cert.date)}.{validity}"
    )
    if cert.skills:
        lines += ["", f"Skills covered by this certification: {_join(cert.skills)}."]
    return title, "\n".join(lines) + "\n"


def _render_languages(profile: Profile) -> tuple[str, str]:
    title = "Spoken languages"
    lines = [f"# {title}", "", "The languages Domingo Berbel speaks and at what level:", ""]
    for lang in profile.languages:
        lines.append(f"- {lang.language} — {lang.level}.")
    for lang in profile.languages:
        if lang.evidence:
            lines += ["", f"On his {lang.language}: {lang.evidence}"]
    return title, "\n".join(lines) + "\n"


def _render_narrative(key: str, text: str) -> tuple[str, str]:
    title = key.replace("_", " ").capitalize()
    return title, f"# {title}\n\n{text}\n"


# ── public rendering entry point ────────────────────────────────────────────


def render_entity(entity: Any, category: str) -> str:
    """Render one entity as a Markdown document with frontmatter.

    Pure: no I/O, so it is unit-testable on its own.
    """
    if category == "role":
        title, body = _render_role(entity)
        entity_id = f"role:{entity.id}"
    elif category == "education":
        title, body = _render_education(entity)
        entity_id = f"education:{entity.id}"
    elif category == "project":
        title, body = _render_project(entity)
        entity_id = f"project:{entity.id}"
    elif category == "certification":
        title, body = _render_certification(entity)
        entity_id = f"certification:{entity.id}"
    elif category == "languages":
        title, body = _render_languages(entity)
        entity_id = "languages:spoken"
    elif category == "narrative":
        key, text = entity
        title, body = _render_narrative(key, text)
        entity_id = f"narrative:{key}"
    else:
        raise ValueError(f"unknown category: {category}")

    return _frontmatter(entity_id, category, title) + "\n" + body


def iter_entities(profile: Profile) -> list[tuple[Any, str]]:
    """Every entity paired with its category, in document order."""
    out: list[tuple[Any, str]] = []
    out += [(r, "role") for r in profile.roles]
    out += [(e, "education") for e in profile.education]
    out += [(p, "project") for p in profile.projects]
    out += [(c, "certification") for c in profile.certifications]
    out.append((profile, "languages"))
    out += [(item, "narrative") for item in profile.narrative.items()]
    return out


# ── writing ─────────────────────────────────────────────────────────────────


def _write_vocabulary(profile: Profile, path: Path) -> int:
    vocab = sorted(profile.vocabulary())
    path.write_text(json.dumps(vocab, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(vocab)


def _frontend_payload(profile: Profile) -> dict[str, Any]:
    """Only what the UI actually renders. Not a dump of the whole profile."""
    return {
        "meta": {
            "name": profile.meta.name,
            "headline": profile.meta.headline,
            "location": profile.meta.location,
            "linkedin": profile.meta.linkedin,
            "github": profile.meta.github,
        },
        "certifications": [
            {
                "id": c.id,
                "title": c.title,
                "issuer": c.issuer,
                "date": format_date_short(c.date),
                "expires": format_date_short(c.expires),
                "image": c.image,
                "skills": list(c.skills),
            }
            for c in profile.certifications
        ],
        "skills": {category: list(getattr(profile.skills, category)) for category in profile.skills.CATEGORIES},
        "languages": [
            {"language": lang.language, "level": lang.level} for lang in profile.languages
        ],
    }


def build(profile: Profile, out_dir: Path, frontend_dir: Path) -> BuildResult:
    """Generate the corpus, the vocabulary and the frontend payload.

    Atomic: the corpus is assembled in a sibling temp directory and moved into
    place only once every write has succeeded.
    """
    out_dir = Path(out_dir)
    frontend_dir = Path(frontend_dir)
    tmp_dir = out_dir.parent / f".{out_dir.name}.tmp"

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    try:
        written: list[str] = []
        for entity, category in iter_entities(profile):
            text = render_entity(entity, category)
            entity_id = parse_frontmatter(text)[0]["id"]
            (tmp_dir / f"{_slug(entity_id)}.md").write_text(text, encoding="utf-8")
            written.append(_slug(entity_id))

        vocabulary_size = _write_vocabulary(profile, tmp_dir / "vocabulary.json")

        frontend_dir.mkdir(parents=True, exist_ok=True)
        frontend_file = frontend_dir / "profile.json"
        frontend_file.write_text(
            json.dumps(_frontend_payload(profile), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    # Swap in. rmtree-then-replace leaves a brief window with no corpus, which is
    # acceptable for a build step and avoids merging stale documents into a new run.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    os.replace(tmp_dir, out_dir)

    return BuildResult(
        documents=[out_dir / f"{name}.md" for name in written],
        vocabulary_size=vocabulary_size,
        frontend_file=frontend_dir / "profile.json",
    )


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--kb-dir", type=Path, default=DEFAULT_KB_DIR)
    parser.add_argument("--frontend-dir", type=Path, default=DEFAULT_FRONTEND_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate and report without writing anything (for CI)",
    )
    args = parser.parse_args(argv)

    try:
        profile = load_profile(args.profile)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    entities = iter_entities(profile)
    if args.check:
        print(f"{args.profile} is valid.")
        print(f"  entities:   {len(entities)}")
        print(f"  vocabulary: {len(profile.vocabulary())} terms")
        print(f"  current:    {profile.current_role().title} at {profile.current_role().company}")
        return 0

    result = build(profile, args.kb_dir, args.frontend_dir)
    print(f"wrote {len(result.documents)} documents to {args.kb_dir}")
    print(f"wrote {result.vocabulary_size} vocabulary terms")
    print(f"wrote {result.frontend_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
