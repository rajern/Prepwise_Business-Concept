from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from prepwise_api.models import OrderStatus
from prepwise_api.schemas.pickup import PickupSlot


class OrderReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pickup_location_id: UUID
    pickup_date: date
    pickup_slot: PickupSlot
    group_id: UUID | None = None


class OrderCreate(OrderReviewRequest):
    review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: UUID


class OrderSummaryResponse(BaseModel):
    id: UUID
    status: OrderStatus
    total_nok: Decimal
    created_at: datetime
    pickup_start_at: datetime
    pickup_end_at: datetime
    pickup_location_name: str
    pickup_location_address: str
    cancellation_deadline: datetime
    can_cancel: bool


class OrderItemResponse(BaseModel):
    meal_id: UUID
    meal_name: str
    quantity: int
    unit_price_nok: Decimal
    line_total_nok: Decimal


class OrderDetailResponse(OrderSummaryResponse):
    items: list[OrderItemResponse]


class OrderReviewResponse(BaseModel):
    review_fingerprint: str
    items: list[OrderItemResponse]
    total_quantity: int
    total_nok: Decimal
    pickup_location_name: str
    pickup_location_address: str
    pickup_start_at: datetime
    pickup_end_at: datetime


class AdminOrderSummaryResponse(OrderSummaryResponse):
    customer_email: str | None
    customer_display_name: str | None


class AdminOrderDetailResponse(AdminOrderSummaryResponse):
    items: list[OrderItemResponse]


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus
