from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
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
from prepwise_api.models import Base, CartItem, Meal, Order, OrderItem, PickupLocation
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


def _headers(token: str = "valid-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _first_meal_and_location(engine: Engine) -> tuple[Meal, PickupLocation]:
    with Session(engine) as session:
        meal = session.scalar(select(Meal).order_by(Meal.name))
        location = session.scalar(select(PickupLocation).order_by(PickupLocation.name))
        assert meal is not None
        assert location is not None
        session.expunge(meal)
        session.expunge(location)
        return meal, location


def test_checkout_creates_historical_order_and_clears_cart_atomically(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    add_response = client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 2},
    )
    assert add_response.status_code == 201

    checkout_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id)},
    )

    assert checkout_response.status_code == 201
    order = checkout_response.json()
    assert order["status"] == "received"
    assert order["total_nok"] == str(meal.price_nok * 2)
    assert order["pickup_location_name"] == location.name
    assert order["items"] == [
        {
            "meal_id": str(meal.id),
            "meal_name": meal.name,
            "quantity": 2,
            "unit_price_nok": str(meal.price_nok),
            "line_total_nok": str(meal.price_nok * 2),
        }
    ]
    assert client.get("/api/cart", headers=_headers()).json()["items"] == []

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 1
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 1
        assert session.scalar(select(func.count()).select_from(CartItem)) == 0
        persisted_meal = session.get(Meal, meal.id)
        assert persisted_meal is not None
        persisted_meal.price_nok = Decimal("999.00")
        session.commit()

    detail_response = client.get(f"/api/orders/{order['id']}", headers=_headers())
    assert detail_response.status_code == 200
    assert detail_response.json()["items"][0]["unit_price_nok"] == str(meal.price_nok)


def test_order_history_is_scoped_to_the_authenticated_user(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 1},
    )
    created = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id)},
    ).json()

    history_response = client.get("/api/orders", headers=_headers())
    assert history_response.status_code == 200
    assert [order["id"] for order in history_response.json()] == [created["id"]]

    assert client.get("/api/orders", headers=_headers("other-token")).json() == []
    other_detail_response = client.get(
        f"/api/orders/{created['id']}",
        headers=_headers("other-token"),
    )
    assert other_detail_response.status_code == 404


@pytest.mark.parametrize("failure", ["inactive-location", "unavailable-meal"])
def test_failed_checkout_preserves_cart_and_creates_no_partial_order(
    client_and_engine: tuple[TestClient, Engine],
    failure: str,
) -> None:
    client, engine = client_and_engine
    meal, location = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 1},
    )

    with Session(engine) as session:
        if failure == "inactive-location":
            persisted_location = session.get(PickupLocation, location.id)
            assert persisted_location is not None
            persisted_location.active = False
        else:
            persisted_meal = session.get(Meal, meal.id)
            assert persisted_meal is not None
            persisted_meal.available = False
        session.commit()

    response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id)},
    )

    assert response.status_code == 409
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
        assert session.scalar(select(func.count()).select_from(OrderItem)) == 0
        assert session.scalar(select(func.count()).select_from(CartItem)) == 1


def test_checkout_rejects_empty_cart_and_frontend_supplied_price(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _, location = _first_meal_and_location(engine)

    empty_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id)},
    )
    assert empty_response.status_code == 409

    untrusted_price_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id), "total_nok": "1.00"},
    )
    assert untrusted_price_response.status_code == 422
