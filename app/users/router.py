from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.users.schemas import CurrentUser, UserProfile, UserProfileUpdate
from app.users.service import ensure_profile, update_profile

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """Get the current user's profile (creating it on first access)."""
    profile = ensure_profile(
        user_id=current_user.id,
        token=current_user.token,
        email=current_user.email,
    )
    return profile


@router.patch("/me", response_model=UserProfile)
def patch_me(
    updates: UserProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update the current user's profile."""
    return update_profile(
        user_id=current_user.id,
        token=current_user.token,
        updates=updates,
    )
