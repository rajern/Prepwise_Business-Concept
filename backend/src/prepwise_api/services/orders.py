import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.models import (
    CartItem,
    Meal,
    Order,
    OrderConfirmation,
    OrderItem,
    OrderStatus,
    PickupLocation,
)
from prepwise_api.schemas import OrderDetailResponse, OrderItemResponse, OrderSummaryResponse
from prepwise_api.schemas.order import OrderReviewResponse
from prepwise_api.schemas.pickup import PickupSlot
from prepwise_api.services import (
    ApplicationConflictError,
    ApplicationNotFoundError,
    ApplicationServiceError,
    ApplicationValidationError,
)
from prepwise_api.services.cart import lock_user_cart, owned_cart_group
from prepwise_api.services.localization import Language, localized
from prepwise_api.services.pickup_schedule import validate_pickup_selection

OSLO_TIME_ZONE = ZoneInfo("Europe/Oslo")
ORDER_CONFIRMATION_LIFETIME = timedelta(minutes=15)


def create_user_order(
    session: Session,
    user_id: UUID,
    pickup_location_id: UUID,
    *,
    pickup_date: date,
    pickup_slot: PickupSlot,
    group_id: UUID | None = None,
    review_fingerprint: str | None = None,
    idempotency_key: UUID | None = None,
    allow_unassigned_with_groups: bool = False,
    lang: Language = "no",
) -> OrderDetailResponse:
    """Create an order through the same validated transaction used by every caller."""
    checked_absence = False
    try:
        lock_user_cart(session, user_id)
        if (review_fingerprint is None) != (idempotency_key is None):
            raise ApplicationValidationError("Review and idempotency key must be supplied together")
        request_hash = (
            _checkout_request_hash(
                pickup_location_id, pickup_date, pickup_slot, group_id, review_fingerprint
            )
            if review_fingerprint is not None
            else None
        )
        if idempotency_key is not None:
            existing = session.scalar(
                select(Order)
                .where(Order.user_id == user_id, Order.checkout_request_key == idempotency_key)
                .execution_options(populate_existing=True)
            )
            if existing is not None:
                if existing.checkout_request_hash != request_hash:
                    raise ApplicationConflictError(
                        "Checkout key was already used for another request"
                    )
                existing_id = existing.id
                session.rollback()
                return _load_created_order(session, existing_id, user_id, lang=lang)
            checked_absence = True
        _validate_group_selection(
            session, user_id, group_id, pickup_location_id, pickup_date, pickup_slot
        )
        pickup_start_at, pickup_end_at = validate_pickup_selection(pickup_date, pickup_slot)
        location, cart_items, meals = _load_checkout_state(
            session,
            user_id,
            pickup_location_id,
            lock=True,
            group_id=group_id,
            allow_unassigned_with_groups=allow_unassigned_with_groups,
        )
        if review_fingerprint is not None and review_fingerprint != _checkout_fingerprint(
            user_id, group_id, location, cart_items, meals, pickup_start_at, pickup_end_at
        ):
            raise ApplicationConflictError("Checkout changed; review the order again")
        order_id = _create_order_from_checkout_state(
            session,
            user_id,
            location,
            cart_items,
            meals,
            pickup_start_at,
            pickup_end_at,
            checkout_request_key=idempotency_key,
            checkout_request_hash=request_hash,
        )
        session.commit()
    except ApplicationServiceError as error:
        session.rollback()
        if checked_absence:
            # Under the cart lock we proved this exact key has no order, then
            # rejected before commit. This is stronger evidence than a generic
            # 4xx/auth failure after an earlier lost response.
            error.code = "checkout_not_created"
        raise
    except Exception:
        session.rollback()
        raise
    return _load_created_order(session, order_id, user_id, lang=lang)


def review_user_order(
    session: Session,
    user_id: UUID,
    pickup_location_id: UUID,
    *,
    pickup_date: date,
    pickup_slot: PickupSlot,
    group_id: UUID | None = None,
    allow_unassigned_with_groups: bool = False,
    lang: Language = "no",
) -> OrderReviewResponse:
    """Take a consistent read-only snapshot, with no checkout or cart preparation writes."""
    try:
        lock_user_cart(session, user_id)
        _validate_group_selection(
            session, user_id, group_id, pickup_location_id, pickup_date, pickup_slot
        )
        start, end = validate_pickup_selection(pickup_date, pickup_slot)
        location, items, meals = _load_checkout_state(
            session,
            user_id,
            pickup_location_id,
            lock=True,
            group_id=group_id,
            allow_unassigned_with_groups=allow_unassigned_with_groups,
        )
        response = OrderReviewResponse(
            review_fingerprint=_checkout_fingerprint(
                user_id, group_id, location, items, meals, start, end
            ),
            items=[
                OrderItemResponse(
                    meal_id=item.meal_id,
                    meal_name=localized(
                        meals[item.meal_id].name, meals[item.meal_id].name_en, lang
                    ),
                    quantity=item.quantity,
                    unit_price_nok=meals[item.meal_id].price_nok,
                    line_total_nok=meals[item.meal_id].price_nok * item.quantity,
                )
                for item in items
            ],
            total_quantity=sum(item.quantity for item in items),
            total_nok=sum(
                (meals[item.meal_id].price_nok * item.quantity for item in items),
                start=Decimal("0.00"),
            ),
            pickup_location_name=location.name,
            pickup_location_address=_location_address(location),
            pickup_start_at=start,
            pickup_end_at=end,
        )
    finally:
        # End the read-only transaction and release snapshot locks before user confirmation.
        session.rollback()
    return response


def _validate_group_selection(
    session: Session,
    user_id: UUID,
    group_id: UUID | None,
    location_id: UUID,
    pickup_date: date,
    pickup_slot: PickupSlot,
) -> None:
    if group_id is not None:
        group = owned_cart_group(session, user_id, group_id)
        if (group.pickup_location_id, group.pickup_date, group.pickup_slot) != (
            location_id,
            pickup_date,
            pickup_slot,
        ):
            raise ApplicationConflictError(
                "Pickup group changed; review its location, date and time again"
            )


def prepare_user_order_confirmation(
    session: Session,
    user_id: UUID,
    pickup_location_id: UUID,
    request_id: str,
    *,
    pickup_date: date,
    pickup_slot: PickupSlot,
    now: datetime | None = None,
) -> dict[str, object]:
    """Create a short-lived token for a later, explicit user confirmation turn."""
    current_time = now or datetime.now(UTC)
    lock_user_cart(session, user_id)
    pickup_start_at, pickup_end_at = validate_pickup_selection(
        pickup_date, pickup_slot, now=current_time
    )
    location, cart_items, meals = _load_checkout_state(
        session,
        user_id,
        pickup_location_id,
        lock=True,
    )
    confirmation = OrderConfirmation(
        user_id=user_id,
        pickup_location_id=pickup_location_id,
        cart_fingerprint=_checkout_fingerprint(
            user_id, None, location, cart_items, meals, pickup_start_at, pickup_end_at
        ),
        issued_request_id=request_id,
        expires_at=current_time + ORDER_CONFIRMATION_LIFETIME,
        pickup_start_at=pickup_start_at,
        pickup_end_at=pickup_end_at,
    )
    session.add(confirmation)
    session.flush()
    token = str(confirmation.id)
    total_nok = sum(
        (meals[item.meal_id].price_nok * item.quantity for item in cart_items),
        start=Decimal("0.00"),
    )
    result: dict[str, object] = {
        "confirmation_token": token,
        "confirmation_phrase": f"CONFIRM ORDER {token}",
        "expires_at": confirmation.expires_at.isoformat(),
        "pickup_location_name": location.name,
        "pickup_location_address": (
            f"{location.address_line}, {location.postal_code} {location.city}"
        ),
        "total_quantity": sum(item.quantity for item in cart_items),
        "total_nok": str(total_nok),
        "order_created": False,
        "pickup_start_at": pickup_start_at.isoformat(),
        "pickup_end_at": pickup_end_at.isoformat(),
    }
    session.commit()
    return result


def confirm_user_order(
    session: Session,
    user_id: UUID,
    confirmation_token: UUID,
    request_id: str,
    user_message: str,
    *,
    now: datetime | None = None,
    lang: Language = "no",
) -> OrderDetailResponse:
    """Consume a prior confirmation and create exactly the reviewed order."""
    expected_phrases = {
        f"confirm order {confirmation_token}".casefold(),
        f"bekreft ordre {confirmation_token}".casefold(),
    }
    if user_message.strip().casefold() not in expected_phrases:
        raise ApplicationConflictError(
            "Order creation requires the exact confirmation phrase from prepare_order"
        )

    current_time = now or datetime.now(UTC)
    try:
        confirmation = session.scalar(
            select(OrderConfirmation)
            .where(
                OrderConfirmation.id == confirmation_token,
                OrderConfirmation.user_id == user_id,
            )
            .with_for_update()
        )
        if confirmation is None:
            raise ApplicationNotFoundError("Order confirmation not found")
        if confirmation.issued_request_id == request_id:
            raise ApplicationConflictError("Order must be confirmed in a later request")
        if confirmation.consumed_at is not None:
            raise ApplicationConflictError("Order confirmation has already been used")
        expires_at = confirmation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= current_time:
            raise ApplicationConflictError("Order confirmation has expired")
        if confirmation.pickup_start_at is None or confirmation.pickup_end_at is None:
            raise ApplicationConflictError("Prepare the order again with a pickup date and time")
        start = confirmation.pickup_start_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        local_start = start.astimezone(OSLO_TIME_ZONE)
        slot: PickupSlot = "16-18" if local_start.hour == 16 else "18-20"
        pickup_start_at, pickup_end_at = validate_pickup_selection(
            local_start.date(), slot, now=current_time
        )
        stored_end = _aware_utc(confirmation.pickup_end_at)
        if start != pickup_start_at or stored_end != pickup_end_at:
            raise ApplicationConflictError("Order confirmation pickup time is invalid")

        location, cart_items, meals = _load_checkout_state(
            session,
            user_id,
            confirmation.pickup_location_id,
            lock=True,
        )
        if (
            _checkout_fingerprint(
                user_id, None, location, cart_items, meals, pickup_start_at, pickup_end_at
            )
            != confirmation.cart_fingerprint
        ):
            raise ApplicationConflictError(
                "Cart changed after preparation or pickup location changed; prepare the order again"
            )
        order_id = _create_order_from_checkout_state(
            session,
            user_id,
            location,
            cart_items,
            meals,
            pickup_start_at,
            pickup_end_at,
        )
        confirmation.consumed_at = current_time
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _load_created_order(session, order_id, user_id, lang=lang)


def list_user_orders(session: Session, user_id: UUID) -> list[OrderSummaryResponse]:
    orders = session.scalars(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .execution_options(populate_existing=True)
    ).all()
    return [order_summary_response(order) for order in orders]


def get_user_order(
    session: Session, user_id: UUID, order_id: UUID, *, lang: Language = "no"
) -> OrderDetailResponse:
    order = load_owned_order(session, order_id, user_id)
    if order is None:
        raise ApplicationNotFoundError("Order not found")
    return order_detail_response(order, lang=lang)


def cancellation_deadline(order: Order) -> datetime:
    pickup_day = _aware_utc(order.pickup_start_at).astimezone(OSLO_TIME_ZONE).date()
    return datetime.combine(pickup_day, time.min, OSLO_TIME_ZONE).astimezone(UTC)


def can_cancel_order(order: Order, *, now: datetime | None = None) -> bool:
    return order.status not in {OrderStatus.CANCELLED, OrderStatus.COMPLETED} and _aware_utc(
        now or datetime.now(UTC)
    ) < cancellation_deadline(order)


def cancel_user_order(
    session: Session,
    user_id: UUID,
    order_id: UUID,
    *,
    lang: Language = "no",
    now: datetime | None = None,
) -> OrderDetailResponse:
    """Keep historical items; serialize cancellation against fulfillment transitions."""
    try:
        order = session.scalar(
            select(Order)
            .where(Order.id == order_id, Order.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if order is None:
            raise ApplicationNotFoundError("Order not found")
        if not can_cancel_order(order, now=now):
            raise ApplicationConflictError(
                "Order cannot be cancelled on or after its pickup day "
                "or after completion/cancellation"
            )
        order.status = OrderStatus.CANCELLED
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _load_created_order(session, order_id, user_id, lang=lang)


def load_owned_order(session: Session, order_id: UUID, user_id: UUID) -> Order | None:
    return session.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.user_id == user_id)
        .execution_options(populate_existing=True)
    )


def _load_checkout_state(
    session: Session,
    user_id: UUID,
    pickup_location_id: UUID,
    *,
    lock: bool,
    group_id: UUID | None = None,
    allow_unassigned_with_groups: bool = False,
) -> tuple[PickupLocation, list[CartItem], dict[UUID, Meal]]:
    lock_user_cart(session, user_id)
    if group_id is None and not allow_unassigned_with_groups:
        grouped_item = session.scalar(
            select(CartItem.id)
            .where(CartItem.user_id == user_id, CartItem.group_id.is_not(None))
            .limit(1)
        )
        if grouped_item is not None:
            raise ApplicationConflictError(
                "Cart has separate pickup groups; review and order each group in the cart UI"
            )
    elif group_id is not None:
        owned_cart_group(session, user_id, group_id)
    location_query = (
        select(PickupLocation)
        .where(PickupLocation.id == pickup_location_id)
        .execution_options(populate_existing=True)
    )
    cart_query = (
        select(CartItem)
        .where(CartItem.user_id == user_id, CartItem.group_id == group_id)
        .order_by(CartItem.created_at, CartItem.id)
        .execution_options(populate_existing=True)
    )
    if lock:
        location_query = location_query.with_for_update()
        cart_query = cart_query.with_for_update()

    location = session.scalar(location_query)
    if location is None or not location.active:
        raise ApplicationConflictError("Pickup location is unavailable")

    cart_items = list(session.scalars(cart_query).all())
    if not cart_items:
        raise ApplicationConflictError("Cart is empty")

    meal_ids = [item.meal_id for item in cart_items]
    # All checkouts acquire shared catalog rows in the same order, including overlapping carts.
    meal_query = (
        select(Meal)
        .where(Meal.id.in_(meal_ids))
        .order_by(Meal.id)
        .execution_options(populate_existing=True)
    )
    if lock:
        meal_query = meal_query.with_for_update()
    meals = {meal.id: meal for meal in session.scalars(meal_query)}
    if len(meals) != len(set(meal_ids)) or any(
        not meals[item.meal_id].available for item in cart_items
    ):
        raise ApplicationConflictError("Cart contains an unavailable meal")
    return location, cart_items, meals


def _create_order_from_checkout_state(
    session: Session,
    user_id: UUID,
    location: PickupLocation,
    cart_items: list[CartItem],
    meals: dict[UUID, Meal],
    pickup_start_at: datetime,
    pickup_end_at: datetime,
    *,
    checkout_request_key: UUID | None = None,
    checkout_request_hash: str | None = None,
) -> UUID:
    total_nok = sum(
        (meals[item.meal_id].price_nok * item.quantity for item in cart_items),
        start=Decimal("0.00"),
    )
    order = Order(
        user_id=user_id,
        pickup_location_id=location.id,
        pickup_start_at=pickup_start_at,
        pickup_end_at=pickup_end_at,
        pickup_location_name=location.name,
        pickup_location_address=_location_address(location),
        total_nok=total_nok,
        checkout_request_key=checkout_request_key,
        checkout_request_hash=checkout_request_hash,
    )
    session.add(order)
    session.flush()

    for cart_item in cart_items:
        meal = meals[cart_item.meal_id]
        session.add(
            OrderItem(
                order_id=order.id,
                meal_id=meal.id,
                meal_name=meal.name,
                meal_name_en=meal.name_en,
                quantity=cart_item.quantity,
                unit_price_nok=meal.price_nok,
            )
        )
    session.execute(delete(CartItem).where(CartItem.id.in_([item.id for item in cart_items])))
    return order.id


def _location_address(location: PickupLocation) -> str:
    return f"{location.address_line}, {location.postal_code} {location.city}"


def _checkout_fingerprint(
    user_id: UUID,
    group_id: UUID | None,
    location: PickupLocation,
    items: list[CartItem],
    meals: dict[UUID, Meal],
    start: datetime,
    end: datetime,
) -> str:
    payload = {
        "user_id": str(user_id),
        "group_id": str(group_id) if group_id else None,
        "pickup_location_id": str(location.id),
        "pickup_location_name": location.name,
        "pickup_location_address": _location_address(location),
        "pickup_start_at": start.isoformat(),
        "pickup_end_at": end.isoformat(),
        "items": [
            {
                "line_id": str(item.id),
                "meal_id": str(item.meal_id),
                "quantity": item.quantity,
                "unit_price_nok": str(meals[item.meal_id].price_nok),
                "meal_name": meals[item.meal_id].name,
                "meal_name_en": meals[item.meal_id].name_en,
            }
            for item in sorted(items, key=lambda line: str(line.id))
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _checkout_request_hash(
    location_id: UUID,
    pickup_date: date,
    pickup_slot: PickupSlot,
    group_id: UUID | None,
    review_fingerprint: str,
) -> str:
    payload = {
        "pickup_location_id": str(location_id),
        "pickup_date": pickup_date.isoformat(),
        "pickup_slot": pickup_slot,
        "group_id": str(group_id) if group_id else None,
        "review_fingerprint": review_fingerprint,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load_created_order(
    session: Session, order_id: UUID, user_id: UUID, *, lang: Language = "no"
) -> OrderDetailResponse:
    created_order = load_owned_order(session, order_id, user_id)
    if created_order is None:  # pragma: no cover - defensive after a successful commit
        raise RuntimeError("Created order could not be loaded")
    return order_detail_response(created_order, lang=lang)


def order_summary_response(order: Order) -> OrderSummaryResponse:
    return OrderSummaryResponse(
        id=order.id,
        status=order.status,
        total_nok=order.total_nok,
        created_at=_aware_utc(order.created_at),
        pickup_start_at=_aware_utc(order.pickup_start_at),
        pickup_end_at=_aware_utc(order.pickup_end_at),
        pickup_location_name=order.pickup_location_name,
        pickup_location_address=order.pickup_location_address,
        cancellation_deadline=cancellation_deadline(order),
        can_cancel=can_cancel_order(order),
    )


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def order_detail_response(order: Order, *, lang: Language = "no") -> OrderDetailResponse:
    return OrderDetailResponse(
        **order_summary_response(order).model_dump(),
        items=[
            OrderItemResponse(
                meal_id=item.meal_id,
                meal_name=localized(item.meal_name, item.meal_name_en, lang),
                quantity=item.quantity,
                unit_price_nok=item.unit_price_nok,
                line_total_nok=item.unit_price_nok * item.quantity,
            )
            for item in order.items
        ],
    )
