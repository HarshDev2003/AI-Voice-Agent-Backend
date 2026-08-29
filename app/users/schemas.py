from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CurrentUser(BaseModel):
    """Resolved from the validated JWT access token."""

    id: str
    email: Optional[EmailStr] = None
    token: str


class UserProfile(BaseModel):
    """Application user profile (public.profiles row)."""

    id: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = Field(default="en")
    timezone: Optional[str] = Field(default="UTC")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileCreate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = Field(default="en")
    timezone: Optional[str] = Field(default="UTC")


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=120)
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = None
    timezone: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str