from tests.conftest import TEST_PROFILE, auth_headers


def test_get_me_returns_profile(client, monkeypatch):
    monkeypatch.setattr(
        "app.users.router.ensure_profile",
        lambda user_id, token, email=None: TEST_PROFILE.model_dump(),
    )

    response = client.get("/api/users/me", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == TEST_PROFILE.id
    assert body["email"] == TEST_PROFILE.email
    assert body["full_name"] == "Test User"


def test_get_me_creates_profile_when_missing(client, monkeypatch):
    called = {}

    def fake_ensure_profile(user_id, token, email=None):
        called["user_id"] = user_id
        called["email"] = email
        profile = TEST_PROFILE.model_dump()
        profile["full_name"] = None
        return profile

    monkeypatch.setattr("app.users.router.ensure_profile", fake_ensure_profile)

    response = client.get("/api/users/me", headers=auth_headers())
    assert response.status_code == 200
    assert called["user_id"] == TEST_PROFILE.id
    assert called["email"] == TEST_PROFILE.email


def test_patch_me_updates_profile(client, monkeypatch):
    def fake_update_profile(user_id, token, updates):
        profile = TEST_PROFILE.model_dump()
        profile["full_name"] = updates.full_name
        profile["timezone"] = updates.timezone
        return profile

    monkeypatch.setattr("app.users.router.update_profile", fake_update_profile)

    response = client.patch(
        "/api/users/me",
        json={"full_name": "Alice", "timezone": "Asia/Kolkata"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Alice"
    assert body["timezone"] == "Asia/Kolkata"


def test_patch_me_rejects_unknown_fields(client):
    response = client.patch(
        "/api/users/me",
        json={"hacker_field": "pwned"},
        headers=auth_headers(),
    )
    assert response.status_code == 422


def test_me_requires_auth(client):
    response = client.patch("/api/users/me", json={"full_name": "Alice"})
    assert response.status_code == 401


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"connected", "disconnected", "not_configured"}
