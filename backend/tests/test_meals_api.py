from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.models import Base, Meal
from prepwise_api.seed import seed_database


@pytest.fixture
def client() -> Iterator[TestClient]:
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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_meals_reads_available_catalogue_from_database(client: TestClient) -> None:
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
