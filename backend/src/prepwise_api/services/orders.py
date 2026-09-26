from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.models import Order
from prepwise_api.schemas import OrderDetailResponse, OrderItemResponse, OrderSummaryResponse
from prepwise_api.services import ApplicationNotFoundError


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
