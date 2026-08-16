import pytest

from app.core import health


@pytest.fixture(autouse=True)
def connected_db(monkeypatch):
    monkeypatch.setattr(
        health,
        "_check_database",
        lambda: {"status": "ok", "detail": "PostgreSQL is reachable"},
    )


def test_health_ok_and_db_connected():
    report = health.build_health_report()
    assert report == {"status": "ok", "database": "connected"}


def test_health_db_disconnected(monkeypatch):
    monkeypatch.setattr(
        health,
        "_check_database",
        lambda: {"status": "error", "detail": "Connection refused"},
    )
    assert health.build_health_report()["database"] == "disconnected"


def test_health_db_not_configured(monkeypatch):
    monkeypatch.setattr(
        health,
        "_check_database",
        lambda: {"status": "not_configured", "detail": "SUPABASE_URL is not configured"},
    )
    assert health.build_health_report()["database"] == "not_configured"


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"connected", "disconnected", "not_configured"}
