import re
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.models import Ingredient, Meal
from prepwise_api.schemas import AllergenResponse, MealDetailResponse, MealResponse
from prepwise_api.services import ApplicationNotFoundError
from prepwise_api.services.localization import Language, localized

_SEARCH_TERM = re.compile(r"[\wæøåÆØÅ-]+", re.UNICODE)
_SEARCH_STOP_WORDS = {
    "and",
    "med",
    "og",
    "the",
    "with",
}


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
    *,
    lang: Language = "no",
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
        predicates = [
            Meal.name.ilike(pattern, escape="\\"),
            Meal.description.ilike(pattern, escape="\\"),
            Meal.name_en.ilike(pattern, escape="\\"),
            Meal.description_en.ilike(pattern, escape="\\"),
            Meal.ingredients.any(Ingredient.name.ilike(pattern, escape="\\")),
            Meal.ingredients.any(Ingredient.name_en.ilike(pattern, escape="\\")),
        ]
        for term in _search_terms(active_filters.query):
            term_pattern = f"%{_escape_like(term)}%"
            predicates.extend(
                [
                    Meal.name.ilike(term_pattern, escape="\\"),
                    Meal.description.ilike(term_pattern, escape="\\"),
                    Meal.name_en.ilike(term_pattern, escape="\\"),
                    Meal.description_en.ilike(term_pattern, escape="\\"),
                    Meal.ingredients.any(Ingredient.name.ilike(term_pattern, escape="\\")),
                    Meal.ingredients.any(Ingredient.name_en.ilike(term_pattern, escape="\\")),
                ]
            )
        statement = statement.where(or_(*predicates))
    if active_filters.min_protein_grams is not None:
        statement = statement.where(Meal.protein_grams >= active_filters.min_protein_grams)
    if active_filters.max_calories is not None:
        statement = statement.where(Meal.calories <= active_filters.max_calories)
    if active_filters.max_price_nok is not None:
        statement = statement.where(Meal.price_nok <= active_filters.max_price_nok)
    if active_filters.limit is not None:
        statement = statement.limit(active_filters.limit)

    matched_meals = list(session.scalars(statement).unique().all())
    if active_filters.query:
        phrase = active_filters.query.casefold()
        exact_matches = [
            meal
            for meal in matched_meals
            if any(
                phrase in value.casefold()
                for value in (
                    meal.name,
                    meal.name_en or "",
                    meal.description,
                    meal.description_en or "",
                )
            )
        ]
        if exact_matches:
            matched_meals = exact_matches
    responses = [meal_response(meal, lang=lang) for meal in matched_meals]
    return sorted(responses, key=lambda meal: meal.name)


def get_meal_details(
    session: Session, meal_id: UUID, *, lang: Language = "no"
) -> MealDetailResponse:
    """Load one meal and preserve its current availability state."""
    meal = session.scalar(
        select(Meal)
        .where(Meal.id == meal_id)
        .options(selectinload(Meal.ingredients), selectinload(Meal.allergens))
    )
    if meal is None:
        raise ApplicationNotFoundError("Meal not found")
    return MealDetailResponse(
        **meal_response(meal, lang=lang).model_dump(), available=meal.available
    )


def meal_response(meal: Meal, *, lang: Language = "no") -> MealResponse:
    return MealResponse(
        id=meal.id,
        name=localized(meal.name, meal.name_en, lang),
        description=localized(meal.description, meal.description_en, lang),
        image_url=meal.image_url,
        price_nok=meal.price_nok,
        calories=meal.calories,
        protein_grams=meal.protein_grams,
        carbohydrate_grams=meal.carbohydrate_grams,
        fat_grams=meal.fat_grams,
        ingredients=[localized(item.name, item.name_en, lang) for item in meal.ingredients],
        allergens=[
            AllergenResponse(
                code=allergen.code, name=localized(allergen.name, allergen.name_en, lang)
            )
            for allergen in sorted(meal.allergens, key=lambda item: item.name)
        ],
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_terms(value: str) -> list[str]:
    return [
        term
        for raw_term in _SEARCH_TERM.findall(value)
        if len(term := raw_term.casefold()) >= 3 and term not in _SEARCH_STOP_WORDS
    ]
