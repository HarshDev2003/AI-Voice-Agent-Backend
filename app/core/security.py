import bcrypt
import jwt
import time
from typing import Optional

from app.core.config import settings


class AuthError(Exception):
    """Raised when authentication fails."""


class TokenValidationError(Exception):
    """Raised when a Supabase access token cannot be validated."""


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str, expires_in: int = 86400) -> str:
    """Create a JWT access token.

    Args:
        subject: The token subject (typically user ID)
        expires_in: Token expiration time in seconds (default: 24h)
    """
    issued_at = time.time()
    expires_at = issued_at + expires_in

    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": expires_at,
        "role": "authenticated",
    }

    encoded = jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )
    return encoded


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Returns the token payload dict if valid.
    Raises AuthError if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}")