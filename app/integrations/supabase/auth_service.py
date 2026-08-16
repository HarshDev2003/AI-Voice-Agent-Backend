import httpx
from supabase import Client, create_client

from app.core.config import settings


class SupabaseApiError(Exception):
    """Raised when a Supabase HTTP call fails."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {token}",
    }


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise SupabaseApiError(response.status_code, response.text or "Supabase request failed")


def sign_up(email: str, password: str) -> dict:
    """Create a new account. Supabase sends the verification email."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return client.auth.sign_up({"email": email, "password": password})


def sign_in(email: str, password: str) -> dict:
    """Log in with email + password (session with access/refresh tokens)."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return client.auth.sign_in_with_password({"email": email, "password": password})


def verify_otp(email: str, token: str) -> dict:
    """Verify the 6-digit email verification OTP sent during signup."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return client.auth.verify_otp({"email": email, "token": token, "type": "signup"})


def resend_otp(email: str) -> dict:
    """Resend the signup verification OTP."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return client.auth.resend({"type": "signup", "email": email})


def reset_password_for_email(email: str) -> dict:
    """Send the password-recovery email."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return client.auth.reset_password_for_email(email)


def update_password(access_token: str, new_password: str) -> dict:
    """Update the password for the authenticated (recovery) session."""
    response = httpx.put(
        f"{settings.supabase_url}/auth/v1/user",
        json={"password": new_password},
        headers=_auth_headers(access_token),
        timeout=10,
    )
    _raise_for_status(response)
    return response.json() if response.content else {}


def sign_out(access_token: str) -> dict:
    """Invalidate the current session/token."""
    response = httpx.post(
        f"{settings.supabase_url}/auth/v1/logout",
        headers=_auth_headers(access_token),
        timeout=10,
    )
    _raise_for_status(response)
    return {"status": "ok"}


def get_supabase_admin() -> Client:
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    return create_client(settings.supabase_url, key)


def get_supabase_user(token: str) -> Client:
    return create_client(settings.supabase_url, token)
