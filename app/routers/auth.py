from fastapi import APIRouter, Depends, status

from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, service: AuthService = Depends(AuthService)) -> UserResponse:
    return await service.register(request)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, service: AuthService = Depends(AuthService)) -> TokenResponse:
    return await service.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, service: AuthService = Depends(AuthService)) -> TokenResponse:
    return await service.refresh(request)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: RefreshRequest, service: AuthService = Depends(AuthService)) -> None:
    await service.logout(request)
