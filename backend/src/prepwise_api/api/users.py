from typing import Annotated

from fastapi import APIRouter, Depends

from prepwise_api.auth import get_current_user
from prepwise_api.models import User
from prepwise_api.schemas import CurrentUserResponse

router = APIRouter(prefix="/api/me", tags=["users"])


@router.get("", response_model=CurrentUserResponse)
def read_current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Return the local application user for the authenticated identity."""
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )
