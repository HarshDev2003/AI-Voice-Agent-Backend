from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from fastapi import Depends, HTTPException, status

from app.core import security
from app.core.config import get_settings
from app.repositories.user_repository import (
    EmailAlreadyRegisteredError,
    RefreshTokenRepository,
    UserRepository,
)
from app.dependencies import get_user_repository
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired refresh token",
)


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository = Depends(get_user_repository),
        refresh_token_repository: RefreshTokenRepository = Depends(RefreshTokenRepository),
    ) -> None:
        self._users = user_repository
        self._refresh_tokens = refresh_token_repository

    async def register(self, request: RegisterRequest) -> UserResponse:
        try:
            document = await self._users.create_user(
                name=request.name.strip(),
                email=request.email.lower(),
                password_hash=security.hash_password(request.password),
            )
        except EmailAlreadyRegisteredError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            ) from None
        return UserResponse(
            id=str(document["_id"]),
            name=document["name"],
            email=document["email"],
        )

    async def login(self, request: LoginRequest) -> TokenResponse:
        document = await self._users.get_user_by_email(request.email.lower())
        if document is None or not security.verify_password(
            request.password, document.get("password_hash", "")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not document.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        return await self._issue_token_pair(document)

    async def refresh(self, request: RefreshRequest) -> TokenResponse:
        """Rotate the refresh token: validate, revoke old, issue a new pair.

        If a revoked token is presented again (possible theft), revoke every
        session for that user.
        """
        try:
            payload = security.decode_refresh_token(request.refresh_token)
        except pyjwt.PyJWTError:
            raise _401 from None

        user_id = payload.get("sub", "")
        stored = await self._refresh_tokens.find_active_by_token(request.refresh_token)
        if stored is None:
            # Reuse of a rotated/revoked token: kill all sessions for this user.
            await self._refresh_tokens.revoke_all_for_user(user_id)
            raise _401

        document = await self._users.get_user_by_id(user_id)
        if document is None or not document.get("is_active", False):
            await self._refresh_tokens.revoke_all_for_user(user_id)
            raise _401

        await self._refresh_tokens.revoke(request.refresh_token)
        return await self._issue_token_pair(document)

    async def logout(self, request: RefreshRequest) -> None:
        """Revoke the presented refresh token (idempotent)."""
        try:
            security.decode_refresh_token(request.refresh_token)
        except pyjwt.PyJWTError:
            raise _401 from None
        await self._refresh_tokens.revoke(request.refresh_token)

    async def _issue_token_pair(self, document: dict) -> TokenResponse:
        settings = get_settings()
        user_id = str(document["_id"])
        email = document["email"]
        access_token = security.create_access_token(user_id, email)
        refresh_token = security.create_refresh_token(user_id, email)
        await self._refresh_tokens.issue(
            user_id=user_id,
            token=refresh_token,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
