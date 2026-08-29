from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: EmailStr
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
