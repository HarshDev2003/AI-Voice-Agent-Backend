from tests.conftest import (
    TEST_PROFILE,
    UNVERIFIED_TOKEN,
    VALID_TOKEN,
    auth_headers,
)


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_invalid_token_rejected(client):
    response = client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_unverified_email_blocked(client):
    response = client.get(
        "/api/users/me",
        headers=auth_headers(UNVERIFIED_TOKEN),
    )
    assert response.status_code == 403


def test_valid_token_accepted(client, monkeypatch):
    monkeypatch.setattr(
        "app.users.router.ensure_profile",
        lambda user_id, token, email=None: TEST_PROFILE.model_dump(),
    )
    response = client.get("/api/users/me", headers=auth_headers(VALID_TOKEN))
    assert response.status_code == 200
    assert response.json()["id"] == TEST_PROFILE.id
    assert response.json()["email"] == TEST_PROFILE.email


def test_malformed_authorization_header_rejected(client):
    response = client.get(
        "/api/users/me",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401
