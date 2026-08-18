"""FUTBOARD endpoints.

Reads are open and writes are open — there is no access code, by choice. The
protection is therefore entirely server-side: a per-IP write ceiling here, field
bounds in `futboard_models`, and global row caps in the store. `created_ip` is
recorded on every write so a spam wave can be undone with one statement, and it
is never returned to a client.

The route layer does no SQL and no business rules. It rate-limits, hands the
validated model to the store, and turns `FutboardError` into a status code.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.futboard_models import (
    Match,
    MatchCreate,
    Player,
    PlayerCreate,
    RosterChange,
    Stats,
    Team,
    TeamCreate,
)
from app.services.futboard_store import FutboardError, FutboardStore
from app.services.guards import RequestGuards

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/futboard", tags=["futboard"])

store = FutboardStore(
    settings.futboard_database_url,
    max_teams=settings.futboard_max_teams,
    max_players=settings.futboard_max_players,
)

# Only `enforce_rate_limit` is used. RequestGuards also carries a token budget,
# which is a chat concept with no meaning here, so it is given a zero it will
# never be asked about rather than a misleading number.
write_guard = RequestGuards(
    per_minute_limit=settings.futboard_max_writes_per_minute_per_ip,
    daily_token_limit=0,
)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _require_available() -> None:
    if not store.available:
        raise HTTPException(
            status_code=503,
            detail="FUTBOARD is not configured on this deployment.",
        )


def _guard_write(request: Request) -> str:
    _require_available()
    client_ip = _client_ip(request)
    decision = write_guard.enforce_rate_limit(client_ip)
    if not decision.allowed:
        raise HTTPException(status_code=429, detail=decision.message)
    return client_ip


def _run(operation, *args, **kwargs):
    """Call the store, mapping its errors onto HTTP.

    Anything unexpected becomes a 503 rather than a 500: the overwhelming cause
    is Neon waking up or briefly unreachable, and that is a "try again in a
    moment", not a bug in the request.
    """
    try:
        return operation(*args, **kwargs)
    except FutboardError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # pragma: no cover - depends on the network
        logger.error("FUTBOARD store failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="The FUTBOARD database is unavailable. Try again in a moment.",
        ) from exc


@router.get("/health")
def health() -> dict[str, bool]:
    """Also the keepalive target for the weekly workflow."""
    if not store.available:
        return {"configured": False, "reachable": False}
    try:
        store.health()
        return {"configured": True, "reachable": True}
    except Exception as exc:
        logger.warning("FUTBOARD health check failed: %s", exc)
        return {"configured": True, "reachable": False}


# ── teams and players ───────────────────────────────────────────────────────


@router.get("/teams", response_model=list[Team])
def list_teams() -> list[Team]:
    _require_available()
    return _run(store.list_teams)


@router.post("/teams", response_model=Team, status_code=201)
def create_team(payload: TeamCreate, request: Request) -> Team:
    client_ip = _guard_write(request)
    return _run(store.create_team, payload.name, client_ip)


@router.get("/players", response_model=list[Player])
def list_players() -> list[Player]:
    _require_available()
    return _run(store.list_players)


@router.post("/players", response_model=Player, status_code=201)
def create_player(payload: PlayerCreate, request: Request) -> Player:
    client_ip = _guard_write(request)
    return _run(store.create_player, payload.name, payload.team_id, client_ip)


@router.post("/teams/{team_id}/players", status_code=204)
def add_player_to_team(team_id: int, payload: RosterChange, request: Request) -> None:
    _guard_write(request)
    _run(store.add_player_to_team, team_id, payload.player_id)


@router.delete("/teams/{team_id}/players/{player_id}", status_code=204)
def remove_player_from_team(team_id: int, player_id: int, request: Request) -> None:
    _guard_write(request)
    _run(store.remove_player_from_team, team_id, player_id)


# ── matches and statistics ──────────────────────────────────────────────────


@router.post("/matches", status_code=201)
def create_match(payload: MatchCreate, request: Request) -> dict[str, int]:
    client_ip = _guard_write(request)
    return {"id": _run(store.save_match, payload, client_ip)}


@router.get("/matches", response_model=list[Match])
def list_matches(limit: int = 20) -> list[Match]:
    _require_available()
    return _run(store.list_matches, max(1, min(limit, 100)))


@router.get("/stats", response_model=Stats)
def stats() -> Stats:
    _require_available()
    return _run(store.stats)
