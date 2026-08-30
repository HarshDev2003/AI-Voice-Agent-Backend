"""Tests for the agent turn function (chain.run_turn).

Uses a fake LLM so the tests run offline and assert the wiring:
- the system prompt is included,
- history grows in the right order,
- intent is detected from the LLM reply,
- the cleaned response is what callers will hand to TTS.
"""
from types import SimpleNamespace

import pytest

from app.agent.chain import AgentResult, run_turn
from app.agent.intent import Intent
from app.llm.base import LLMProvider
from app.voice.session import CallSession


class FakeLLM(LLMProvider):
    """Tiny stub LLM that returns scripted replies, in order."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list[dict]] = []
        self._i = 0

    async def chat(self, messages):
        self.calls.append(messages)
        if self._i >= len(self._replies):
            raise AssertionError("FakeLLM ran out of scripted replies")
        reply = self._replies[self._i]
        self._i += 1
        return reply


@pytest.mark.asyncio
async def test_run_turn_chat_intent_updates_history():
    llm = FakeLLM(["Hello! How can I help?"])
    session = CallSession(call_sid="CA1")
    result = await run_turn(session, "Hi there", llm)

    assert isinstance(result, AgentResult)
    assert result.intent is Intent.CHAT
    assert result.should_transfer is False
    assert result.should_end is False
    assert result.response_text == "Hello! How can I help?"

    # History: user then assistant.
    assert [t.role for t in session.history] == ["user", "assistant"]
    assert session.history[0].text == "Hi there"
    assert session.history[1].text == "Hello! How can I help?"

    # System prompt was included in the LLM call.
    assert llm.calls[0][0]["role"] == "system"
    assert "Harsh" in llm.calls[0][0]["content"]


@pytest.mark.asyncio
async def test_run_turn_transfer_intent_strips_token():
    llm = FakeLLM(["Sure, please hold. [TRANSFER]"])
    session = CallSession(call_sid="CA1")
    result = await run_turn(session, "Connect me to Harsh", llm)

    assert result.intent is Intent.TRANSFER
    assert result.should_transfer is True
    assert result.should_end is False
    # The spoken text has the token stripped.
    assert result.response_text == "Sure, please hold."
    # But the transcript buffer keeps the cleaned line (no token).
    assert "assistant: Sure, please hold." in session.transcript_buffer


@pytest.mark.asyncio
async def test_run_turn_end_intent():
    llm = FakeLLM(["Goodbye! [END_CALL]"])
    session = CallSession(call_sid="CA1")
    result = await run_turn(session, "Okay, bye", llm)

    assert result.intent is Intent.END
    assert result.should_end is True
    assert result.should_transfer is False
    assert result.response_text == "Goodbye!"


@pytest.mark.asyncio
async def test_run_turn_empty_input_is_noop():
    llm = FakeLLM([])
    session = CallSession(call_sid="CA1")
    result = await run_turn(session, "   ", llm)
    assert result.intent is Intent.CHAT
    assert result.response_text == ""
    # No LLM call, no history update.
    assert llm.calls == []
    assert session.history == []


@pytest.mark.asyncio
async def test_run_turn_multi_turn_history_is_sent_to_llm():
    llm = FakeLLM(["Got it.", "Sure, transferring. [TRANSFER]"])
    session = CallSession(call_sid="CA1")
    await run_turn(session, "My name is Rahul", llm)
    await run_turn(session, "Please connect me to Harsh", llm)

    # Second call must include the full history.
    msgs = llm.calls[1]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "My name is Rahul"
    assert msgs[2]["content"] == "Got it."
    assert msgs[3]["content"] == "Please connect me to Harsh"
