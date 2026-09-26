import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from prepwise_api.api.service_errors import raise_service_http_error
from prepwise_api.auth import get_current_user
from prepwise_api.database import get_session
from prepwise_api.models import User
from prepwise_api.schemas import OrderCreate, OrderDetailResponse, OrderSummaryResponse
from prepwise_api.services import ApplicationServiceError
from prepwise_api.services.orders import (
    create_user_order,
    get_user_order,
    list_user_orders,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])
logger = logging.getLogger("prepwise.domain.orders")


@router.post("", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OrderDetailResponse:
    """Create an order and clear the cart in one database transaction."""
    try:
        created_order = create_user_order(session, user.id, payload.pickup_location_id)
    except ApplicationServiceError as error:
        raise_service_http_error(error)
    logger.info(
        "Order created",
        extra={
            "event": "order.created",
            "order_id": str(created_order.id),
            "item_count": len(created_order.items),
            "total_nok": str(created_order.total_nok),
        },
    )
    return created_order


@router.get("", response_model=list[OrderSummaryResponse])
def list_orders(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[OrderSummaryResponse]:
    """Return only the authenticated user's orders, newest first."""
    return list_user_orders(session, user.id)


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order(
    order_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OrderDetailResponse:
    """Return an owned order without revealing another user's order."""
    try:
        return get_user_order(session, user.id, order_id)
    except ApplicationServiceError as error:
        raise_service_http_error(error)
