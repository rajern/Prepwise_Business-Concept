import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.models import CartItem, Meal, Order, OrderConfirmation, OrderItem, PickupLocation
from prepwise_api.schemas import OrderDetailResponse, OrderItemResponse, OrderSummaryResponse
from prepwise_api.services import ApplicationConflictError, ApplicationNotFoundError

OSLO_TIME_ZONE = ZoneInfo("Europe/Oslo")
ORDER_CONFIRMATION_LIFETIME = timedelta(minutes=15)


def create_user_order(
    session: Session,
    user_id: UUID,
    pickup_location_id: UUID,
) -> OrderDetailResponse:
    """Create an order through the same validated transaction used by every caller."""
    try:
        location, cart_items, meals = _load_checkout_state(
            session,
            user_id,
            pickup_location_id,
            lock=True,
        )
        order_id = _create_order_from_checkout_state(
            session,
            user_id,
            location,
            cart_items,
            meals,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _load_created_order(session, order_id, user_id)


def prepare_user_order_confirmation(
    session: Session,
    user_id: UUID,
    pickup_location_id: UUID,
    request_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Create a short-lived token for a later, explicit user confirmation turn."""
    current_time = now or datetime.now(UTC)
    location, cart_items, meals = _load_checkout_state(
        session,
        user_id,
        pickup_location_id,
        lock=False,
    )
    confirmation = OrderConfirmation(
        user_id=user_id,
        pickup_location_id=pickup_location_id,
        cart_fingerprint=_cart_fingerprint(cart_items, meals),
        issued_request_id=request_id,
        expires_at=current_time + ORDER_CONFIRMATION_LIFETIME,
    )
    session.add(confirmation)
    session.commit()
    token = str(confirmation.id)
    total_nok = sum(
        (meals[item.meal_id].price_nok * item.quantity for item in cart_items),
        start=Decimal("0.00"),
    )
    return {
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
    }


def confirm_user_order(
    session: Session,
    user_id: UUID,
    confirmation_token: UUID,
    request_id: str,
    user_message: str,
    *,
    now: datetime | None = None,
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

        location, cart_items, meals = _load_checkout_state(
            session,
            user_id,
            confirmation.pickup_location_id,
            lock=True,
        )
        if _cart_fingerprint(cart_items, meals) != confirmation.cart_fingerprint:
            raise ApplicationConflictError(
                "Cart changed after preparation; prepare the order again"
            )
        order_id = _create_order_from_checkout_state(
            session,
            user_id,
            location,
            cart_items,
            meals,
        )
        confirmation.consumed_at = current_time
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _load_created_order(session, order_id, user_id)


def list_user_orders(session: Session, user_id: UUID) -> list[OrderSummaryResponse]:
    orders = session.scalars(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    return [order_summary_response(order) for order in orders]


def get_user_order(session: Session, user_id: UUID, order_id: UUID) -> OrderDetailResponse:
    order = load_owned_order(session, order_id, user_id)
    if order is None:
        raise ApplicationNotFoundError("Order not found")
    return order_detail_response(order)


def load_owned_order(session: Session, order_id: UUID, user_id: UUID) -> Order | None:
    return session.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.user_id == user_id)
    )


def _load_checkout_state(
    session: Session,
    user_id: UUID,
    pickup_location_id: UUID,
    *,
    lock: bool,
) -> tuple[PickupLocation, list[CartItem], dict[UUID, Meal]]:
    location_query = select(PickupLocation).where(PickupLocation.id == pickup_location_id)
    cart_query = (
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at, CartItem.id)
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
    meal_query = select(Meal).where(Meal.id.in_(meal_ids))
    if lock:
        meal_query = meal_query.with_for_update()
    meals = {meal.id: meal for meal in session.scalars(meal_query)}
    if len(meals) != len(meal_ids) or any(not meals[item.meal_id].available for item in cart_items):
        raise ApplicationConflictError("Cart contains an unavailable meal")
    return location, cart_items, meals


def _create_order_from_checkout_state(
    session: Session,
    user_id: UUID,
    location: PickupLocation,
    cart_items: list[CartItem],
    meals: dict[UUID, Meal],
) -> UUID:
    pickup_start_at, pickup_end_at = _next_pickup_window()
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
        pickup_location_address=(
            f"{location.address_line}, {location.postal_code} {location.city}"
        ),
        total_nok=total_nok,
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
                quantity=cart_item.quantity,
                unit_price_nok=meal.price_nok,
            )
        )
    session.execute(delete(CartItem).where(CartItem.id.in_([item.id for item in cart_items])))
    return order.id


def _cart_fingerprint(cart_items: list[CartItem], meals: dict[UUID, Meal]) -> str:
    payload = [
        {
            "meal_id": str(item.meal_id),
            "quantity": item.quantity,
            "unit_price_nok": str(meals[item.meal_id].price_nok),
        }
        for item in sorted(cart_items, key=lambda item: str(item.meal_id))
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_created_order(session: Session, order_id: UUID, user_id: UUID) -> OrderDetailResponse:
    created_order = load_owned_order(session, order_id, user_id)
    if created_order is None:  # pragma: no cover - defensive after a successful commit
        raise RuntimeError("Created order could not be loaded")
    return order_detail_response(created_order)


def _next_pickup_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    local_now = now.astimezone(OSLO_TIME_ZONE) if now else datetime.now(OSLO_TIME_ZONE)
    pickup_date = local_now.date() + timedelta(days=1)
    return (
        datetime.combine(pickup_date, time(hour=16), OSLO_TIME_ZONE),
        datetime.combine(pickup_date, time(hour=18), OSLO_TIME_ZONE),
    )


def order_summary_response(order: Order) -> OrderSummaryResponse:
    return OrderSummaryResponse(
        id=order.id,
        status=order.status,
        total_nok=order.total_nok,
        created_at=order.created_at,
        pickup_start_at=order.pickup_start_at,
        pickup_end_at=order.pickup_end_at,
        pickup_location_name=order.pickup_location_name,
        pickup_location_address=order.pickup_location_address,
    )


def order_detail_response(order: Order) -> OrderDetailResponse:
    return OrderDetailResponse(
        **order_summary_response(order).model_dump(),
        items=[
            OrderItemResponse(
                meal_id=item.meal_id,
                meal_name=item.meal_name,
                quantity=item.quantity,
                unit_price_nok=item.unit_price_nok,
                line_total_nok=item.unit_price_nok * item.quantity,
            )
            for item in order.items
        ],
    )
