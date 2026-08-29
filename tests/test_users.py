from tests.conftest import login, register


def test_me_returns_profile_without_sensitive_fields(client):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "name", "email", "is_active"}
