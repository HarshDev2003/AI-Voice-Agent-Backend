from __future__ import annotations

import httpx

from app.core.config import settings


def _check_database() -> dict[str, str]:
    if not settings.supabase_url:
        return {"status": "not_configured", "detail": "SUPABASE_URL is not configured"}
    if not settings.supabase_anon_key:
        return {"status": "not_configured", "detail": "SUPABASE_ANON_KEY is not configured"}

    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles?select=id&limit=1",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {settings.supabase_anon_key}",
            },
            timeout=5,
        )
    except httpx.HTTPError as exc:
        return {"status": "error", "detail": f"Unreachable: {exc}"}

    if response.status_code == 200:
        return {"status": "ok", "detail": "PostgreSQL / PostgREST is reachable (profiles table)"}
    if response.status_code == 404:
        return {"status": "error", "detail": "profiles table not found"}
    return {"status": "error", "detail": f"Unexpected HTTP {response.status_code}"}


def build_health_report() -> dict[str, str]:
    db_check = _check_database()
    if db_check["status"] == "ok":
        database_status = "connected"
    elif db_check["status"] == "not_configured":
        database_status = "not_configured"
    else:
        database_status = "disconnected"

    return {
        "status": "ok",
        "database": database_status,
    }
