"""Tests for the in-memory call session state."""
from app.voice.session import CallSession, SessionStore


def test_call_session_defaults():
    s = CallSession(call_sid="CA123")
    assert s.call_sid == "CA123"
    assert s.history == []
    assert s.transcript_buffer == []
    assert s.status == "active"


def test_add_user_and_assistant_turns_extend_history():
    s = CallSession(call_sid="CA1")
    s.add_user_turn("hi")
    s.add_assistant_turn("hello!")
    assert [t.role for t in s.history] == ["user", "assistant"]
    assert [t.text for t in s.history] == ["hi", "hello!"]


def test_messages_returns_system_plus_history():
    s = CallSession(call_sid="CA1")
    s.add_user_turn("hi")
    s.add_assistant_turn("hello")
    msgs = s.messages("system-prompt")
    assert msgs[0] == {"role": "system", "content": "system-prompt"}
    assert msgs[1] == {"role": "user", "content": "hi"}
    assert msgs[2] == {"role": "assistant", "content": "hello"}


def test_turn_guard_serialises_concurrent_turns():
    import threading

    s = CallSession(call_sid="CA1")
    in_critical = 0
    max_in_critical = 0

    def worker():
        nonlocal in_critical, max_in_critical
        with s.acquire_turn():
            in_critical += 1
            max_in_critical = max(max_in_critical, in_critical)
            # Yield so other threads can race.
            import time

            time.sleep(0.01)
            in_critical -= 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_in_critical == 1  # lock is held by at most one thread at a time


def test_session_store_get_or_create_returns_same_session():
    store = SessionStore()
    a = store.get_or_create("CA1", caller_number="+91xxxxxxxxxx")
    b = store.get_or_create("CA1")
    assert a is b
    assert a.caller_number == "+91xxxxxxxxxx"


def test_session_store_remove_and_active_count():
    store = SessionStore()
    store.get_or_create("CA1")
    store.get_or_create("CA2")
    assert store.active_count() == 2
    removed = store.remove("CA1")
    assert removed is not None and removed.call_sid == "CA1"
    assert store.active_count() == 1
    assert store.get("CA1") is None
