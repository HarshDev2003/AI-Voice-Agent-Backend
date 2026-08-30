"""Persistence layer for call records (Phase 6).

Mirrors the schema in ``docs/Ai-Voice-MVP.md`` section 7:

* ``calls``            - one row per call (metadata)
* ``call_transcripts`` - full transcript + structured turns (JSONB)
* ``call_summaries``   - LLM-generated summary + caller intent + actions

Two implementations are provided:

* :class:`InMemoryCallsRepository` - dict-backed, used by the test suite.
* :class:`SupabaseCallsRepository` - real one, used in production / staging.

Both implementations are idempotent on writes keyed by ``call_sid`` so a
duplicate Twilio status callback (which is normal) does not double-write.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Iterable

logger = logging.getLogger(__name__)


class CallsRepository(ABC):
    """Abstract persistence interface for call records."""

    @abstractmethod
    def insert_call(
        self,
        *,
        call_sid: str,
        caller_number: str = "",
        status: str = "active",
        started_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a new call row. Idempotent on ``call_sid``."""

    @abstractmethod
    def update_call_status(
        self,
        call_sid: str,
        *,
        status: str,
        ended_at: datetime | None = None,
        duration_seconds: int | None = None,
        transferred_to: str | None = None,
    ) -> dict[str, Any] | None:
        """Update an existing call. Returns the row, or ``None`` if missing."""

    @abstractmethod
    def insert_transcript(
        self,
        *,
        call_sid: str,
        transcript: str,
        turns: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Store the transcript. Idempotent on ``call_sid``."""

    @abstractmethod
    def insert_summary(
        self,
        *,
        call_sid: str,
        summary: str,
        caller_intent: str = "",
        action_items: list[str] | None = None,
        sentiment: str = "neutral",
    ) -> dict[str, Any] | None:
        """Store the post-call summary. Idempotent on ``call_sid``."""

    @abstractmethod
    def get_call_by_sid(self, call_sid: str) -> dict[str, Any] | None:
        """Return a call row enriched with its transcript + summary, or ``None``."""

    @abstractmethod
    def list_recent_calls(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent calls, newest first."""


# ---------------------------------------------------------------------------
# In-memory implementation (for tests / dev without Supabase)
# ---------------------------------------------------------------------------


class InMemoryCallsRepository(CallsRepository):
    """Simple dict-backed repository used by the test suite."""

    def __init__(self) -> None:
        self._calls: dict[str, dict[str, Any]] = {}
        self._transcripts: dict[str, dict[str, Any]] = {}
        self._summaries: dict[str, dict[str, Any]] = {}

    def insert_call(
        self,
        *,
        call_sid: str,
        caller_number: str = "",
        status: str = "active",
        started_at: datetime | None = None,
    ) -> dict[str, Any]:
        if call_sid in self._calls:
            return self._calls[call_sid]
        row = {
            "id": f"id-{call_sid}",
            "call_sid": call_sid,
            "caller_number": caller_number,
            "status": status,
            "started_at": (started_at or datetime.now(timezone.utc)).isoformat(),
            "ended_at": None,
            "duration_seconds": None,
            "transferred_to": None,
        }
        self._calls[call_sid] = row
        return row

    def update_call_status(
        self,
        call_sid: str,
        *,
        status: str,
        ended_at: datetime | None = None,
        duration_seconds: int | None = None,
        transferred_to: str | None = None,
    ) -> dict[str, Any] | None:
        row = self._calls.get(call_sid)
        if row is None:
            return None
        row["status"] = status
        if ended_at is not None:
            row["ended_at"] = ended_at.isoformat()
        if duration_seconds is not None:
            row["duration_seconds"] = duration_seconds
        if transferred_to is not None:
            row["transferred_to"] = transferred_to
        return row

    def insert_transcript(
        self,
        *,
        call_sid: str,
        transcript: str,
        turns: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if call_sid not in self._calls:
            return None
        if call_sid in self._transcripts:
            return self._transcripts[call_sid]
        row = {
            "id": f"t-{call_sid}",
            "call_id": self._calls[call_sid]["id"],
            "call_sid": call_sid,
            "transcript": transcript,
            "turns": turns,
        }
        self._transcripts[call_sid] = row
        return row

    def insert_summary(
        self,
        *,
        call_sid: str,
        summary: str,
        caller_intent: str = "",
        action_items: list[str] | None = None,
        sentiment: str = "neutral",
    ) -> dict[str, Any] | None:
        if call_sid not in self._calls:
            return None
        if call_sid in self._summaries:
            return self._summaries[call_sid]
        row = {
            "id": f"s-{call_sid}",
            "call_id": self._calls[call_sid]["id"],
            "call_sid": call_sid,
            "summary": summary,
            "caller_intent": caller_intent,
            "action_items": action_items or [],
            "sentiment": sentiment,
        }
        self._summaries[call_sid] = row
        return row

    def get_call_by_sid(self, call_sid: str) -> dict[str, Any] | None:
        call = self._calls.get(call_sid)
        if call is None:
            return None
        return {
            **call,
            "transcript": self._transcripts.get(call_sid),
            "summary": self._summaries.get(call_sid),
        }

    def list_recent_calls(self, limit: int = 20) -> list[dict[str, Any]]:
        rows: Iterable[dict[str, Any]] = sorted(
            self._calls.values(),
            key=lambda r: r.get("started_at") or "",
            reverse=True,
        )
        return [self.get_call_by_sid(r["call_sid"]) for r in rows[:limit]]

# ---------------------------------------------------------------------------
# Supabase implementation
# ---------------------------------------------------------------------------


def _row(data: Any) -> dict[str, Any] | None:
    """Normalise a single Supabase response row."""
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


class SupabaseCallsRepository(CallsRepository):
    """Supabase/PostgreSQL-backed repository (production)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def insert_call(
        self,
        *,
        call_sid: str,
        caller_number: str = "",
        status: str = "active",
        started_at: datetime | None = None,
    ) -> dict[str, Any]:
        existing = self.get_call_by_sid(call_sid)
        if existing is not None:
            return existing
        row = {
            "call_sid": call_sid,
            "caller_number": caller_number,
            "status": status,
            "started_at": (started_at or datetime.now(timezone.utc)).isoformat(),
        }
        response = self._client.table("calls").insert(row).execute()
        return _row(response.data) or row

    def update_call_status(
        self,
        call_sid: str,
        *,
        status: str,
        ended_at: datetime | None = None,
        duration_seconds: int | None = None,
        transferred_to: str | None = None,
    ) -> dict[str, Any] | None:
        patch: dict[str, Any] = {"status": status}
        if ended_at is not None:
            patch["ended_at"] = ended_at.isoformat()
        if duration_seconds is not None:
            patch["duration_seconds"] = duration_seconds
        if transferred_to is not None:
            patch["transferred_to"] = transferred_to
        response = (
            self._client.table("calls")
            .update(patch)
            .eq("call_sid", call_sid)
            .execute()
        )
        return _row(response.data)

    def insert_transcript(
        self,
        *,
        call_sid: str,
        transcript: str,
        turns: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        call = self.get_call_by_sid(call_sid)
        if call is None:
            logger.warning("insert_transcript: unknown call_sid=%s", call_sid)
            return None
        existing = (
            self._client.table("call_transcripts")
            .select("id")
            .eq("call_sid", call_sid)
            .limit(1)
            .execute()
        )
        if _row(existing.data) is not None:
            return _row(existing.data)
        row = {
            "call_id": call["id"],
            "call_sid": call_sid,
            "transcript": transcript,
            "turns": turns,
        }
        response = self._client.table("call_transcripts").insert(row).execute()
        return _row(response.data) or row


    def insert_summary(
        self,
        *,
        call_sid: str,
        summary: str,
        caller_intent: str = "",
        action_items: list[str] | None = None,
        sentiment: str = "neutral",
    ) -> dict[str, Any] | None:
        call = self.get_call_by_sid(call_sid)
        if call is None:
            logger.warning("insert_summary: unknown call_sid=%s", call_sid)
            return None
        existing = (
            self._client.table("call_summaries")
            .select("id")
            .eq("call_sid", call_sid)
            .limit(1)
            .execute()
        )
        if _row(existing.data) is not None:
            return _row(existing.data)
        row = {
            "call_id": call["id"],
            "call_sid": call_sid,
            "summary": summary,
            "caller_intent": caller_intent,
            "action_items": action_items or [],
            "sentiment": sentiment,
        }
        response = self._client.table("call_summaries").insert(row).execute()
        return _row(response.data) or row

    def get_call_by_sid(self, call_sid: str) -> dict[str, Any] | None:
        response = (
            self._client.table("calls")
            .select("*, call_transcripts(*), call_summaries(*)")
            .eq("call_sid", call_sid)
            .limit(1)
            .execute()
        )
        call = _row(response.data)
        if call is None:
            return None
        transcripts = call.pop("call_transcripts", None) or []
        summaries = call.pop("call_summaries", None) or []
        call["transcript"] = transcripts[0] if transcripts else None
        call["summary"] = summaries[0] if summaries else None
        return call

    def list_recent_calls(self, limit: int = 20) -> list[dict[str, Any]]:
        response = (
            self._client.table("calls")
            .select("*, call_transcripts(*), call_summaries(*)")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data or []
        for row in rows:
            transcripts = row.pop("call_transcripts", None) or []
            summaries = row.pop("call_summaries", None) or []
            row["transcript"] = transcripts[0] if transcripts else None
            row["summary"] = summaries[0] if summaries else None
        return rows


def build_calls_repository(settings: Any) -> CallsRepository:
    """Build a repository from application settings.

    Returns an :class:`InMemoryCallsRepository` when Supabase isn't
    configured, so dev / test runs can still hit ``GET /calls`` without
    needing the real database.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.info("Supabase not configured; using in-memory call repository")
        return InMemoryCallsRepository()
    try:
        from supabase import create_client  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "supabase package is required for SupabaseCallsRepository"
        ) from exc
    client = create_client(
        settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
    )
    return SupabaseCallsRepository(client)


