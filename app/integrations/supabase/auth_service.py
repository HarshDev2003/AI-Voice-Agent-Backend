"""Supabase database integration - user profile operations.

This module provides database operations for the Supabase profiles table.
It does NOT use Supabase Auth (auth.users table) - all authentication
is handled locally via JWT + bcrypt password hashing against the profiles table.
"""
from typing import Optional

import bcrypt

from supabase import Client, create_client

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.users.schemas import UserProfileCreate


def _get_client() -> Client:
    """Get a Supabase client using the anon key."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def _profiles() -> Client:
    """Get the profiles table reference."""
    return _get_client().table("profiles")


def create_user(email: str, password: str, full_name: Optional[str] = None) -> dict:
    """Create a new user in the profiles table with hashed password.
    
    This does NOT create a user in Supabase Auth (auth.users).
    It only stores user data in the profiles table.
    """
    password = hash_password(password)

    user_id = email.replace("@", "_at_").replace(".", "_dot_")

    data = {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "password": password,
    }

    _profiles().insert(data).execute()
    return {"id": user_id, "email": email, "full_name": full_name}


def verify_credentials(email: str, password: str) -> Optional[dict]:
    """Verify user credentials against the profiles table.
    
    Returns user dict if valid, None otherwise.
    Does NOT check email confirmation status - only validates email/password.
    """
    result = _profiles().select("*").eq("email", email).maybe_single().execute()

    if not result.data:
        return None

    user = result.data

    if verify_password(password, user["password"]):
        return {
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name"),
        }

    return None


def get_user(user_id: str) -> Optional[dict]:
    """Fetch a user from the profiles table by ID."""
    result = _profiles().select("*").eq("id", user_id).maybe_single().execute()

    if not result.data:
        return None

    return result.data
