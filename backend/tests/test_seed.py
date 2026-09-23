from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from prepwise_api.models import (
    Allergen,
    Base,
    Ingredient,
    Meal,
    PickupLocation,
    meal_allergens,
    meal_ingredients,
)
from prepwise_api.seed import SeedSummary, seed_database, seed_database_if_empty
from prepwise_api.seed_data import ALLERGENS, INGREDIENT_NAMES, MEALS, PICKUP_LOCATIONS


def test_seed_database_is_repeatable() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    expected = SeedSummary(
        meals=len(MEALS),
        ingredients=len(INGREDIENT_NAMES),
        allergens=len(ALLERGENS),
        pickup_locations=len(PICKUP_LOCATIONS),
    )
    assert seed_database(engine) == expected
    assert seed_database(engine) == expected

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Meal)) == len(MEALS)
        assert session.scalar(select(func.count()).select_from(Ingredient)) == len(INGREDIENT_NAMES)
        assert session.scalar(select(func.count()).select_from(Allergen)) == len(ALLERGENS)
        assert session.scalar(select(func.count()).select_from(PickupLocation)) == len(
            PICKUP_LOCATIONS
        )
        assert session.scalar(select(func.count()).select_from(meal_ingredients)) == sum(
            len(meal.ingredients) for meal in MEALS
        )
        assert session.scalar(select(func.count()).select_from(meal_allergens)) == sum(
            len(meal.allergen_codes) for meal in MEALS
        )

    engine.dispose()


def test_seed_preserves_ingredient_order() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    seed_database(engine)

    with Session(engine) as session:
        meal_id = session.scalar(select(Meal.id).where(Meal.name == MEALS[0].name))
        positions = session.scalars(
            select(meal_ingredients.c.position)
            .where(meal_ingredients.c.meal_id == meal_id)
            .order_by(meal_ingredients.c.position)
        ).all()

    assert positions == list(range(len(MEALS[0].ingredients)))
    engine.dispose()


def test_seed_if_empty_does_not_replace_an_existing_catalogue() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    summary = seed_database_if_empty(engine)
    assert summary is not None

    with Session(engine) as session, session.begin():
        first_meal = session.scalar(select(Meal).order_by(Meal.name).limit(1))
        assert first_meal is not None
        first_meal.available = False
        first_meal_id = first_meal.id

    assert seed_database_if_empty(engine) is None

    with Session(engine) as session:
        preserved_meal = session.get(Meal, first_meal_id)
        assert preserved_meal is not None
        assert preserved_meal.available is False

    engine.dispose()
