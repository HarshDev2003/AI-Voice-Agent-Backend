import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app.core.config import get_settings
from app.main import create_app

AUTH_TOKEN = "test-auth-token-12345"
BASE_URL = "https://example.ngrok.io"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    monkeypatch.setenv("SERVER_BASE_URL", BASE_URL)
    get_settings.cache_clear()
    try:
        app = create_app()
        # base_url matches the public URL used to sign requests, so the app sees
        # the same origin Twilio signed against (as it would behind a tunnel/proxy).
        with TestClient(app, base_url=BASE_URL) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


def sign(url_path: str, params: dict) -> str:
    validator = RequestValidator(AUTH_TOKEN)
    return validator.compute_signature(f"{BASE_URL}{url_path}", params)


def test_incoming_valid_signature_returns_stream_twiml(client):
    params = {"CallSid": "CA123"}
    response = client.post(
        "/webhooks/twilio/incoming",
        data=params,
        headers={"X-Twilio-Signature": sign("/webhooks/twilio/incoming", params)},
    )
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "wss://example.ngrok.io/ws/media-stream/CA123" in response.text


def test_incoming_missing_signature_is_forbidden(client):
    response = client.post("/webhooks/twilio/incoming", data={"CallSid": "CA123"})
    assert response.status_code == 403


def test_incoming_wrong_signature_is_forbidden(client):
    params = {"CallSid": "CA123"}
    response = client.post(
        "/webhooks/twilio/incoming",
        data=params,
        headers={"X-Twilio-Signature": "garbage-signature"},
    )
    assert response.status_code == 403


def test_status_valid_signature_returns_empty_twiml(client):
    params = {"CallSid": "CA123", "CallStatus": "completed"}
    response = client.post(
        "/webhooks/twilio/status",
        data=params,
        headers={"X-Twilio-Signature": sign("/webhooks/twilio/status", params)},
    )
    assert response.status_code == 200
    assert "<Response" in response.text


def test_status_missing_signature_is_forbidden(client):
    response = client.post("/webhooks/twilio/status", data={"CallSid": "CA123"})
    assert response.status_code == 403