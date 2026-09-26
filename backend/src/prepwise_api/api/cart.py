from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from prepwise_api.api.service_errors import raise_service_http_error
from prepwise_api.auth import get_current_user
from prepwise_api.database import get_session
from prepwise_api.models import User
from prepwise_api.schemas import (
    CartItemCreate,
    CartItemQuantityUpdate,
    CartResponse,
)
from prepwise_api.services import ApplicationServiceError
from prepwise_api.services.cart import (
    add_user_cart_item,
    get_user_cart,
    remove_user_cart_item,
    set_user_cart_item_quantity,
)

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("", response_model=CartResponse)
def get_cart(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CartResponse:
    """Return the authenticated user's persisted cart."""
    return get_user_cart(session, user.id)


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: CartItemCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CartResponse:
    """Add an available meal, or increment its existing cart quantity."""
    try:
        return add_user_cart_item(session, user.id, payload.meal_id, payload.quantity)
    except ApplicationServiceError as error:
        raise_service_http_error(error)


@router.patch("/items/{item_id}", response_model=CartResponse)
def change_cart_item_quantity(
    item_id: UUID,
    payload: CartItemQuantityUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CartResponse:
    """Set a cart quantity while enforcing ownership and availability."""
    try:
        return set_user_cart_item_quantity(session, user.id, item_id, payload.quantity)
    except ApplicationServiceError as error:
        raise_service_http_error(error)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cart_item(
    item_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    """Remove one item from the authenticated user's cart."""
    try:
        remove_user_cart_item(session, user.id, item_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ApplicationServiceError as error:
        raise_service_http_error(error)
