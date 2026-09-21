from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from prepwise_api.database import get_session
from prepwise_api.models import Meal
from prepwise_api.schemas import AllergenResponse, MealResponse

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

    return [
        MealResponse(
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
        for meal in meals
    ]
