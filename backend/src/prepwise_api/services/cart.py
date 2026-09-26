from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from prepwise_api.models import CartItem, Meal
from prepwise_api.schemas import CartItemResponse, CartMealResponse, CartResponse
from prepwise_api.services import (
    ApplicationConflictError,
    ApplicationNotFoundError,
    ApplicationValidationError,
)


def get_user_cart(session: Session, user_id: UUID) -> CartResponse:
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


def add_user_cart_item(
    session: Session,
    user_id: UUID,
    meal_id: UUID,
    quantity: int,
) -> CartResponse:
    if not 1 <= quantity <= 99:
        raise ApplicationValidationError("Cart item quantity must be between 1 and 99")

    meal = session.get(Meal, meal_id)
    if meal is None:
        raise ApplicationNotFoundError("Meal not found")
    if not meal.available:
        raise ApplicationConflictError("Unavailable meals cannot be added to the cart")

    item = session.scalar(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.meal_id == meal_id,
        )
    )
    if item is None:
        session.add(CartItem(user_id=user_id, meal_id=meal_id, quantity=quantity))
    else:
        new_quantity = item.quantity + quantity
        if new_quantity > 99:
            raise ApplicationValidationError("Cart item quantity cannot exceed 99")
        item.quantity = new_quantity

    session.commit()
    return get_user_cart(session, user_id)


def set_user_cart_item_quantity(
    session: Session,
    user_id: UUID,
    item_id: UUID,
    quantity: int,
) -> CartResponse:
    if not 1 <= quantity <= 99:
        raise ApplicationValidationError("Cart item quantity must be between 1 and 99")

    item = session.scalar(
        select(CartItem)
        .options(joinedload(CartItem.meal))
        .where(CartItem.id == item_id, CartItem.user_id == user_id)
    )
    if item is None:
        raise ApplicationNotFoundError("Cart item not found")
    if quantity > item.quantity and not item.meal.available:
        raise ApplicationConflictError("Unavailable meals cannot be increased in the cart")

    item.quantity = quantity
    session.commit()
    return get_user_cart(session, user_id)


def remove_user_cart_item(
    session: Session,
    user_id: UUID,
    item_id: UUID,
) -> CartResponse:
    item = session.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id)
    )
    if item is None:
        raise ApplicationNotFoundError("Cart item not found")

    session.delete(item)
    session.commit()
    return get_user_cart(session, user_id)
