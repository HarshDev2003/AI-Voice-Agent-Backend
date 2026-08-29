from app.integrations.supabase import auth_service
from tests.conftest import auth_headers


def test_signup_proxies_to_supabase(client, monkeypatch):
    captured = {}

    def fake_sign_up(email, password):
        captured["email"] = email
        captured["password"] = password
        return {"user": {"id": "u1", "email": email}, "session": None}

    monkeypatch.setattr(auth_service, "sign_up", fake_sign_up)

    response = client.post(
        "/api/auth/signup",
        json={"email": "new@example.com", "password": "supersecret"},
    )
    assert response.status_code == 200
    assert captured["email"] == "new@example.com"
    assert captured["password"] == "supersecret"
    assert response.json()["user"]["id"] == "u1"


def test_signup_rejects_invalid_email(client):
    response = client.post(
        "/api/auth/signup",
        json={"email": "not-an-email", "password": "supersecret"},
    )
    assert response.status_code == 422


def test_login_proxies_to_supabase(client, monkeypatch):
    def fake_sign_in(email, password):
        return {"user": {"email": email}, "session": {"access_token": "abc"}}

    monkeypatch.setattr(auth_service, "sign_in", fake_sign_in)

    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "secret"},
    )
    assert response.status_code == 200
    assert response.json()["session"]["access_token"] == "abc"
