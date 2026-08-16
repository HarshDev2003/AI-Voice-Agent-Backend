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


def test_verify_otp_proxies_to_supabase(client, monkeypatch):
    captured = {}

    def fake_verify_otp(email, token):
        captured["email"] = email
        captured["token"] = token
        return {"user": {"email": email}}

    monkeypatch.setattr(auth_service, "verify_otp", fake_verify_otp)

    response = client.post(
        "/api/auth/verify-otp",
        json={"email": "test@example.com", "token": "483921"},
    )
    assert response.status_code == 200
    assert captured["token"] == "483921"


def test_resend_otp_proxies_to_supabase(client, monkeypatch):
    def fake_resend_otp(email):
        return {"status": "ok"}

    monkeypatch.setattr(auth_service, "resend_otp", fake_resend_otp)

    response = client.post(
        "/api/auth/resend-otp",
        json={"email": "test@example.com"},
    )
    assert response.status_code == 200


def test_forgot_password_proxies_to_supabase(client, monkeypatch):
    captured = {}

    def fake_reset_password_for_email(email):
        captured["email"] = email
        return {"status": "ok"}

    monkeypatch.setattr(auth_service, "reset_password_for_email", fake_reset_password_for_email)

    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "test@example.com"},
    )
    assert response.status_code == 200
    assert captured["email"] == "test@example.com"


def test_reset_password_requires_token(client):
    response = client.post("/api/auth/reset-password", json={"new_password": "newsecret"})
    assert response.status_code == 401


def test_reset_password_proxies_to_supabase(client, monkeypatch):
    captured = {}

    def fake_update_password(access_token, new_password):
        captured["access_token"] = access_token
        captured["new_password"] = new_password
        return {"status": "ok"}

    monkeypatch.setattr(auth_service, "update_password", fake_update_password)

    response = client.post(
        "/api/auth/reset-password",
        json={"new_password": "newsecret"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert captured["new_password"] == "newsecret"


def test_logout_proxies_to_supabase(client, monkeypatch):
    captured = {}

    def fake_sign_out(access_token):
        captured["access_token"] = access_token
        return {"status": "ok"}

    monkeypatch.setattr(auth_service, "sign_out", fake_sign_out)

    response = client.post("/api/auth/logout", headers=auth_headers())
    assert response.status_code == 200
    assert captured["access_token"] == "valid-token"


def test_auth_error_maps_to_http_error(client, monkeypatch):
    from app.integrations.supabase.auth_service import SupabaseApiError

    def failing_sign_up(email, password):
        raise SupabaseApiError(422, "User already registered")

    monkeypatch.setattr(auth_service, "sign_up", failing_sign_up)

    response = client.post(
        "/api/auth/signup",
        json={"email": "dup@example.com", "password": "supersecret"},
    )
    assert response.status_code == 422
