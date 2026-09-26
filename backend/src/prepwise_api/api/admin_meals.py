from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from prepwise_api.auth import require_admin
from prepwise_api.database import get_session
from prepwise_api.models import (
    Allergen,
    Ingredient,
    Meal,
    User,
    meal_allergens,
    meal_ingredients,
)
from prepwise_api.schemas import AllergenResponse, MealAdminWrite, MealDetailResponse
from prepwise_api.services.catalog import meal_response

router = APIRouter(prefix="/api/admin/meals", tags=["admin meals"])


@router.get("", response_model=list[MealDetailResponse])
def list_admin_meals(
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[MealDetailResponse]:
    """Return the full catalogue, including unavailable meals, to admins."""
    meals = session.scalars(
        select(Meal)
        .options(selectinload(Meal.ingredients), selectinload(Meal.allergens))
        .order_by(Meal.name)
    ).all()
    return [_admin_meal_response(meal) for meal in meals]


@router.get("/allergens", response_model=list[AllergenResponse])
def list_admin_allergens(
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[AllergenResponse]:
    """Return valid allergen choices for the admin editor."""
    allergens = session.scalars(select(Allergen).order_by(Allergen.name)).all()
    return [AllergenResponse(code=item.code, name=item.name) for item in allergens]


@router.post("", response_model=MealDetailResponse, status_code=status.HTTP_201_CREATED)
def create_admin_meal(
    payload: MealAdminWrite,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> MealDetailResponse:
    """Create a validated meal and its catalogue relationships."""
    meal = Meal(name=payload.name)
    return _save_meal(session, meal, payload)


@router.patch("/{meal_id}", response_model=MealDetailResponse)
def update_admin_meal(
    meal_id: UUID,
    payload: MealAdminWrite,
    _: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> MealDetailResponse:
    """Replace editable meal fields while preserving its stable identifier."""
    meal = session.get(Meal, meal_id)
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    return _save_meal(session, meal, payload)


def _save_meal(
    session: Session,
    meal: Meal,
    payload: MealAdminWrite,
) -> MealDetailResponse:
    try:
        allergens = _resolve_allergens(session, payload.allergen_codes)
        meal.name = payload.name
        meal.description = payload.description
        meal.image_url = str(payload.image_url) if payload.image_url else None
        meal.price_nok = payload.price_nok
        meal.calories = payload.calories
        meal.protein_grams = payload.protein_grams
        meal.carbohydrate_grams = payload.carbohydrate_grams
        meal.fat_grams = payload.fat_grams
        meal.available = payload.available
        session.add(meal)
        ingredients = _resolve_ingredients(session, payload.ingredients)
        session.flush()

        session.execute(delete(meal_ingredients).where(meal_ingredients.c.meal_id == meal.id))
        session.execute(
            insert(meal_ingredients),
            [
                {
                    "meal_id": meal.id,
                    "ingredient_id": ingredient.id,
                    "position": position,
                }
                for position, ingredient in enumerate(ingredients)
            ],
        )
        session.execute(delete(meal_allergens).where(meal_allergens.c.meal_id == meal.id))
        if allergens:
            session.execute(
                insert(meal_allergens),
                [{"meal_id": meal.id, "allergen_id": allergen.id} for allergen in allergens],
            )
        meal_id = meal.id
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A meal or ingredient with that name already exists",
        ) from error

    saved_meal = _load_meal(session, meal_id)
    if saved_meal is None:  # pragma: no cover - defensive after a successful commit
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Saved meal could not be loaded",
        )
    return _admin_meal_response(saved_meal)


def _resolve_allergens(session: Session, codes: list[str]) -> list[Allergen]:
    if not codes:
        return []
    allergens = list(session.scalars(select(Allergen).where(Allergen.code.in_(codes))))
    by_code = {allergen.code: allergen for allergen in allergens}
    missing = [code for code in codes if code not in by_code]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown allergen codes: {', '.join(missing)}",
        )
    return [by_code[code] for code in codes]


def _resolve_ingredients(session: Session, names: list[str]) -> list[Ingredient]:
    existing = {
        ingredient.name.casefold(): ingredient for ingredient in session.scalars(select(Ingredient))
    }
    ingredients: list[Ingredient] = []
    for name in names:
        ingredient = existing.get(name.casefold())
        if ingredient is None:
            ingredient = Ingredient(name=name)
            session.add(ingredient)
            existing[name.casefold()] = ingredient
        ingredients.append(ingredient)
    session.flush()
    return ingredients


def _load_meal(session: Session, meal_id: UUID) -> Meal | None:
    return session.scalar(
        select(Meal)
        .where(Meal.id == meal_id)
        .options(selectinload(Meal.ingredients), selectinload(Meal.allergens))
    )


def _admin_meal_response(meal: Meal) -> MealDetailResponse:
    return MealDetailResponse(
        **meal_response(meal).model_dump(),
        available=meal.available,
    )
