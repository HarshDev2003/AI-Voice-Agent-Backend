"""Post-call pipeline (Phase 6).

Triggered by the Twilio status webhook when a call ends. The pipeline:

1. Looks up the in-memory :class:`CallSession` to get the transcript.
2. Asks the LLM to summarise the call (using the post-call prompt).
3. Parses the LLM JSON (lenient: extracts JSON even from prose).
4. Persists call metadata + transcript + summary via the repository.
5. Marks the call's terminal status (``completed`` / ``transferred``).
6. Removes the in-memory session.

The whole thing is idempotent on ``call_sid`` so a duplicate Twilio
status callback (which Twilio often sends) doesn't double-write.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.agent.prompts import build_post_call_prompt
from app.calls.repository import CallsRepository
from app.llm.base import LLMProvider
from app.voice.session import CallSession, session_store

logger = logging.getLogger(__name__)


# Status values reported by Twilio that we treat as "call ended".
TERMINAL_STATUSES = {"completed", "failed", "busy", "no-answer", "canceled"}


def parse_summary_json(text: str) -> dict[str, Any]:
    """Parse the LLM's post-call summary response.

    The model is asked to return strict JSON, but may occasionally wrap it
    in markdown code fences or add a leading explanation. This helper
    extracts the first JSON object from ``text`` and returns it, falling
    back to a minimal shape if nothing parseable is found.
    """
    if not text:
        return {
            "summary": "",
            "caller_intent": "",
            "action_items": [],
            "sentiment": "neutral",
        }
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return _normalise_summary(obj)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return _normalise_summary(obj)
        except json.JSONDecodeError:
            pass
    return {
        "summary": text,
        "caller_intent": "",
        "action_items": [],
        "sentiment": "neutral",
    }


def _normalise_summary(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(obj.get("summary") or "").strip(),
        "caller_intent": str(obj.get("caller_intent") or "").strip(),
        "action_items": [
            str(a).strip() for a in (obj.get("action_items") or []) if str(a).strip()
        ],
        "sentiment": str(obj.get("sentiment") or "neutral").strip().lower() or "neutral",
    }

async def run_post_call(
    call_sid: str,
    *,
    call_status: str = "completed",
    repository: CallsRepository,
    llm: LLMProvider,
) -> dict[str, Any] | None:
    """Run the post-call pipeline for ``call_sid``.

    Returns the final call row (or ``None`` if the call is unknown).
    """
    session = session_store.get(call_sid)
    if session is None:
        logger.info("post_call: no session for %s, skipping", call_sid)
        return None

    started_at = datetime.fromtimestamp(session.started_at, timezone.utc)
    ended_at = datetime.now(timezone.utc)
    duration = max(0, int((ended_at - started_at).total_seconds()))
    final_status = (
        "transferred"
        if session.status == "transferred"
        else ("completed" if call_status in TERMINAL_STATUSES else call_status)
    )

    repository.insert_call(
        call_sid=call_sid,
        caller_number=session.caller_number,
        status=final_status,
        started_at=started_at,
    )

    transcript_text, turns = transcript_from_session(session)
    repository.insert_transcript(
        call_sid=call_sid, transcript=transcript_text, turns=turns
    )

    if transcript_text.strip():
        try:
            raw = await llm.chat(
                [
                    {"role": "system", "content": "You output only valid JSON."},
                    {
                        "role": "user",
                        "content": build_post_call_prompt(transcript_text),
                    },
                ]
            )
            summary_obj = parse_summary_json(raw)
        except Exception as exc:  # noqa: BLE001
            logger.exception("post_call: summary LLM call failed: %s", exc)
            summary_obj = {
                "summary": "Summary unavailable due to an internal error.",
                "caller_intent": "",
                "action_items": [],
                "sentiment": "neutral",
            }
    else:
        summary_obj = {
            "summary": "Call had no transcript.",
            "caller_intent": "",
            "action_items": [],
            "sentiment": "neutral",
        }
    repository.insert_summary(call_sid=call_sid, **summary_obj)

    repository.update_call_status(
        call_sid,
        status=final_status,
        ended_at=ended_at,
        duration_seconds=duration,
    )

    session_store.remove(call_sid)
    logger.info(
        "post_call: persisted call_sid=%s status=%s duration=%ss",
        call_sid,
        final_status,
        duration,
    )
    return repository.get_call_by_sid(call_sid)



def transcript_from_session(session: CallSession) -> tuple[str, list[dict[str, Any]]]:
    """Build the plain-text transcript and structured turns from a session."""
    lines: list[str] = []
    turns: list[dict[str, Any]] = []
    for t in session.history:
        role = "caller" if t.role == "user" else "assistant"
        lines.append(f"{role}: {t.text}")
        turns.append(
            {
                "role": role,
                "text": t.text,
                "timestamp": datetime.fromtimestamp(t.timestamp, timezone.utc).isoformat(),
            }
        )
    return "\n".join(lines), turns
