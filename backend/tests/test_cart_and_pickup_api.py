from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.auth import (
    AccessTokenClaims,
    InvalidAccessTokenError,
    get_access_token_validator,
)
from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.models import Base, Meal, PickupLocation
from prepwise_api.seed import seed_database


class StubAccessTokenValidator:
    def validate(self, token: str) -> AccessTokenClaims:
        object_ids = {
            "valid-token": "d074c8a4-4494-4597-9d33-2df93b5f9959",
            "other-token": "52a8cd26-8b95-447b-aa0f-80efeb1aa218",
        }
        object_id = object_ids.get(token)
        if object_id is None:
            raise InvalidAccessTokenError

        return AccessTokenClaims(
            tenant_id="1a782388-bf90-4ea8-af8f-bcc755f5cd7e",
            object_id=object_id,
            subject="pairwise-subject",
            email=f"{object_id}@example.com",
            display_name="Prepwise Customer",
        )


@pytest.fixture
def client_and_engine() -> Iterator[tuple[TestClient, Engine]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_database(engine)

    def override_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_access_token_validator] = StubAccessTokenValidator
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_cart_requires_authentication(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine

    response = client.get("/api/cart")

    assert response.status_code == 401


def test_cart_crud_persists_and_calculates_authoritative_totals(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    headers = {"Authorization": "Bearer valid-token"}
    with Session(engine) as session:
        meal = session.scalar(select(Meal).order_by(Meal.name))
        assert meal is not None
        meal_id = str(meal.id)
        unit_price = meal.price_nok

    add_response = client.post(
        "/api/cart/items",
        headers=headers,
        json={"meal_id": meal_id, "quantity": 2},
    )

    assert add_response.status_code == 201
    cart = add_response.json()
    assert cart["total_quantity"] == 2
    assert cart["total_nok"] == str(unit_price * 2)
    assert cart["items"][0]["meal"]["id"] == meal_id
    item_id = cart["items"][0]["id"]

    persisted_response = client.get("/api/cart", headers=headers)
    assert persisted_response.json() == cart

    update_response = client.patch(
        f"/api/cart/items/{item_id}",
        headers=headers,
        json={"quantity": 3},
    )
    assert update_response.status_code == 200
    assert update_response.json()["total_quantity"] == 3
    assert update_response.json()["total_nok"] == str(unit_price * 3)

    delete_response = client.delete(f"/api/cart/items/{item_id}", headers=headers)
    assert delete_response.status_code == 204
    assert client.get("/api/cart", headers=headers).json() == {
        "items": [],
        "total_quantity": 0,
        "total_nok": "0.00",
    }


def test_cart_rejects_invalid_quantities_unavailable_meals_and_cross_user_access(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    headers = {"Authorization": "Bearer valid-token"}
    other_headers = {"Authorization": "Bearer other-token"}
    with Session(engine) as session:
        meals = session.scalars(select(Meal).order_by(Meal.name).limit(2)).all()
        assert len(meals) == 2
        available_meal_id = str(meals[0].id)
        unavailable_meal_id = str(meals[1].id)
        meals[1].available = False
        session.commit()

    invalid_response = client.post(
        "/api/cart/items",
        headers=headers,
        json={"meal_id": available_meal_id, "quantity": 0},
    )
    assert invalid_response.status_code == 422

    unavailable_response = client.post(
        "/api/cart/items",
        headers=headers,
        json={"meal_id": unavailable_meal_id, "quantity": 1},
    )
    assert unavailable_response.status_code == 409

    added = client.post(
        "/api/cart/items",
        headers=headers,
        json={"meal_id": available_meal_id, "quantity": 1},
    ).json()
    item_id = added["items"][0]["id"]

    assert client.get("/api/cart", headers=other_headers).json()["items"] == []
    cross_user_response = client.patch(
        f"/api/cart/items/{item_id}",
        headers=other_headers,
        json={"quantity": 2},
    )
    assert cross_user_response.status_code == 404


def test_pickup_locations_only_expose_active_database_rows(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    with Session(engine) as session:
        inactive = session.scalar(select(PickupLocation).order_by(PickupLocation.name))
        assert inactive is not None
        inactive.active = False
        inactive_id = inactive.id
        session.commit()

    list_response = client.get("/api/pickup-locations")

    assert list_response.status_code == 200
    locations = list_response.json()
    assert len(locations) == 3
    assert str(inactive_id) not in {location["id"] for location in locations}

    inactive_response = client.get(f"/api/pickup-locations/{inactive_id}")
    assert inactive_response.status_code == 404
    assert inactive_response.json()["detail"] == "Pickup location not found or inactive"
    assert inactive_response.json()["code"] == "not_found"
