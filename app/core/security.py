import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import settings


class TokenValidationError(Exception):
    """Raised when a Supabase access token cannot be validated."""


_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _decode_local(token: str) -> dict:
    errors: list[str] = []

    if settings.supabase_jwt_secret:
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except Exception as exc:  # noqa: BLE001 - collect and fall through
            errors.append(f"HS256: {exc}")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="authenticated",
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"JWKS: {exc}")

    raise TokenValidationError("; ".join(errors) or "No validation method configured")


def _verify_remote(token: str) -> dict:
    """Fallback: ask Supabase to resolve the token (network round-trip)."""
    response = httpx.get(
        f"{settings.supabase_url}/auth/v1/user",
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise TokenValidationError(f"Supabase returned HTTP {response.status_code}")
    user = response.json()
    return {
        "sub": user["id"],
        "email": user.get("email"),
        "email_verified": user.get("email_verified"),
        "role": user.get("role"),
    }


def decode_access_token(token: str) -> dict:
    """Validate a Supabase access token and return its claims.

    Local JWT validation first (HS256 secret or JWKS/RS256), falling back
    to Supabase's ``/auth/v1/user`` endpoint when local validation fails.
    """
    try:
        return _decode_local(token)
    except TokenValidationError as local_error:
        if settings.supabase_url:
            return _verify_remote(token)
        raise TokenValidationError(f"Unable to validate token: {local_error}") from local_error
