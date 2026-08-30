"""Tests for the agent prompts module."""
from app.agent.prompts import (
    POST_CALL_SUMMARY_PROMPT,
    SYSTEM_PROMPT,
    build_post_call_prompt,
)


def test_system_prompt_mentions_languages():
    assert "Hindi" in SYSTEM_PROMPT
    assert "English" in SYSTEM_PROMPT
    assert "Hinglish" in SYSTEM_PROMPT


def test_system_prompt_contains_control_tokens():
    assert "[TRANSFER]" in SYSTEM_PROMPT
    assert "[END_CALL]" in SYSTEM_PROMPT


def test_post_call_prompt_includes_transcript():
    out = build_post_call_prompt("caller: hi\nassistant: hello")
    assert "caller: hi" in out
    assert "assistant: hello" in out
    # Output is JSON-only; no markdown fences.
    assert "```" not in out
    # Format string is stable.
    assert "{transcript}" not in out


def test_post_call_summary_prompt_keys():
    for key in ("summary", "caller_intent", "action_items", "sentiment"):
        assert key in POST_CALL_SUMMARY_PROMPT
