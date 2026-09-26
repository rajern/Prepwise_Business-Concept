import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.auth import require_admin
from prepwise_api.database import get_session
from prepwise_api.models import Order, OrderStatus, User
from prepwise_api.schemas import (
    AdminOrderDetailResponse,
    AdminOrderSummaryResponse,
    OrderItemResponse,
    OrderStatusUpdate,
)
from prepwise_api.services.orders import order_summary_response

router = APIRouter(prefix="/api/admin/orders", tags=["admin orders"])
logger = logging.getLogger("prepwise.domain.orders")
NEXT_STATUS = {
    OrderStatus.RECEIVED: OrderStatus.PREPARING,
    OrderStatus.PREPARING: OrderStatus.READY_FOR_PICKUP,
    OrderStatus.READY_FOR_PICKUP: OrderStatus.COMPLETED,
}


@router.get("", response_model=list[AdminOrderSummaryResponse])
def list_admin_orders(
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[AdminOrderSummaryResponse]:
    """Return all orders, newest first, for fulfilment administration."""
    orders = session.scalars(
        select(Order)
        .options(selectinload(Order.user))
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    return [_admin_order_summary_response(order) for order in orders]


@router.get("/{order_id}", response_model=AdminOrderDetailResponse)
def get_admin_order(
    order_id: UUID,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminOrderDetailResponse:
    """Return one order with its historical line items."""
    order = _get_admin_order(session, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return _admin_order_detail_response(order)


@router.patch("/{order_id}/status", response_model=AdminOrderDetailResponse)
def update_admin_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> AdminOrderDetailResponse:
    """Advance an order by exactly one step in the agreed lifecycle."""
    order = session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    allowed_status = NEXT_STATUS.get(order.status)
    if payload.status != allowed_status:
        expected = allowed_status.value if allowed_status else "no further status"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Order cannot move from {order.status.value} to {payload.status.value}; "
                f"expected {expected}"
            ),
        )

    previous_status = order.status
    order.status = payload.status
    session.commit()
    saved_order = _get_admin_order(session, order_id)
    if saved_order is None:  # pragma: no cover - defensive after successful commit
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Updated order could not be loaded",
        )
    logger.info(
        "Order status updated",
        extra={
            "event": "order.status_updated",
            "order_id": str(saved_order.id),
            "from_status": previous_status.value,
            "to_status": saved_order.status.value,
        },
    )
    return _admin_order_detail_response(saved_order)


def _get_admin_order(session: Session, order_id: UUID) -> Order | None:
    return session.scalar(
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.items))
        .where(Order.id == order_id)
    )


def _admin_order_summary_response(order: Order) -> AdminOrderSummaryResponse:
    return AdminOrderSummaryResponse(
        **order_summary_response(order).model_dump(),
        customer_email=order.user.email,
        customer_display_name=order.user.display_name,
    )


def _admin_order_detail_response(order: Order) -> AdminOrderDetailResponse:
    return AdminOrderDetailResponse(
        **_admin_order_summary_response(order).model_dump(),
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
