from datetime import UTC, datetime, timedelta
import uuid
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _password_hash.verify(plain_password, password_hash)


def _create_token(
    user_id: str,
    email: str,
    token_type: str,
    lifetime: timedelta,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    if token_type == "refresh":
        payload["jti"] = uuid.uuid4().hex
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, email: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id, email, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: str, email: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id, email, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode and validate a JWT of the expected type.

    Raises jwt.PyJWTError on invalid/expired tokens or type mismatch.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected {expected_type} token")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(token, "refresh")
