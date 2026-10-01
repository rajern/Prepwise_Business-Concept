from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from prepwise_api.schemas.pickup import PickupSlot


class CartMealResponse(BaseModel):
    id: UUID
    name: str
    image_url: str | None
    price_nok: Decimal
    available: bool


class CartItemResponse(BaseModel):
    id: UUID
    quantity: int
    line_total_nok: Decimal
    meal: CartMealResponse
    group_id: UUID | None = None


class CartGroupResponse(BaseModel):
    id: UUID
    pickup_location_id: UUID | None
    pickup_date: date | None
    pickup_slot: PickupSlot | None
    items: list[CartItemResponse]
    total_quantity: int
    total_nok: Decimal


class CartGroupWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pickup_location_id: UUID | None = None
    pickup_date: date | None = None
    pickup_slot: PickupSlot | None = None


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_quantity: int
    total_nok: Decimal
    groups: list[CartGroupResponse] = Field(default_factory=list)


class CartItemCreate(BaseModel):
    meal_id: UUID
    quantity: int = Field(ge=1, le=99)
    group_id: UUID | None = None


class CartItemQuantityUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)
    group_id: UUID | None = None
