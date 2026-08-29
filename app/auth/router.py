from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token, AuthError
from app.core.config import settings
from app.integrations.supabase import create_client as supabase_client
from app.users.schemas import CurrentUser, UserProfile

router = APIRouter(prefix="/api/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


import uuid

def _get_supabase():
    """Get a Supabase client instance."""
    return supabase_client(settings.supabase_url, settings.supabase_anon_key)


def _generate_user_id(email: str) -> str:
    """Generate a UUID from the user's email."""
    # Use UUID v5 (hash-based) for deterministic UUID from email
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def _map_error(exc: Exception) -> HTTPException:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code >= 400:
        detail = getattr(exc, "detail", str(exc))
        if isinstance(detail, str) and detail.startswith("{") and detail.endswith("}"):
            try:
                import json
                parsed = json.loads(detail)
                if isinstance(parsed, dict) and "msg" in parsed:
                    detail = parsed["msg"]
            except (json.JSONDecodeError, ValueError):
                pass
        return HTTPException(status_code=status_code, detail=detail)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/signup", summary="Register with email + password + full name")
def signup(payload: SignUpRequest):
    try:
        # Hash the password locally
        password = hash_password(payload.password)

        # Get Supabase client and insert user into profiles table
        sb = _get_supabase()
        user_id = _generate_user_id(payload.email)

        user_data = {
            "id": user_id,
            "email": payload.email,
            "full_name": payload.full_name,
            "password": password,
        }

        response = sb.table("profiles").insert(user_data).execute()

        # Create JWT access token
        access_token = create_access_token(subject=user_id)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": payload.email,
                "full_name": payload.full_name,
            },
        }
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/login", summary="Log in with email + password")
def login(payload: LoginRequest):
    try:
        # Get Supabase client and fetch user by email
        sb = _get_supabase()

        result = sb.table("profiles").select("*").eq("email", payload.email).maybe_single().execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user = result.data

        # Verify password against stored hash
        if not verify_password(payload.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Create JWT access token
        access_token = create_access_token(subject=user["id"])

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user.get("full_name"),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _map_error(exc) from exc
