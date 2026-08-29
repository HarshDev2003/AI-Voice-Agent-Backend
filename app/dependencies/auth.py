import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import security
from app.core.database import get_database
from app.repositories.user_repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository() -> UserRepository:
    return UserRepository(db=get_database())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    user_repository: UserRepository = Depends(get_user_repository),
) -> dict:
    """Resolve the authenticated user from a Bearer JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = security.decode_access_token(credentials.credentials)
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = await user_repository.get_user_by_id(payload.get("sub", ""))
    if user is None or not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
