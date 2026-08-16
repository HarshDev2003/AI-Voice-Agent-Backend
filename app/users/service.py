from typing import Optional

from app.integrations.supabase.auth_service import get_supabase_user
from app.users.schemas import UserProfileCreate, UserProfileUpdate


def _profiles(token: str):
    return get_supabase_user(token).table("profiles")


def get_profile(user_id: str, token: str) -> Optional[dict]:
    result = _profiles(token).select("*").eq("id", user_id).maybe_single().execute()
    return result.data or None


def ensure_profile(user_id: str, token: str, email: Optional[str] = None) -> dict:
    """Return the user's profile, creating it if it doesn't exist yet."""
    profile = get_profile(user_id, token)
    if profile:
        return profile

    data = UserProfileCreate(email=email).model_dump(exclude_none=True)
    data["id"] = user_id
    _profiles(token).insert(data).execute()
    return get_profile(user_id, token)


def update_profile(user_id: str, token: str, updates: UserProfileUpdate) -> dict:
    data = updates.model_dump(exclude_unset=True, exclude_none=True)
    if data:
        _profiles(token).update(data).eq("id", user_id).execute()
    return get_profile(user_id, token)
