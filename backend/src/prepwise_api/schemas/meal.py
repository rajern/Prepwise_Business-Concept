from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class AllergenResponse(BaseModel):
    code: str
    name: str


class MealResponse(BaseModel):
    id: UUID
    name: str
    description: str
    image_url: str | None
    price_nok: Decimal
    calories: int
    protein_grams: Decimal
    carbohydrate_grams: Decimal
    fat_grams: Decimal
    ingredients: list[str]
    allergens: list[AllergenResponse]
