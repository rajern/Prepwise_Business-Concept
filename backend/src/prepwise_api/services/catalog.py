from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.models import Ingredient, Meal
from prepwise_api.schemas import AllergenResponse, MealDetailResponse, MealResponse
from prepwise_api.services import ApplicationNotFoundError


@dataclass(frozen=True, slots=True)
class MealSearchFilters:
    query: str | None = None
    min_protein_grams: Decimal | None = None
    max_calories: int | None = None
    max_price_nok: Decimal | None = None
    limit: int | None = None


def search_available_meals(
    session: Session,
    filters: MealSearchFilters | None = None,
) -> list[MealResponse]:
    """Search the available catalogue using server-controlled filters and limits."""
    active_filters = filters or MealSearchFilters()
    statement = (
        select(Meal)
        .where(Meal.available.is_(True))
        .options(selectinload(Meal.ingredients), selectinload(Meal.allergens))
        .order_by(Meal.name)
    )
    if active_filters.query:
        escaped_query = _escape_like(active_filters.query)
        pattern = f"%{escaped_query}%"
        statement = statement.where(
            or_(
                Meal.name.ilike(pattern, escape="\\"),
                Meal.description.ilike(pattern, escape="\\"),
                Meal.ingredients.any(Ingredient.name.ilike(pattern, escape="\\")),
            )
        )
    if active_filters.min_protein_grams is not None:
        statement = statement.where(Meal.protein_grams >= active_filters.min_protein_grams)
    if active_filters.max_calories is not None:
        statement = statement.where(Meal.calories <= active_filters.max_calories)
    if active_filters.max_price_nok is not None:
        statement = statement.where(Meal.price_nok <= active_filters.max_price_nok)
    if active_filters.limit is not None:
        statement = statement.limit(active_filters.limit)

    return [meal_response(meal) for meal in session.scalars(statement).unique().all()]


def get_meal_details(session: Session, meal_id: UUID) -> MealDetailResponse:
    """Load one meal and preserve its current availability state."""
    meal = session.scalar(
        select(Meal)
        .where(Meal.id == meal_id)
        .options(selectinload(Meal.ingredients), selectinload(Meal.allergens))
    )
    if meal is None:
        raise ApplicationNotFoundError("Meal not found")
    return MealDetailResponse(**meal_response(meal).model_dump(), available=meal.available)


def meal_response(meal: Meal) -> MealResponse:
    return MealResponse(
        id=meal.id,
        name=meal.name,
        description=meal.description,
        image_url=meal.image_url,
        price_nok=meal.price_nok,
        calories=meal.calories,
        protein_grams=meal.protein_grams,
        carbohydrate_grams=meal.carbohydrate_grams,
        fat_grams=meal.fat_grams,
        ingredients=[ingredient.name for ingredient in meal.ingredients],
        allergens=[
            AllergenResponse(code=allergen.code, name=allergen.name)
            for allergen in sorted(meal.allergens, key=lambda item: item.name)
        ],
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
