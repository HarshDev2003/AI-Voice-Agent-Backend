"""Agent turn function.

This module is *pure* from a business-logic perspective: it accepts an
``LLMProvider`` and a :class:`CallSession`, asks the model for a reply,
classifies the intent, and returns an :class:`AgentResult`. No I/O of its
own — the WebSocket handler in Phase 5 is responsible for plumbing
audio/TTS, and Phase 6 persists the outcome.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agent.intent import Intent, clean_response, detect_intent
from app.agent.prompts import SYSTEM_PROMPT
from app.llm.base import LLMProvider
from app.voice.session import CallSession

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """The outcome of a single agent turn.

    ``response_text`` is the *cleaned* reply (control tokens stripped),
    ready to send to TTS. ``should_transfer`` / ``should_end`` are derived
    from ``intent`` for the caller's convenience.
    """

    response_text: str
    intent: Intent

    @property
    def should_transfer(self) -> bool:
        return self.intent is Intent.TRANSFER

    @property
    def should_end(self) -> bool:
        return self.intent is Intent.END


async def run_turn(
    session: CallSession, user_text: str, llm: LLMProvider
) -> AgentResult:
    """Run one agent turn for ``user_text`` and update ``session``.

    The caller is responsible for any turn-level concurrency control
    (use :meth:`CallSession.acquire_turn`). The session's history is
    mutated in place: the user message is appended, the assistant reply
    is appended after the LLM responds.
    """
    if not user_text or not user_text.strip():
        # Nothing to reason about — treat as a no-op so the call stays open.
        return AgentResult(response_text="", intent=Intent.CHAT)

    session.add_user_turn(user_text)
    messages = session.messages(SYSTEM_PROMPT)

    raw = await llm.chat(messages)
    intent = detect_intent(raw)
    spoken = clean_response(raw)

    session.add_assistant_turn(spoken or raw)
    session.transcript_buffer.append(f"caller: {user_text}")
    session.transcript_buffer.append(f"assistant: {spoken or raw}")

    logger.info(
        "agent turn call_sid=%s intent=%s reply_len=%d",
        session.call_sid,
        intent.value,
        len(spoken),
    )
    return AgentResult(response_text=spoken, intent=intent)
