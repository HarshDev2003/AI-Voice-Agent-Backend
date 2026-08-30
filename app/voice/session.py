"""In-memory call session state.

Each active phone call gets a :class:`CallSession` that lives for the
duration of the call. A simple :class:`SessionStore` provides a
process-wide registry keyed by ``call_sid`` so any code path (the media
stream WebSocket, the post-call pipeline, etc.) can look it up.

This is intentionally a process-local cache: Supabase is the source of
truth for persisted call data (added in Phase 6).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turn:
    """A single transcript turn (caller or assistant)."""

    role: str  # "user" (caller) or "assistant"
    text: str
    timestamp: float = field(default_factory=time.time)

    def to_message(self) -> dict[str, Any]:
        """Return the OpenAI chat-completions message shape."""
        return {"role": self.role, "content": self.text}


@dataclass
class CallSession:
    """Mutable state for one active call.

    Holds the full conversation history and a transcript buffer used by
    the post-call pipeline. A turn-lock guard serialises LLM calls so
    overlapping STT finals don't trigger concurrent reasoning.
    """

    call_sid: str
    caller_number: str = ""
    started_at: float = field(default_factory=time.time)
    history: list[Turn] = field(default_factory=list)
    transcript_buffer: list[str] = field(default_factory=list)
    status: str = "active"  # "active" | "transferred" | "completed"
    _turn_lock: threading.Lock = field(default_factory=threading.Lock)

    def add_user_turn(self, text: str) -> None:
        """Append a caller transcript to the history."""
        self.history.append(Turn(role="user", text=text))

    def add_assistant_turn(self, text: str) -> None:
        """Append an agent reply to the history."""
        self.history.append(Turn(role="assistant", text=text))

    def messages(self, system_prompt: str) -> list[dict[str, Any]]:
        """Build the OpenAI chat messages list (system + history)."""
        return [{"role": "system", "content": system_prompt}, *(
            t.to_message() for t in self.history
        )]

    def acquire_turn(self) -> "_TurnGuard":
        """Return a context manager that serialises a single agent turn."""
        return _TurnGuard(self._turn_lock)


class _TurnGuard:
    """Tiny ``with`` wrapper around :class:`threading.Lock`."""

    def __init__(self, lock: threading.Lock) -> None:
        self._lock = lock

    def __enter__(self) -> "_TurnGuard":
        self._lock.acquire()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._lock.release()


class SessionStore:
    """Process-wide registry of active call sessions, keyed by ``call_sid``."""

    def __init__(self) -> None:
        self._sessions: dict[str, CallSession] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self, call_sid: str, caller_number: str = ""
    ) -> CallSession:
        """Return the session for ``call_sid``, creating it if needed."""
        with self._lock:
            session = self._sessions.get(call_sid)
            if session is None:
                session = CallSession(
                    call_sid=call_sid, caller_number=caller_number
                )
                self._sessions[call_sid] = session
            elif caller_number and not session.caller_number:
                session.caller_number = caller_number
            return session

    def get(self, call_sid: str) -> CallSession | None:
        """Return the session for ``call_sid`` or ``None`` if missing."""
        with self._lock:
            return self._sessions.get(call_sid)

    def remove(self, call_sid: str) -> CallSession | None:
        """Remove and return the session, or ``None`` if it didn't exist."""
        with self._lock:
            return self._sessions.pop(call_sid, None)

    def active_count(self) -> int:
        """Number of sessions currently held in memory."""
        with self._lock:
            return len(self._sessions)


# Process-wide singleton used by routers/services.
session_store = SessionStore()
