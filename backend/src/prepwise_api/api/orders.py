import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from prepwise_api.api.service_errors import raise_service_http_error
from prepwise_api.auth import get_current_user
from prepwise_api.database import get_session
from prepwise_api.models import User
from prepwise_api.schemas import OrderCreate, OrderDetailResponse, OrderSummaryResponse
from prepwise_api.schemas.order import OrderReviewRequest, OrderReviewResponse
from prepwise_api.services import (
    ApplicationNotFoundError,
    ApplicationServiceError,
    ApplicationValidationError,
)
from prepwise_api.services.localization import Language
from prepwise_api.services.orders import (
    cancel_user_order,
    create_user_order,
    get_user_order,
    list_user_orders,
    review_user_order,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])
logger = logging.getLogger("prepwise.domain.orders")


@router.post("", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    lang: Language = "no",
) -> OrderDetailResponse | JSONResponse:
    """Create an order and clear the cart in one database transaction."""
    try:
        created_order = create_user_order(
            session,
            user.id,
            payload.pickup_location_id,
            pickup_date=payload.pickup_date,
            pickup_slot=payload.pickup_slot,
            group_id=payload.group_id,
            review_fingerprint=payload.review_fingerprint,
            idempotency_key=payload.idempotency_key,
            allow_unassigned_with_groups=True,
            lang=lang,
        )
    except ApplicationServiceError as error:
        if error.code == "checkout_not_created":
            return JSONResponse(
                status_code=404
                if isinstance(error, ApplicationNotFoundError)
                else 422
                if isinstance(error, ApplicationValidationError)
                else 409,
                content={
                    "code": "checkout_not_created",
                    "detail": error.message,
                    "request_id": str(request.state.request_id),
                },
            )
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


@router.post("/review", response_model=OrderReviewResponse)
def review_order(
    payload: OrderReviewRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    lang: Language = "no",
) -> OrderReviewResponse:
    """Review exactly one persisted scope without changing the cart."""
    try:
        return review_user_order(
            session,
            user.id,
            payload.pickup_location_id,
            pickup_date=payload.pickup_date,
            pickup_slot=payload.pickup_slot,
            group_id=payload.group_id,
            allow_unassigned_with_groups=True,
            lang=lang,
        )
    except ApplicationServiceError as error:
        raise_service_http_error(error)


@router.post("/{order_id}/cancel", response_model=OrderDetailResponse)
def cancel_order(
    order_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    lang: Language = "no",
) -> OrderDetailResponse:
    try:
        cancelled = cancel_user_order(session, user.id, order_id, lang=lang)
    except ApplicationServiceError as error:
        raise_service_http_error(error)
    logger.info(
        "Order cancelled", extra={"event": "order.cancelled", "order_id": str(cancelled.id)}
    )
    return cancelled


@router.get("", response_model=list[OrderSummaryResponse])
def list_orders(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    lang: Language = "no",
) -> list[OrderSummaryResponse]:
    """Return only the authenticated user's orders, newest first."""
    return list_user_orders(session, user.id)


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order(
    order_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    lang: Language = "no",
) -> OrderDetailResponse:
    """Return an owned order without revealing another user's order."""
    try:
        return get_user_order(session, user.id, order_id, lang=lang)
    except ApplicationServiceError as error:
        raise_service_http_error(error)
