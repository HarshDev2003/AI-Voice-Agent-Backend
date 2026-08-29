import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.users.schemas import UserProfile

TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
TEST_EMAIL = "test@example.com"

VALID_TOKEN = "valid-token"
UNVERIFIED_TOKEN = "unverified-token"

VALID_CLAIMS = {
    "sub": TEST_USER_ID,
    "email": TEST_EMAIL,
    "role": "authenticated",
}

UNVERIFIED_CLAIMS = {
    "sub": TEST_USER_ID,
    "email": TEST_EMAIL,
    "role": "authenticated",
}

TEST_PROFILE = UserProfile(
    id=TEST_USER_ID,
    email=TEST_EMAIL,
    full_name="Test User",
    avatar_url=None,
    preferred_language="en",
    timezone="UTC",
)


@pytest.fixture
def client(monkeypatch):
    from app.core.security import TokenValidationError

    def fake_decode_access_token(token: str) -> dict:
        if token == VALID_TOKEN:
            return dict(VALID_CLAIMS)
        if token == UNVERIFIED_TOKEN:
            return dict(UNVERIFIED_CLAIMS)
        raise TokenValidationError("invalid token")

    monkeypatch.setattr("app.auth.dependencies.decode_access_token", fake_decode_access_token)

    with TestClient(app) as test_client:
        yield test_client


def auth_headers(token: str = VALID_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}