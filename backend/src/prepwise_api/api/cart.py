from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from prepwise_api.auth import get_current_user
from prepwise_api.database import get_session
from prepwise_api.models import CartItem, Meal, User
from prepwise_api.schemas import (
    CartItemCreate,
    CartItemQuantityUpdate,
    CartItemResponse,
    CartMealResponse,
    CartResponse,
)

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("", response_model=CartResponse)
def get_cart(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CartResponse:
    """Return the authenticated user's persisted cart."""
    return _cart_response(session, user.id)


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: CartItemCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CartResponse:
    """Add an available meal, or increment its existing cart quantity."""
    meal = session.get(Meal, payload.meal_id)
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    if not meal.available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unavailable meals cannot be added to the cart",
        )

    item = session.scalar(
        select(CartItem).where(
            CartItem.user_id == user.id,
            CartItem.meal_id == payload.meal_id,
        )
    )
    if item is None:
        session.add(CartItem(user_id=user.id, meal_id=payload.meal_id, quantity=payload.quantity))
    else:
        new_quantity = item.quantity + payload.quantity
        if new_quantity > 99:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cart item quantity cannot exceed 99",
            )
        item.quantity = new_quantity

    session.commit()
    return _cart_response(session, user.id)


@router.patch("/items/{item_id}", response_model=CartResponse)
def change_cart_item_quantity(
    item_id: UUID,
    payload: CartItemQuantityUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> CartResponse:
    """Set a cart quantity while enforcing ownership and availability."""
    item = session.scalar(
        select(CartItem)
        .options(joinedload(CartItem.meal))
        .where(CartItem.id == item_id, CartItem.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
    if payload.quantity > item.quantity and not item.meal.available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unavailable meals cannot be increased in the cart",
        )

    item.quantity = payload.quantity
    session.commit()
    return _cart_response(session, user.id)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cart_item(
    item_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    """Remove one item from the authenticated user's cart."""
    item = session.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _cart_response(session: Session, user_id: UUID) -> CartResponse:
    items = session.scalars(
        select(CartItem)
        .options(joinedload(CartItem.meal))
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at, CartItem.id)
    ).all()
    response_items = [
        CartItemResponse(
            id=item.id,
            quantity=item.quantity,
            line_total_nok=item.meal.price_nok * item.quantity,
            meal=CartMealResponse(
                id=item.meal.id,
                name=item.meal.name,
                image_url=item.meal.image_url,
                price_nok=item.meal.price_nok,
                available=item.meal.available,
            ),
        )
        for item in items
    ]
    return CartResponse(
        items=response_items,
        total_quantity=sum(item.quantity for item in items),
        total_nok=sum(
            (item.line_total_nok for item in response_items),
            start=Decimal("0.00"),
        ),
    )
