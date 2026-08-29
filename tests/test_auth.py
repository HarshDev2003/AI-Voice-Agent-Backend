from datetime import datetime, timedelta, timezone

import jwt
from tests.conftest import login, logout, refresh, register


class TestRegistration:
    def test_register_valid_user(self, client):
        response = register(client)
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "John Doe"
        assert body["email"] == "john@example.com"
        assert "id" in body
        assert "password" not in body
        assert "password_hash" not in body

    def test_reject_invalid_email(self, client):
        response = register(client, email="not-an-email")
        assert response.status_code == 422

    def test_reject_short_password(self, client):
        response = register(client, password="short")
        assert response.status_code == 422

    def test_reject_empty_name(self, client):
        response = register(client, name="")
        assert response.status_code == 422

    def test_reject_duplicate_email(self, client):
        assert register(client).status_code == 201
        response = register(client, name="Other")
        assert response.status_code == 409
        assert response.json()["detail"] == "Email is already registered"


class TestLogin:
    def test_login_with_valid_credentials(self, client):
        register(client)
        response = login(client)
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    def test_reject_invalid_password(self, client):
        register(client)
        response = login(client, password="WrongPassword1")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_reject_unknown_email(self, client):
        response = login(client, email="ghost@example.com")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_reject_inactive_user(self, client, fake_db):
        register(client)
        doc = next(iter(fake_db.users.documents.values()))
        doc["is_active"] = False
        response = login(client)
        assert response.status_code == 401


class TestProtectedApi:
    def test_me_with_valid_jwt(self, client):
        register(client)
        token = login(client).json()["access_token"]
        response = client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "john@example.com"
        assert body["is_active"] is True
        assert "password_hash" not in body

    def test_reject_missing_jwt(self, client):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_reject_invalid_jwt(self, client):
        response = client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer not-a-token"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    def test_reject_expired_jwt(self, client, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
        register(client)
        from app.core.config import get_settings

        settings = get_settings()
        expired = jwt.encode(
            {"sub": "0" * 24, "email": "john@example.com",
             "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        response = client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    def test_reject_inactive_user_token(self, client, fake_db):
        register(client)
        token = login(client).json()["access_token"]
        doc = next(iter(fake_db.users.documents.values()))
        doc["is_active"] = False
        response = client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401


class TestCors:
    def test_preflight_allows_configured_origin(self, client):
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_unconfigured_origin_not_allowed(self, client):
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.headers.get("access-control-allow-origin") != "https://evil.example.com"

    def test_simple_request_exposes_cors_header(self, client):
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


class TestRefreshToken:
    def test_login_returns_both_tokens(self, client):
        register(client)
        body = login(client).json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["access_token"] != body["refresh_token"]

    def test_refresh_returns_new_pair_and_rotates(self, client, fake_db):
        register(client)
        old = login(client).json()["refresh_token"]
        response = refresh(client, old)
        assert response.status_code == 200
        body = response.json()
        assert body["refresh_token"] != old
        assert body["access_token"]
        # Old token is now revoked (rotated)
        import hashlib

        old_hash = hashlib.sha256(old.encode()).hexdigest()
        old_doc = next(
            d for d in fake_db.refresh_tokens.documents.values()
            if d["token_hash"] == old_hash
        )
        assert old_doc["revoked"] is True
        assert len(fake_db.refresh_tokens.documents) == 2

    def test_new_refresh_token_works_and_new_access_token_authenticates(self, client):
        register(client)
        tokens = login(client).json()
        new_pair = refresh(client, tokens["refresh_token"]).json()
        me = client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {new_pair['access_token']}"}
        )
        assert me.status_code == 200
        assert refresh(client, new_pair["refresh_token"]).status_code == 200

    def test_reuse_of_rotated_token_revokes_all_sessions(self, client):
        register(client)
        first = login(client).json()["refresh_token"]
        # Rotate once: first is now stale
        second = refresh(client, first).json()["refresh_token"]
        # Reuse the rotated token -> theft detection
        assert refresh(client, first).status_code == 401
        # Even the legitimately issued token is now dead
        assert refresh(client, second).status_code == 401

    def test_reject_access_token_as_refresh(self, client):
        register(client)
        tokens = login(client).json()
        response = refresh(client, tokens["access_token"])
        assert response.status_code == 401

    def test_reject_garbage_refresh_token(self, client):
        assert refresh(client, "not-a-token").status_code == 401

    def test_handles_naive_datetimes_from_mongodb(self, client, fake_db):
        """MongoDB returns naive UTC datetimes; refresh must still work."""
        register(client)
        tokens = login(client).json()

        # Naive, still-valid expiry -> refresh succeeds
        for doc in fake_db.refresh_tokens.documents.values():
            if not doc["revoked"]:
                doc["expires_at"] = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        assert refresh(client, tokens["refresh_token"]).status_code == 200

        # Naive, expired expiry -> refresh is rejected (no TypeError)
        login(client)  # issue a fresh, active token
        for doc in fake_db.refresh_tokens.documents.values():
            if not doc["revoked"]:
                doc["expires_at"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        assert refresh(client, tokens["refresh_token"]).status_code == 401

    def test_logout_revokes_refresh_token(self, client):
        register(client)
        tokens = login(client).json()
        response = logout(client, tokens["refresh_token"])
        assert response.status_code == 204
        assert refresh(client, tokens["refresh_token"]).status_code == 401

    def test_logout_rejects_invalid_token(self, client):
        assert logout(client, "garbage").status_code == 401
