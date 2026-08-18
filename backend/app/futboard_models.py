"""Request and response shapes for FUTBOARD.

Kept out of `models.py`, which owns the chat contract, because the two have
nothing to do with each other and the chat models are load-bearing for the
frontend's SSE parsing.

Every bound here is deliberate. Writes are open — there is no access code — so
validation is the first line of defence and the store's global caps are the
second. A field with no maximum is a field someone can use to fill the database.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# One place for the limits, so the API, the store and the tests cannot disagree.
MAX_NAME_LENGTH = 40
MAX_ROSTER_PER_SIDE = 30
MAX_GOALS_PER_MATCH = 60
MAX_HALF_MINUTES = 60
MAX_SUB_INTERVAL_MINUTES = 30


class _Named(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)

    @field_validator("name")
    @classmethod
    def _clean(cls, value: str) -> str:
        """Collapse whitespace and reject names that are only punctuation.

        Without this, ' ' and '   ' are two different teams, and so are 'Los
        Pibes' and 'Los  Pibes'.
        """
        collapsed = " ".join(value.split())
        if not collapsed:
            raise ValueError("name cannot be blank")
        if not any(ch.isalnum() for ch in collapsed):
            raise ValueError("name must contain at least one letter or digit")
        return collapsed


class TeamCreate(_Named):
    pass


class PlayerCreate(_Named):
    # Optional, because a player can be registered straight into a squad or on
    # their own and added to one later.
    team_id: int | None = Field(default=None, ge=1)


class RosterChange(BaseModel):
    player_id: int = Field(..., ge=1)


class GoalInput(BaseModel):
    """One goal. `player_id` is null when nobody recorded who scored.

    That is the normal case, not an error state: the team's score has to be
    right even when the scorer is unknown, so every goal is a row and the
    attribution is optional.
    """

    team_id: int = Field(..., ge=1)
    player_id: int | None = Field(default=None, ge=1)
    half: int = Field(..., ge=1, le=2)
    minute: int = Field(..., ge=0, le=MAX_HALF_MINUTES * 2)


class MatchCreate(BaseModel):
    home_team_id: int = Field(..., ge=1)
    away_team_id: int = Field(..., ge=1)
    half_minutes: int = Field(..., ge=1, le=MAX_HALF_MINUTES)
    sub_interval_minutes: int = Field(..., ge=1, le=MAX_SUB_INTERVAL_MINUTES)
    home_player_ids: list[int] = Field(default_factory=list, max_length=MAX_ROSTER_PER_SIDE)
    away_player_ids: list[int] = Field(default_factory=list, max_length=MAX_ROSTER_PER_SIDE)
    goals: list[GoalInput] = Field(default_factory=list, max_length=MAX_GOALS_PER_MATCH)

    @field_validator("away_team_id")
    @classmethod
    def _distinct_teams(cls, value: int, info) -> int:
        if info.data.get("home_team_id") == value:
            raise ValueError("a team cannot play itself")
        return value

    @field_validator("home_player_ids", "away_player_ids")
    @classmethod
    def _no_duplicates(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("a player cannot be listed twice on the same side")
        return value


# ── responses ───────────────────────────────────────────────────────────────


class Team(BaseModel):
    id: int
    name: str
    player_count: int = 0


class Player(BaseModel):
    id: int
    name: str
    team_ids: list[int] = Field(default_factory=list)


class MatchGoal(BaseModel):
    team_id: int
    player_id: int | None
    player_name: str | None
    half: int
    minute: int


class Match(BaseModel):
    id: int
    played_at: datetime
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_goals: int
    away_goals: int
    half_minutes: int
    sub_interval_minutes: int
    goals: list[MatchGoal] = Field(default_factory=list)


class PlayerStats(BaseModel):
    player_id: int
    name: str
    matches: int
    goals: int
    goals_per_match: float
    teams: list[str] = Field(default_factory=list)


class TeamStats(BaseModel):
    team_id: int
    name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int


class Stats(BaseModel):
    players: list[PlayerStats] = Field(default_factory=list)
    teams: list[TeamStats] = Field(default_factory=list)
