from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.database import get_session
from prepwise_api.models import Meal
from prepwise_api.schemas import AllergenResponse, MealDetailResponse, MealResponse

router = APIRouter(prefix="/api/meals", tags=["meals"])


@router.get("", response_model=list[MealResponse])
def list_available_meals(
    session: Annotated[Session, Depends(get_session)],
) -> list[MealResponse]:
    """Return the public meal catalogue from PostgreSQL."""
    statement = (
        select(Meal)
        .where(Meal.available.is_(True))
        .options(selectinload(Meal.ingredients), selectinload(Meal.allergens))
        .order_by(Meal.name)
    )
    meals = session.scalars(statement).all()

    return [_meal_response(meal) for meal in meals]


@router.get("/{meal_id}", response_model=MealDetailResponse)
def get_meal(
    meal_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> MealDetailResponse:
    """Return one meal, including a clear current availability state."""
    statement = (
        select(Meal)
        .where(Meal.id == meal_id)
        .options(selectinload(Meal.ingredients), selectinload(Meal.allergens))
    )
    meal = session.scalar(statement)
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")

    return MealDetailResponse(
        **_meal_response(meal).model_dump(),
        available=meal.available,
    )


def _meal_response(meal: Meal) -> MealResponse:
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
