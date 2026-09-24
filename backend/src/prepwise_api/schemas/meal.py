from decimal import Decimal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


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


class MealDetailResponse(MealResponse):
    available: bool


class MealAdminWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    image_url: AnyHttpUrl | None = None
    price_nok: Decimal = Field(ge=0, le=10000)
    calories: int = Field(ge=0, le=10000)
    protein_grams: Decimal = Field(ge=0, le=5000)
    carbohydrate_grams: Decimal = Field(ge=0, le=5000)
    fat_grams: Decimal = Field(ge=0, le=5000)
    ingredients: list[str] = Field(min_length=1, max_length=100)
    allergen_codes: list[str] = Field(default_factory=list, max_length=50)
    available: bool = True

    @field_validator("name", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("ingredients")
    @classmethod
    def normalize_ingredients(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            ingredient = value.strip()
            key = ingredient.casefold()
            if not ingredient:
                raise ValueError("ingredients must not contain blank values")
            if len(ingredient) > 200:
                raise ValueError("ingredient names cannot exceed 200 characters")
            if key not in seen:
                normalized.append(ingredient)
                seen.add(key)
        if not normalized:
            raise ValueError("at least one ingredient is required")
        return normalized

    @field_validator("allergen_codes")
    @classmethod
    def normalize_allergen_codes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        if any(not value for value in normalized):
            raise ValueError("allergen codes must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("allergen codes must be unique")
        return normalized
