from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


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


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_quantity: int
    total_nok: Decimal


class CartItemCreate(BaseModel):
    meal_id: UUID
    quantity: int = Field(ge=1, le=99)


class CartItemQuantityUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)
