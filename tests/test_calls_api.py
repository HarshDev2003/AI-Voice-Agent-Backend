"""Tests for the GET /calls and GET /calls/{call_sid} endpoints."""
from fastapi.testclient import TestClient

from app.calls.repository import InMemoryCallsRepository
from app.main import create_app


def _client_with_repo() -> tuple[TestClient, InMemoryCallsRepository]:
    repo = InMemoryCallsRepository()
    app = create_app()
    app.state.calls_repository = repo
    return TestClient(app), repo


def test_list_calls_empty():
    client, _ = _client_with_repo()
    r = client.get("/calls")
    assert r.status_code == 200
    assert r.json() == {"calls": []}


def test_list_calls_returns_inserted_records():
    client, repo = _client_with_repo()
    repo.insert_call(call_sid="CA1", caller_number="+91xxxxxxxxxx")
    repo.insert_transcript(call_sid="CA1", transcript="hi", turns=[])
    repo.insert_summary(call_sid="CA1", summary="ok", sentiment="positive")
    r = client.get("/calls")
    assert r.status_code == 200
    body = r.json()
    assert len(body["calls"]) == 1
    assert body["calls"][0]["call_sid"] == "CA1"
    assert body["calls"][0]["transcript"]["transcript"] == "hi"
    assert body["calls"][0]["summary"]["summary"] == "ok"


def test_get_call_by_sid_returns_full_record():
    client, repo = _client_with_repo()
    repo.insert_call(call_sid="CA1", caller_number="+91xxxxxxxxxx")
    repo.insert_transcript(call_sid="CA1", transcript="hi", turns=[])
    repo.insert_summary(call_sid="CA1", summary="ok", sentiment="positive")
    r = client.get("/calls/CA1")
    assert r.status_code == 200
    body = r.json()
    assert body["call_sid"] == "CA1"
    assert body["transcript"]["transcript"] == "hi"
    assert body["summary"]["summary"] == "ok"


def test_get_call_by_sid_returns_404_when_missing():
    client, _ = _client_with_repo()
    r = client.get("/calls/UNKNOWN")
    assert r.status_code == 404


def test_list_calls_respects_limit_query_param():
    client, repo = _client_with_repo()
    for i in range(5):
        repo.insert_call(call_sid=f"CA{i}")
    r = client.get("/calls?limit=2")
    assert r.status_code == 200
    assert len(r.json()["calls"]) == 2
