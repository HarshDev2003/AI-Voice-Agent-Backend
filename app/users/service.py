from typing import Optional

import bcrypt
import uuid

from supabase import Client, create_client

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.users.schemas import UserProfileCreate, UserProfile, UserProfileUpdate
from app.integrations.supabase import create_client as supabase_create_client


def _profiles(token: Optional[str] = None):
    client = create_client(settings.supabase_url, token) if token else create_client(settings.supabase_url, settings.supabase_anon_key)
    return client.table("profiles")


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


def _generate_user_id(email: str) -> str:
    """Generate a UUID from the user's email."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def create_user(email: str, password: str, full_name: Optional[str] = None) -> dict:
    """Create a new user in the profiles table with hashed password."""
    password = hash_password(password)

    user_id = _generate_user_id(email)

    data = {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "password": password,
    }

    _profiles().insert(data).execute()
    return get_profile(user_id, None)


def verify_user_credentials(email: str, password: str) -> Optional[dict]:
    """Verify user credentials against the database.

    Returns user dict if valid, None otherwise.
    """
    result = _profiles().select("*").eq("email", email).maybe_single().execute()

    if not result.data:
        return None

    user = result.data

    if verify_password(password, user["password"]):
        return user

    return None
