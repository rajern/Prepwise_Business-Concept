from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from prepwise_api.models import CartGroup, CartItem, Meal, PickupLocation
from prepwise_api.schemas import CartItemResponse, CartMealResponse, CartResponse
from prepwise_api.schemas.cart import CartGroupResponse, CartGroupWrite
from prepwise_api.schemas.pickup import PickupSlot
from prepwise_api.services import (
    ApplicationConflictError,
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from prepwise_api.services.localization import Language, localized
from prepwise_api.services.pickup_schedule import validate_pickup_selection


def lock_user_cart(session: Session, user_id: UUID) -> None:
    """Serialize cart transactions without granting runtime UPDATE access to users."""
    if session.get_bind().dialect.name == "postgresql":
        key = int.from_bytes(user_id.bytes[:8], "big", signed=True)
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def owned_cart_group(session: Session, user_id: UUID, group_id: UUID) -> CartGroup:
    group = session.scalar(
        select(CartGroup)
        .where(CartGroup.id == group_id, CartGroup.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    if group is None:
        raise ApplicationNotFoundError("Cart group not found")
    return group


def write_user_cart_group(
    session: Session,
    user_id: UUID,
    payload: CartGroupWrite,
    *,
    group_id: UUID | None = None,
    lang: Language = "no",
) -> CartResponse:
    lock_user_cart(session, user_id)
    group = owned_cart_group(session, user_id, group_id) if group_id else CartGroup(user_id=user_id)
    fields = payload.model_fields_set
    location_id = (
        payload.pickup_location_id if "pickup_location_id" in fields else group.pickup_location_id
    )
    pickup_date = payload.pickup_date if "pickup_date" in fields else group.pickup_date
    pickup_slot = payload.pickup_slot if "pickup_slot" in fields else group.pickup_slot
    if location_id is not None:
        location = session.get(PickupLocation, location_id, populate_existing=True)
        if location is None or not location.active:
            raise ApplicationConflictError("Pickup location is unavailable")
    if (pickup_date is None) != (pickup_slot is None):
        raise ApplicationValidationError("Pickup date and time must be selected together")
    if pickup_date is not None and pickup_slot is not None:
        validate_pickup_selection(pickup_date, pickup_slot)
    group.pickup_location_id, group.pickup_date, group.pickup_slot = (
        location_id,
        pickup_date,
        pickup_slot,
    )
    session.add(group)
    session.commit()
    return get_user_cart(session, user_id, lang=lang)


def remove_user_cart_group(session: Session, user_id: UUID, group_id: UUID) -> None:
    lock_user_cart(session, user_id)
    group = owned_cart_group(session, user_id, group_id)
    if (
        session.scalar(select(CartItem.id).where(CartItem.group_id == group_id).limit(1))
        is not None
    ):
        raise ApplicationConflictError("Move or remove the group's meals before deleting it")
    session.delete(group)
    session.commit()


def get_user_cart(session: Session, user_id: UUID, *, lang: Language = "no") -> CartResponse:
    items = session.scalars(
        select(CartItem)
        .options(joinedload(CartItem.meal))
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at, CartItem.id)
        .execution_options(populate_existing=True)
    ).all()
    response_items = [
        CartItemResponse(
            id=item.id,
            group_id=item.group_id,
            quantity=item.quantity,
            line_total_nok=item.meal.price_nok * item.quantity,
            meal=CartMealResponse(
                id=item.meal.id,
                name=localized(item.meal.name, item.meal.name_en, lang),
                image_url=item.meal.image_url,
                price_nok=item.meal.price_nok,
                available=item.meal.available,
            ),
        )
        for item in items
    ]
    groups = session.scalars(
        select(CartGroup)
        .where(CartGroup.user_id == user_id)
        .order_by(CartGroup.created_at, CartGroup.id)
        .execution_options(populate_existing=True)
    ).all()
    response_groups = []
    for group in groups:
        group_items = [item for item in response_items if item.group_id == group.id]
        response_groups.append(
            CartGroupResponse(
                id=group.id,
                pickup_location_id=group.pickup_location_id,
                pickup_date=group.pickup_date,
                pickup_slot=cast(PickupSlot | None, group.pickup_slot),
                items=group_items,
                total_quantity=sum(item.quantity for item in group_items),
                total_nok=sum((item.line_total_nok for item in group_items), start=Decimal("0.00")),
            )
        )
    return CartResponse(
        items=response_items,
        groups=response_groups,
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
    *,
    group_id: UUID | None = None,
    lang: Language = "no",
) -> CartResponse:
    lock_user_cart(session, user_id)
    if group_id is not None:
        owned_cart_group(session, user_id, group_id)
    if not 1 <= quantity <= 99:
        raise ApplicationValidationError("Cart item quantity must be between 1 and 99")

    meal = session.get(Meal, meal_id, populate_existing=True)
    if meal is None:
        raise ApplicationNotFoundError("Meal not found")
    if not meal.available:
        raise ApplicationConflictError("Unavailable meals cannot be added to the cart")

    item = session.scalar(
        select(CartItem)
        .where(
            CartItem.user_id == user_id,
            CartItem.meal_id == meal_id,
            CartItem.group_id == group_id,
        )
        .execution_options(populate_existing=True)
    )
    if item is None:
        session.add(
            CartItem(user_id=user_id, meal_id=meal_id, quantity=quantity, group_id=group_id)
        )
    else:
        new_quantity = item.quantity + quantity
        if new_quantity > 99:
            raise ApplicationValidationError("Cart item quantity cannot exceed 99")
        item.quantity = new_quantity

    session.commit()
    return get_user_cart(session, user_id, lang=lang)


def set_user_cart_item_quantity(
    session: Session,
    user_id: UUID,
    item_id: UUID,
    quantity: int,
    *,
    group_id: UUID | None = None,
    move_group: bool = False,
    lang: Language = "no",
) -> CartResponse:
    lock_user_cart(session, user_id)
    if not 1 <= quantity <= 99:
        raise ApplicationValidationError("Cart item quantity must be between 1 and 99")

    item = session.scalar(
        select(CartItem)
        .options(joinedload(CartItem.meal))
        .where(CartItem.id == item_id, CartItem.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise ApplicationNotFoundError("Cart item not found")
    if quantity > item.quantity and not item.meal.available:
        raise ApplicationConflictError("Unavailable meals cannot be increased in the cart")

    if move_group and group_id != item.group_id:
        if group_id is not None:
            owned_cart_group(session, user_id, group_id)
        existing = session.scalar(
            select(CartItem)
            .where(
                CartItem.user_id == user_id,
                CartItem.meal_id == item.meal_id,
                CartItem.group_id == group_id,
                CartItem.id != item.id,
            )
            .execution_options(populate_existing=True)
        )
        if existing is not None:
            if existing.quantity + quantity > 99:
                raise ApplicationValidationError("Cart item quantity cannot exceed 99")
            existing.quantity += quantity
            session.delete(item)
        else:
            item.quantity, item.group_id = quantity, group_id
    else:
        item.quantity = quantity
    session.commit()
    return get_user_cart(session, user_id, lang=lang)


def remove_user_cart_item(
    session: Session,
    user_id: UUID,
    item_id: UUID,
    *,
    lang: Language = "no",
) -> CartResponse:
    lock_user_cart(session, user_id)
    item = session.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id)
    )
    if item is None:
        raise ApplicationNotFoundError("Cart item not found")

    session.delete(item)
    session.commit()
    return get_user_cart(session, user_id, lang=lang)
