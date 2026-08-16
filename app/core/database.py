from supabase import Client, create_client

from app.core.config import settings


def get_user_client(token: str) -> Client:
    """Supabase client authenticated as the end user.

    Passing the user's access token as the client key makes PostgREST
    requests carry that user's Authorization header, so Row Level
    Security policies are enforced per-user.
    """
    return create_client(settings.supabase_url, token)


def get_admin_client() -> Client:
    """Supabase client using the service-role key (server-side only)."""
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    return create_client(settings.supabase_url, key)
