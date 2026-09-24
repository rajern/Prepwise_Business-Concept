from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.auth import get_current_user
from prepwise_api.database import get_session
from prepwise_api.models import CartItem, Meal, Order, OrderItem, PickupLocation, User
from prepwise_api.schemas import (
    OrderCreate,
    OrderDetailResponse,
    OrderItemResponse,
    OrderSummaryResponse,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])
OSLO_TIME_ZONE = ZoneInfo("Europe/Oslo")


@router.post("", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OrderDetailResponse:
    """Create an order and clear the cart in one database transaction."""
    try:
        location = session.scalar(
            select(PickupLocation)
            .where(PickupLocation.id == payload.pickup_location_id)
            .with_for_update()
        )
        if location is None or not location.active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Pickup location is unavailable",
            )

        cart_items = session.scalars(
            select(CartItem)
            .where(CartItem.user_id == user.id)
            .order_by(CartItem.created_at, CartItem.id)
            .with_for_update()
        ).all()
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cart is empty",
            )

        meal_ids = [item.meal_id for item in cart_items]
        meals = {
            meal.id: meal
            for meal in session.scalars(select(Meal).where(Meal.id.in_(meal_ids)).with_for_update())
        }
        if len(meals) != len(meal_ids) or any(
            not meals[item.meal_id].available for item in cart_items
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cart contains an unavailable meal",
            )

        pickup_start_at, pickup_end_at = _next_pickup_window()
        total_nok = sum(
            (meals[item.meal_id].price_nok * item.quantity for item in cart_items),
            start=Decimal("0.00"),
        )
        order = Order(
            user_id=user.id,
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

        checked_out_item_ids = [item.id for item in cart_items]
        session.execute(delete(CartItem).where(CartItem.id.in_(checked_out_item_ids)))
        order_id = order.id
        session.commit()
    except Exception:
        session.rollback()
        raise

    created_order = _get_owned_order(session, order_id, user.id)
    if created_order is None:  # pragma: no cover - defensive after a successful commit
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Created order could not be loaded",
        )
    return _order_detail_response(created_order)


@router.get("", response_model=list[OrderSummaryResponse])
def list_orders(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[OrderSummaryResponse]:
    """Return only the authenticated user's orders, newest first."""
    orders = session.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    return [_order_summary_response(order) for order in orders]


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order(
    order_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OrderDetailResponse:
    """Return an owned order without revealing another user's order."""
    order = _get_owned_order(session, order_id, user.id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return _order_detail_response(order)


def _get_owned_order(session: Session, order_id: UUID, user_id: UUID) -> Order | None:
    return session.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.user_id == user_id)
    )


def _order_summary_response(order: Order) -> OrderSummaryResponse:
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


def _order_detail_response(order: Order) -> OrderDetailResponse:
    return OrderDetailResponse(
        **_order_summary_response(order).model_dump(),
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


def _next_pickup_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    local_now = now.astimezone(OSLO_TIME_ZONE) if now else datetime.now(OSLO_TIME_ZONE)
    pickup_date = local_now.date() + timedelta(days=1)
    return (
        datetime.combine(pickup_date, time(hour=16), OSLO_TIME_ZONE),
        datetime.combine(pickup_date, time(hour=18), OSLO_TIME_ZONE),
    )
