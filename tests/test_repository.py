"""Tests for the in-memory calls repository."""
from datetime import datetime, timezone

from app.calls.repository import InMemoryCallsRepository


def test_insert_call_is_idempotent_on_call_sid():
    repo = InMemoryCallsRepository()
    a = repo.insert_call(call_sid="CA1", caller_number="+91xxxxxxxxxx")
    b = repo.insert_call(call_sid="CA1", caller_number="+1-other")
    assert a is b
    # The first insert wins — caller number is not overwritten.
    assert b["caller_number"] == "+91xxxxxxxxxx"


def test_insert_transcript_is_idempotent_on_call_sid():
    repo = InMemoryCallsRepository()
    repo.insert_call(call_sid="CA1")
    first = repo.insert_transcript(call_sid="CA1", transcript="hi", turns=[])
    second = repo.insert_transcript(call_sid="CA1", transcript="hello", turns=[])
    assert first is second
    assert second["transcript"] == "hi"


def test_insert_summary_is_idempotent_on_call_sid():
    repo = InMemoryCallsRepository()
    repo.insert_call(call_sid="CA1")
    repo.insert_transcript(call_sid="CA1", transcript="hi", turns=[])
    a = repo.insert_summary(
        call_sid="CA1", summary="first", caller_intent="x", action_items=[], sentiment="positive"
    )
    b = repo.insert_summary(
        call_sid="CA1", summary="second", caller_intent="y", action_items=[], sentiment="negative"
    )
    assert a is b
    assert b["summary"] == "first"


def test_get_call_by_sid_returns_enriched_row():
    repo = InMemoryCallsRepository()
    repo.insert_call(call_sid="CA1", caller_number="+91")
    repo.insert_transcript(call_sid="CA1", transcript="hi", turns=[{"role": "caller", "text": "hi"}])
    repo.insert_summary(call_sid="CA1", summary="ok", action_items=["a"], sentiment="positive")
    row = repo.get_call_by_sid("CA1")
    assert row is not None
    assert row["caller_number"] == "+91"
    assert row["transcript"]["transcript"] == "hi"
    assert row["summary"]["summary"] == "ok"
    assert row["summary"]["action_items"] == ["a"]


def test_get_call_by_sid_returns_none_for_unknown():
    repo = InMemoryCallsRepository()
    assert repo.get_call_by_sid("missing") is None


def test_list_recent_orders_by_started_at_desc():
    repo = InMemoryCallsRepository()
    repo.insert_call(call_sid="OLD", started_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    repo.insert_call(call_sid="NEW", started_at=datetime(2030, 1, 1, tzinfo=timezone.utc))
    rows = repo.list_recent_calls()
    assert [r["call_sid"] for r in rows] == ["NEW", "OLD"]


def test_update_call_status_sets_fields():
    repo = InMemoryCallsRepository()
    repo.insert_call(call_sid="CA1")
    repo.update_call_status(
        "CA1",
        status="completed",
        ended_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        duration_seconds=42,
    )
    row = repo.get_call_by_sid("CA1")
    assert row["status"] == "completed"
    assert row["ended_at"] is not None
    assert row["duration_seconds"] == 42


def test_transcript_and_summary_ignored_when_no_call_row():
    repo = InMemoryCallsRepository()
    assert repo.insert_transcript(call_sid="ghost", transcript="x", turns=[]) is None
    assert repo.insert_summary(call_sid="ghost", summary="x") is None
