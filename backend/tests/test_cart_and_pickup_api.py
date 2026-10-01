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
        "groups": [],
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


def test_groups_persist_pickup_and_isolate_duplicate_meals(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine
    headers = {"Authorization": "Bearer valid-token"}
    meal = client.get("/api/meals").json()[0]
    location = client.get("/api/pickup-locations").json()[0]
    days = client.get("/api/pickup-locations/options").json()["days"]
    group_ids = []
    for day in days[:2]:
        created = client.post(
            "/api/cart/groups",
            headers=headers,
            json={
                "pickup_location_id": location["id"],
                "pickup_date": day["date"],
                "pickup_slot": "16-18",
            },
        )
        assert created.status_code == 201
        group_id = next(
            group["id"] for group in created.json()["groups"] if group["id"] not in group_ids
        )
        group_ids.append(group_id)
        added = client.post(
            "/api/cart/items",
            headers=headers,
            json={"meal_id": meal["id"], "quantity": 2, "group_id": group_id},
        )
        assert added.status_code == 201
    cart = client.get("/api/cart", headers=headers).json()
    assert cart["total_quantity"] == 4
    assert len(cart["items"]) == 2
    assert {item["group_id"] for item in cart["items"]} == set(group_ids)
    assert {group["pickup_date"] for group in cart["groups"]} == {day["date"] for day in days[:2]}
    assert client.delete(f"/api/cart/groups/{group_ids[0]}", headers=headers).status_code == 409
    item = next(item for item in cart["items"] if item["group_id"] == group_ids[0])
    moved = client.patch(
        f"/api/cart/items/{item['id']}",
        headers=headers,
        json={"quantity": 2, "group_id": group_ids[1]},
    )
    assert moved.status_code == 200
    assert len(moved.json()["items"]) == 1
    assert moved.json()["items"][0]["quantity"] == 4
    assert client.delete(f"/api/cart/groups/{group_ids[0]}", headers=headers).status_code == 204
    item = moved.json()["items"][0]
    # Omitted group_id retains assignment; explicit null removes assignment.
    retained = client.patch(
        f"/api/cart/items/{item['id']}", headers=headers, json={"quantity": 3}
    ).json()
    assert retained["items"][0]["group_id"] == group_ids[1]
    unassigned = client.patch(
        f"/api/cart/items/{item['id']}", headers=headers, json={"quantity": 3, "group_id": None}
    ).json()
    assert unassigned["items"][0]["group_id"] is None


def test_group_ownership_and_invalid_selection(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine
    headers = {"Authorization": "Bearer valid-token"}
    other = {"Authorization": "Bearer other-token"}
    group_id = client.post("/api/cart/groups", headers=headers, json={}).json()["groups"][0]["id"]
    meal = client.get("/api/meals").json()[0]
    assert client.patch(f"/api/cart/groups/{group_id}", headers=other, json={}).status_code == 404
    assert client.delete(f"/api/cart/groups/{group_id}", headers=other).status_code == 404
    assert (
        client.post(
            "/api/cart/items",
            headers=other,
            json={"meal_id": meal["id"], "quantity": 1, "group_id": group_id},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/cart/groups/{group_id}",
            headers=headers,
            json={"pickup_date": "2020-01-01", "pickup_slot": "16-18"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/cart/groups/{group_id}", headers=headers, json={"pickup_date": "2020-01-01"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/cart/groups/{group_id}",
            headers=headers,
            json={"pickup_location_id": "00000000-0000-0000-0000-000000000000"},
        ).status_code
        == 409
    )


def test_group_move_quantity_overflow_preserves_both_lines(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine
    headers = {"Authorization": "Bearer valid-token"}
    meal = client.get("/api/meals").json()[0]
    group_id = client.post("/api/cart/groups", headers=headers, json={}).json()["groups"][0]["id"]
    client.post(
        "/api/cart/items",
        headers=headers,
        json={"meal_id": meal["id"], "quantity": 99, "group_id": group_id},
    )
    cart = client.post(
        "/api/cart/items", headers=headers, json={"meal_id": meal["id"], "quantity": 1}
    ).json()
    item = next(item for item in cart["items"] if item["group_id"] is None)
    assert (
        client.patch(
            f"/api/cart/items/{item['id']}",
            headers=headers,
            json={"quantity": 1, "group_id": group_id},
        ).status_code
        == 422
    )
    assert client.get("/api/cart", headers=headers).json()["total_quantity"] == 100
