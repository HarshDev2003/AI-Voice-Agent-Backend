"""Tests for the post-call pipeline.

Drives :func:`run_post_call` with an injected repository and a fake LLM
so the full flow is exercised offline. Also covers the lenient
``parse_summary_json`` helper.
"""
from types import SimpleNamespace

import pytest

from app.calls.post_call import (
    TERMINAL_STATUSES,
    parse_summary_json,
    run_post_call,
    transcript_from_session,
)
from app.calls.repository import InMemoryCallsRepository
from app.llm.base import LLMProvider
from app.voice.session import CallSession, session_store


@pytest.fixture(autouse=True)
def _clear_session_store():
    session_store._sessions.clear()
    yield
    session_store._sessions.clear()



# ---------------------------------------------------------------------------
# parse_summary_json
# ---------------------------------------------------------------------------


def test_parse_summary_json_pure_json():
    obj = parse_summary_json(
        '{"summary": "ok", "caller_intent": "ask", "action_items": ["a"], "sentiment": "positive"}'
    )
    assert obj == {
        "summary": "ok",
        "caller_intent": "ask",
        "action_items": ["a"],
        "sentiment": "positive",
    }


def test_parse_summary_json_strips_markdown_fence():
    text = "```json\n{\"summary\": \"ok\", \"sentiment\": \"neutral\"}\n```"
    assert parse_summary_json(text)["summary"] == "ok"


def test_parse_summary_json_extracts_embedded_object():
    text = "Here is the JSON you asked for:\n{\"summary\": \"embedded\"}\nThanks!"
    assert parse_summary_json(text)["summary"] == "embedded"


def test_parse_summary_json_falls_back_to_raw_text():
    obj = parse_summary_json("not json at all, just prose")
    assert obj["summary"] == "not json at all, just prose"
    assert obj["sentiment"] == "neutral"


def test_parse_summary_json_empty_string():
    obj = parse_summary_json("")
    assert obj == {
        "summary": "",
        "caller_intent": "",
        "action_items": [],
        "sentiment": "neutral",
    }


# ---------------------------------------------------------------------------
# transcript_from_session
# ---------------------------------------------------------------------------


def test_transcript_from_session_builds_text_and_turns():
    session = CallSession(call_sid="CA1")
    session.add_user_turn("hi")
    session.add_assistant_turn("hello")
    text, turns = transcript_from_session(session)
    assert "caller: hi" in text
    assert "assistant: hello" in text
    assert [t["role"] for t in turns] == ["caller", "assistant"]


# ---------------------------------------------------------------------------
# run_post_call
# ---------------------------------------------------------------------------


async def test_run_post_call_persists_call_transcript_and_summary():
    repo = InMemoryCallsRepository()
    llm = FakeLLM(
        [
            '{"summary": "Call was a quick greeting", "caller_intent": "say hi", "action_items": [], "sentiment": "positive"}'
        ]
    )
    session = session_store.get_or_create("CA1", caller_number="+91xxxxxxxxxx")
    session.add_user_turn("hi")
    session.add_assistant_turn("hello")

    row = await run_post_call("CA1", call_status="completed", repository=repo, llm=llm)
    assert row is not None
    assert row["caller_number"] == "+91xxxxxxxxxx"
    assert row["status"] == "completed"
    assert row["transcript"]["transcript"]
    assert "caller: hi" in row["transcript"]["transcript"]
    assert row["summary"]["summary"] == "Call was a quick greeting"
    assert row["summary"]["sentiment"] == "positive"
    assert session_store.get("CA1") is None


async def test_run_post_call_marks_transferred_status():
    repo = InMemoryCallsRepository()
    llm = FakeLLM(['{"summary": "x", "sentiment": "neutral"}'])
    session = session_store.get_or_create("CA1")
    session.add_user_turn("transfer me")
    session.add_assistant_turn("ok [TRANSFER]")
    session.status = "transferred"

    row = await run_post_call("CA1", call_status="completed", repository=repo, llm=llm)
    assert row["status"] == "transferred"


async def test_run_post_call_is_idempotent():
    repo = InMemoryCallsRepository()
    llm = FakeLLM(['{"summary": "x", "sentiment": "neutral"}'])
    session = session_store.get_or_create("CA1")
    session.add_user_turn("hi")

    await run_post_call("CA1", call_status="completed", repository=repo, llm=llm)
    # Second call after session cleanup returns None.
    row2 = await run_post_call("CA1", call_status="completed", repository=repo, llm=llm)
    assert row2 is None


async def test_run_post_call_handles_empty_transcript_without_llm():
    repo = InMemoryCallsRepository()
    llm = FakeLLM([])  # would raise if called
    session = session_store.get_or_create("CA1")
    row = await run_post_call("CA1", call_status="completed", repository=repo, llm=llm)
    assert row is not None
    assert row["summary"]["summary"] == "Call had no transcript."
    assert llm.calls == 0


async def test_run_post_call_falls_back_when_summary_llm_fails():
    repo = InMemoryCallsRepository()

    class BoomLLM(LLMProvider):
        async def chat(self, messages):
            raise RuntimeError("down")

    session = session_store.get_or_create("CA1")
    session.add_user_turn("hi")
    row = await run_post_call("CA1", call_status="completed", repository=repo, llm=BoomLLM())
    assert row["summary"]["summary"].startswith("Summary unavailable")


def test_terminal_statuses_include_completed():
    assert "completed" in TERMINAL_STATUSES
    assert "failed" in TERMINAL_STATUSES
    assert "canceled" in TERMINAL_STATUSES

class FakeLLM(LLMProvider):
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self._i = 0
        self.calls = 0

    async def chat(self, messages):
        self.calls += 1
        reply = self._replies[self._i]
        self._i += 1
        return reply
