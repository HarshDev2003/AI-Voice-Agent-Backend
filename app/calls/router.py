"""HTTP router for call records (Phase 6).

Exposes:

* ``GET /calls``              - list the most recent calls (with embedded
  transcript + summary if available).
* ``GET /calls/{call_sid}``   - fetch a single call by ``call_sid``.

There is no auth on these endpoints in the MVP. Phase 7 / V1 will
introduce it.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query, Request

from app.calls.repository import CallsRepository, build_calls_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["calls"])


@lru_cache
def _get_repository() -> CallsRepository:
    """Build the repository once per process.

    ``lru_cache`` is fine here because the function is pure (it only
    reads settings, which don't change at runtime). Tests bypass this by
    overriding the dependency below.
    """
    from app.core.config import get_settings

    return build_calls_repository(get_settings())


def get_repository(request: Request) -> CallsRepository:
    """FastAPI dependency: prefer an overridden repository (tests) if set."""
    repo: CallsRepository | None = getattr(request.app.state, "calls_repository", None)
    return repo or _get_repository()


@router.get("", summary="List recent calls")
async def list_calls(
    request: Request,
    limit: int = Query(20, ge=1, le=200),
) -> dict:
    """Return up to ``limit`` most recent calls (newest first)."""
    repo = get_repository(request)
    return {"calls": repo.list_recent_calls(limit=limit)}


@router.get("/{call_sid}", summary="Fetch a single call")
async def get_call(request: Request, call_sid: str) -> dict:
    """Return one call, its transcript and its summary."""
    repo = get_repository(request)
    row = repo.get_call_by_sid(call_sid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"call {call_sid!r} not found")
    return row
