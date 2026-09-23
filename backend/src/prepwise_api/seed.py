from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from prepwise_api.database import get_engine
from prepwise_api.models import (
    Allergen,
    Ingredient,
    Meal,
    PickupLocation,
    meal_allergens,
    meal_ingredients,
)
from prepwise_api.seed_data import ALLERGENS, INGREDIENT_NAMES, MEALS, PICKUP_LOCATIONS


@dataclass(frozen=True, slots=True)
class SeedSummary:
    meals: int
    ingredients: int
    allergens: int
    pickup_locations: int


def _sync_ingredients(session: Session) -> dict[str, Ingredient]:
    ingredients = {
        ingredient.name: ingredient
        for ingredient in session.scalars(
            select(Ingredient).where(Ingredient.name.in_(INGREDIENT_NAMES))
        )
    }

    for name in INGREDIENT_NAMES:
        if name not in ingredients:
            ingredient = Ingredient(name=name)
            session.add(ingredient)
            ingredients[name] = ingredient

    session.flush()
    return ingredients


def _sync_allergens(session: Session) -> dict[str, Allergen]:
    seed_codes = tuple(allergen.code for allergen in ALLERGENS)
    allergens = {
        allergen.code: allergen
        for allergen in session.scalars(select(Allergen).where(Allergen.code.in_(seed_codes)))
    }

    for seed in ALLERGENS:
        allergen = allergens.get(seed.code)
        if allergen is None:
            allergen = Allergen(code=seed.code, name=seed.name)
            session.add(allergen)
            allergens[seed.code] = allergen
        else:
            allergen.name = seed.name

    session.flush()
    return allergens


def _sync_pickup_locations(session: Session) -> None:
    seed_names = tuple(location.name for location in PICKUP_LOCATIONS)
    locations = {
        location.name: location
        for location in session.scalars(
            select(PickupLocation).where(PickupLocation.name.in_(seed_names))
        )
    }

    for seed in PICKUP_LOCATIONS:
        location = locations.get(seed.name)
        if location is None:
            location = PickupLocation(name=seed.name)
            session.add(location)

        location.address_line = seed.address_line
        location.postal_code = seed.postal_code
        location.city = seed.city
        location.active = True


def _sync_meals(
    session: Session,
    ingredients: dict[str, Ingredient],
    allergens: dict[str, Allergen],
) -> None:
    seed_names = tuple(meal.name for meal in MEALS)
    meals = {
        meal.name: meal for meal in session.scalars(select(Meal).where(Meal.name.in_(seed_names)))
    }

    for seed in MEALS:
        meal = meals.get(seed.name)
        if meal is None:
            meal = Meal(name=seed.name)
            session.add(meal)
            meals[seed.name] = meal

        meal.description = seed.description
        meal.image_url = seed.image_url
        meal.price_nok = seed.price_nok
        meal.calories = seed.calories
        meal.protein_grams = seed.protein_grams
        meal.carbohydrate_grams = seed.carbohydrate_grams
        meal.fat_grams = seed.fat_grams
        meal.available = True

    session.flush()

    for seed in MEALS:
        meal = meals[seed.name]
        session.execute(delete(meal_ingredients).where(meal_ingredients.c.meal_id == meal.id))
        ingredient_rows: list[dict[str, object]] = [
            {
                "meal_id": meal.id,
                "ingredient_id": ingredients[name].id,
                "position": position,
            }
            for position, name in enumerate(seed.ingredients)
        ]
        session.execute(insert(meal_ingredients), ingredient_rows)

        session.execute(delete(meal_allergens).where(meal_allergens.c.meal_id == meal.id))
        allergen_rows: list[dict[str, object]] = [
            {"meal_id": meal.id, "allergen_id": allergens[code].id} for code in seed.allergen_codes
        ]
        if allergen_rows:
            session.execute(insert(meal_allergens), allergen_rows)


def seed_database(engine: Engine) -> SeedSummary:
    """Synchronise the canonical development catalogue in one transaction."""
    with Session(engine) as session, session.begin():
        ingredients = _sync_ingredients(session)
        allergens = _sync_allergens(session)
        _sync_pickup_locations(session)
        _sync_meals(session, ingredients, allergens)

    return SeedSummary(
        meals=len(MEALS),
        ingredients=len(INGREDIENT_NAMES),
        allergens=len(ALLERGENS),
        pickup_locations=len(PICKUP_LOCATIONS),
    )


def seed_database_if_empty(engine: Engine) -> SeedSummary | None:
    """Seed an empty database once without overwriting an existing production catalogue."""
    with Session(engine) as session:
        if session.scalar(select(Meal.id).limit(1)) is not None:
            return None

    return seed_database(engine)


def main() -> None:
    summary = seed_database(get_engine())
    print(
        "Seeded "
        f"{summary.meals} meals, "
        f"{summary.ingredients} ingredients, "
        f"{summary.allergens} allergens and "
        f"{summary.pickup_locations} pickup locations."
    )


def main_if_empty() -> None:
    summary = seed_database_if_empty(get_engine())
    if summary is None:
        print("Skipped demo catalogue seed because meals already exist.")
        return

    print(
        "Seeded initial demo catalogue with "
        f"{summary.meals} meals, "
        f"{summary.ingredients} ingredients, "
        f"{summary.allergens} allergens and "
        f"{summary.pickup_locations} pickup locations."
    )


if __name__ == "__main__":
    main()
