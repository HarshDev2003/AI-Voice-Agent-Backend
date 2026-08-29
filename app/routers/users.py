from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.auth import CurrentUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(current_user: dict = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=str(current_user["_id"]),
        name=current_user["name"],
        email=current_user["email"],
        is_active=current_user.get("is_active", True),
    )
