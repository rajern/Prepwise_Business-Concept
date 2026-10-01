from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.models import Base, Meal
from prepwise_api.seed import seed_database
from prepwise_api.services.catalog import MealSearchFilters, search_available_meals


@pytest.fixture
def client_and_engine() -> Iterator[tuple[TestClient, Engine]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_database(engine)

    with Session(engine) as session, session.begin():
        unavailable_meal = session.scalar(select(Meal).where(Meal.name == "Stekt ris med egg"))
        assert unavailable_meal is not None
        unavailable_meal.available = False

    def override_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_meals_reads_available_catalogue_from_database(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine
    response = client.get("/api/meals")

    assert response.status_code == 200
    meals = response.json()
    assert len(meals) == 11
    assert [meal["name"] for meal in meals] == sorted(meal["name"] for meal in meals)
    assert all(meal["name"] != "Stekt ris med egg" for meal in meals)

    teriyaki = next(meal for meal in meals if meal["name"] == "Kylling teriyaki med ris")
    assert teriyaki["price_nok"] == "129.00"
    assert teriyaki["ingredients"] == [
        "Kylling",
        "Jasminris",
        "Brokkoli",
        "Gulrot",
        "Teriyakisaus",
    ]
    assert {allergen["code"] for allergen in teriyaki["allergens"]} == {"gluten", "soy"}


def test_get_meal_returns_full_detail_and_availability(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine
    meals = client.get("/api/meals").json()
    meal_id = meals[0]["id"]

    response = client.get(f"/api/meals/{meal_id}")

    assert response.status_code == 200
    assert response.json()["id"] == meal_id
    assert response.json()["available"] is True
    assert response.json()["ingredients"]


def test_get_meal_exposes_unavailable_state(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    with Session(engine) as session:
        meal_id = session.scalar(select(Meal.id).where(Meal.name == "Stekt ris med egg"))
    assert meal_id is not None

    response = client.get(f"/api/meals/{meal_id}")

    assert response.status_code == 200
    assert response.json()["available"] is False


def test_get_meal_returns_safe_not_found_response(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine

    response = client.get("/api/meals/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "Meal not found"
    assert response.json()["code"] == "not_found"


def test_catalog_search_matches_distinctive_terms_in_a_translated_meal_name(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    _, engine = client_and_engine
    with Session(engine) as session:
        meals = search_available_meals(
            session,
            MealSearchFilters(query="Tofu satay with rice noodles"),
        )

    assert [meal.name for meal in meals] == ["Tofu satay med risnudler"]


def test_broad_meat_word_preserves_ingredient_only_matches(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    _, engine = client_and_engine
    with Session(engine) as session:
        meals = search_available_meals(session, MealSearchFilters(query="kjøtt"))
    assert {meal.name for meal in meals} == {
        "Kalkunkjøttboller med couscous",
        "Biff stroganoff med potetmos",
    }


def test_diet_category_returns_all_declared_meat_and_vegetarian_recipes(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    _, engine = client_and_engine
    with Session(engine) as session:
        meat = search_available_meals(session, MealSearchFilters(diet_category="meat"))
        vegetarian = search_available_meals(
            session,
            MealSearchFilters(diet_category="vegetarian"),
        )
    assert len(meat) == 6
    assert {meal.name for meal in vegetarian} == {
        "Tofu satay med risnudler",
        "Linsegryte med søtpotet",
        "Falafelbowl med bulgur",
    }
    assert all(meal.diet_category == "meat" for meal in meat)


def test_recipe_edit_invalidates_diet_category_instead_of_guessing(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    with Session(engine) as session:
        meal = session.scalar(select(Meal).where(Meal.name == "Tofu satay med risnudler"))
        assert meal is not None
        meal.ingredients.pop()
        session.commit()
        meal_id = meal.id
    assert client.get(f"/api/meals/{meal_id}").json()["diet_category"] is None


def test_english_catalogue_localizes_names_ingredients_and_allergens(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine
    meals = client.get("/api/meals?lang=en").json()
    teriyaki = next(meal for meal in meals if meal["name"] == "Chicken teriyaki with rice")
    assert teriyaki["ingredients"] == [
        "Chicken",
        "Jasmine rice",
        "Broccoli",
        "Carrot",
        "Teriyaki sauce",
    ]
    assert {item["name"] for item in teriyaki["allergens"]} == {"Gluten", "Soy"}
    detail = client.get(f"/api/meals/{teriyaki['id']}?lang=en").json()
    assert detail["description"].startswith("Tender chicken")
    assert client.get("/api/meals?lang=invalid").status_code == 422
