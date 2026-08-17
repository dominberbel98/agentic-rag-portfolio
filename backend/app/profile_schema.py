"""Schema and validation for `data/profile.yml`, the profile's single source of truth.

Everything downstream — the RAG corpus, the groundedness vocabulary, the
frontend's certification data — is generated from that file. This module owns
what counts as a valid profile; `scripts/build_kb.py` owns turning it into
artefacts. Nothing here does I/O beyond `load_profile`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, ClassVar

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

__all__ = [
    "Profile",
    "ProfileError",
    "load_profile",
    "Meta",
    "Role",
    "Education",
    "Project",
    "Certification",
    "Skills",
    "SpokenLanguage",
    "Grade",
    "Narrative",
]

# "2025" or "2025-10". Day precision is noise for a CV.
#
# YAML parses a bare `2016` as an int and `2016-10` as a string, so the same
# field arrives as two types depending on precision. Coerce rather than forcing
# the author to remember quotes — `start: 2016` is the natural thing to write.
_DATE_RE = r"^\d{4}(-(0[1-9]|1[0-2]))?$"


def _stringify_year(value: Any) -> Any:
    return str(value) if isinstance(value, int) else value


YearMonth = Annotated[str, BeforeValidator(_stringify_year), Field(pattern=_DATE_RE)]

NARRATIVE_KEYS = ("adaptability", "resilience", "teamwork", "career_change")


class ProfileError(Exception):
    """Raised when the profile cannot be read or fails validation."""


def _sortable(date: str | None, *, default: tuple[int, int]) -> tuple[int, int]:
    """Turn '2025' or '2025-10' into a comparable (year, month)."""
    if date is None:
        return default
    parts = date.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    return (year, month)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Meta(_Strict):
    name: str
    headline: str
    location: str
    emails: list[str] = Field(min_length=1)
    linkedin: str
    github: str


class Role(_Strict):
    id: str
    company: str
    title: str
    location: str
    start: YearMonth
    end: YearMonth | None = None
    summary: str
    achievements: list[str] = Field(default_factory=list)
    stack: list[str] = Field(default_factory=list)

    @property
    def is_current(self) -> bool:
        return self.end is None


class Grade(_Strict):
    subject: str
    score: float = Field(ge=0, le=10)
    distinction: str | None = None


class Education(_Strict):
    id: str
    institution: str
    degree: str
    start: YearMonth
    end: YearMonth | None = None
    location: str | None = None
    grades: list[Grade] = Field(default_factory=list)
    honours: list[str] = Field(default_factory=list)
    notes: str | None = None


class Project(_Strict):
    id: str
    name: str
    year: int = Field(ge=2010, le=2100)
    summary: str
    problem: str
    approach: str
    stack: list[str] = Field(default_factory=list)
    outcome: str
    repo: str | None = None
    live_url: str | None = None


class Certification(_Strict):
    id: str
    title: str
    issuer: str
    date: YearMonth
    expires: YearMonth | None = None
    image: str | None = None
    skills: list[str] = Field(default_factory=list)


class Skills(_Strict):
    """Technical skills. `programming` is languages-as-in-code; spoken languages
    live in `Profile.languages`, since they are asked about separately and often."""

    programming: list[str] = Field(default_factory=list)
    data: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    ml: list[str] = Field(default_factory=list)
    bi: list[str] = Field(default_factory=list)
    web: list[str] = Field(default_factory=list)

    CATEGORIES: ClassVar[tuple[str, ...]] = ("programming", "data", "cloud", "ml", "bi", "web")

    def all(self) -> set[str]:
        out: set[str] = set()
        for category in self.CATEGORIES:
            out |= set(getattr(self, category))
        return out


class SpokenLanguage(_Strict):
    language: str
    level: str
    evidence: str | None = None


class Narrative(_Strict):
    adaptability: str
    resilience: str
    teamwork: str
    career_change: str

    def items(self) -> list[tuple[str, str]]:
        return [(k, getattr(self, k)) for k in NARRATIVE_KEYS]


class Profile(_Strict):
    meta: Meta
    roles: list[Role] = Field(min_length=1)
    education: list[Education] = Field(min_length=1)
    projects: list[Project] = Field(min_length=1)
    certifications: list[Certification] = Field(default_factory=list)
    skills: Skills
    languages: list[SpokenLanguage] = Field(min_length=1)
    narrative: Narrative

    # --- cross-field rules --------------------------------------------------

    @model_validator(mode="after")
    def _check_consistency(self) -> Profile:
        problems: list[str] = []

        # Raw ids must be unique across *all* categories, not just within one.
        # The prefixed form is what retrieval addresses, but a human writing
        # `get_entity("data-equity")` should not have to know which category it
        # landed in, so reuse across categories is rejected too.
        seen: set[str] = set()
        raw_ids = (
            [r.id for r in self.roles]
            + [e.id for e in self.education]
            + [p.id for p in self.projects]
            + [c.id for c in self.certifications]
        )
        for raw in raw_ids:
            if raw in seen:
                problems.append(f"duplicate id: {raw}")
            seen.add(raw)

        current = [r for r in self.roles if r.is_current]
        if len(current) != 1:
            problems.append(
                f"exactly one current role (end: null) is required, found {len(current)}"
            )

        for role in self.roles:
            if role.end is not None and _sortable(role.end, default=(9999, 12)) < _sortable(
                role.start, default=(0, 0)
            ):
                problems.append(f"role {role.id} ends before it starts")
        for edu in self.education:
            if edu.end is not None and _sortable(edu.end, default=(9999, 12)) < _sortable(
                edu.start, default=(0, 0)
            ):
                problems.append(f"education {edu.id} ends before it starts")

        # Referential integrity: a stack entry that is not a declared skill is a
        # typo, and would otherwise create a skill that exists in only one place.
        known = self.skills.all()
        for role in self.roles:
            for tech in role.stack:
                if tech not in known:
                    problems.append(f"role {role.id} stack entry not in skills: {tech}")
        for project in self.projects:
            for tech in project.stack:
                if tech not in known:
                    problems.append(f"project {project.id} stack entry not in skills: {tech}")

        if problems:
            raise ProfileError("; ".join(problems))
        return self

    # --- construction -------------------------------------------------------

    @classmethod
    def from_mapping(cls, raw: Any, *, source: str = "profile") -> Profile:
        """Validate a mapping, reporting every failure as a `ProfileError`.

        Pydantic raises `ValidationError` for field-level problems while the
        cross-field validator raises `ProfileError`. Callers should not have to
        catch both, so this is the single entry point.
        """
        try:
            return cls.model_validate(raw)
        except ProfileError:
            raise
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            )
            raise ProfileError(f"{source} failed validation — {details}") from exc

    # --- derived views ------------------------------------------------------

    def current_role(self) -> Role:
        for role in self.roles:
            if role.is_current:
                return role
        raise ProfileError("no current role")  # unreachable after validation

    def entity_ids(self) -> list[str]:
        """Every retrievable entity, in document order.

        These are the addresses `get_entity(id)` resolves in the agent loop, so
        they must stay stable: renaming one invalidates the retrieval tests.
        """
        ids: list[str] = []
        ids += [f"role:{r.id}" for r in self.roles]
        ids += [f"education:{e.id}" for e in self.education]
        ids += [f"project:{p.id}" for p in self.projects]
        ids += [f"certification:{c.id}" for c in self.certifications]
        ids.append("languages:spoken")
        ids += [f"narrative:{key}" for key, _ in self.narrative.items()]
        return ids

    def vocabulary(self) -> set[str]:
        """Every proper noun the assistant is allowed to attribute to him.

        Block B's groundedness check treats anything outside this set, and
        outside the retrieved context, as a fabricated entity.
        """
        vocab: set[str] = set()
        vocab.add(self.meta.name)
        vocab |= self.skills.all()
        for role in self.roles:
            vocab.add(role.company)
            vocab.update(role.stack)
        for edu in self.education:
            vocab.add(edu.institution)
        for project in self.projects:
            vocab.add(project.name)
            vocab.update(project.stack)
        for cert in self.certifications:
            vocab.add(cert.title)
            vocab.add(cert.issuer)
            vocab.update(cert.skills)
        for lang in self.languages:
            vocab.add(lang.language)
        return {v for v in vocab if v}


def load_profile(path: Path | str) -> Profile:
    """Read and validate the profile, naming the offending field on failure."""
    path = Path(path)
    if not path.exists():
        raise ProfileError(f"profile not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ProfileError(f"{path} must contain a mapping at the top level")

    return Profile.from_mapping(raw, source=str(path))
