"""Intent detection and response-text cleanup for the LLM.

The agent signals a control action by including a bracketed token
(``[TRANSFER]`` or ``[END_CALL]``) in its reply. ``detect_intent`` reads the
token; ``clean_response`` strips it from the text before it is sent to TTS.
"""
from __future__ import annotations

from enum import Enum


# Control tokens that the LLM embeds in its reply to drive call actions.
TRANSFER_TOKEN = "[TRANSFER]"
END_TOKEN = "[END_CALL]"


class Intent(str, Enum):
    """High-level call action derived from the LLM response."""

    CHAT = "chat"
    TRANSFER = "transfer"
    END = "end"


def detect_intent(response_text: str) -> Intent:
    """Return the intent encoded in ``response_text``.

    Order matters: ``[TRANSFER]`` is checked before ``[END_CALL]`` so an
    ambiguous response prioritises transferring the caller.
    """
    if TRANSFER_TOKEN in response_text:
        return Intent.TRANSFER
    if END_TOKEN in response_text:
        return Intent.END
    return Intent.CHAT


def clean_response(response_text: str) -> str:
    """Strip control tokens from the response and return the spoken text."""
    return (
        response_text.replace(TRANSFER_TOKEN, "")
        .replace(END_TOKEN, "")
        .strip()
    )
