from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from prepwise_api.models import OrderStatus


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pickup_location_id: UUID


class OrderSummaryResponse(BaseModel):
    id: UUID
    status: OrderStatus
    total_nok: Decimal
    created_at: datetime
    pickup_start_at: datetime
    pickup_end_at: datetime
    pickup_location_name: str
    pickup_location_address: str


class OrderItemResponse(BaseModel):
    meal_id: UUID
    meal_name: str
    quantity: int
    unit_price_nok: Decimal
    line_total_nok: Decimal


class OrderDetailResponse(OrderSummaryResponse):
    items: list[OrderItemResponse]
