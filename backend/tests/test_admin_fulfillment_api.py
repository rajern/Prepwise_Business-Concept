from collections.abc import Iterator
from typing import cast

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
from prepwise_api.models import Base, Meal, PickupLocation, User, UserRole
from prepwise_api.seed import seed_database


class StubAccessTokenValidator:
    def validate(self, token: str) -> AccessTokenClaims:
        if token != "valid-token":
            raise InvalidAccessTokenError
        return AccessTokenClaims(
            tenant_id="1a782388-bf90-4ea8-af8f-bcc755f5cd7e",
            object_id="d074c8a4-4494-4597-9d33-2df93b5f9959",
            subject="pairwise-subject",
            email="admin@example.com",
            display_name="Prepwise Admin",
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


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid-token"}


def _provision_user(client: TestClient) -> None:
    assert client.get("/api/me", headers=_headers()).status_code == 200


def _promote_admin(engine: Engine) -> None:
    with Session(engine) as session, session.begin():
        user = session.scalar(select(User))
        assert user is not None
        user.role = UserRole.ADMIN


def _first_meal_and_location(engine: Engine) -> tuple[Meal, PickupLocation]:
    with Session(engine) as session:
        meal = session.scalar(select(Meal).order_by(Meal.name))
        location = session.scalar(select(PickupLocation).order_by(PickupLocation.name))
        assert meal is not None
        assert location is not None
        session.expunge(meal)
        session.expunge(location)
        return meal, location


def _create_customer_order(client: TestClient, engine: Engine) -> dict[str, object]:
    meal, location = _first_meal_and_location(engine)
    cart_response = client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 1},
    )
    assert cart_response.status_code == 201
    order_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": str(location.id)},
    )
    assert order_response.status_code == 201
    return cast(dict[str, object], order_response.json())


def test_admin_can_create_edit_and_deactivate_pickup_locations(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _provision_user(client)
    assert client.get("/api/admin/pickup-locations", headers=_headers()).status_code == 403
    _promote_admin(engine)

    payload = {
        "name": "Admin test pickup",
        "address_line": "Testgata 1",
        "postal_code": "0150",
        "city": "Oslo",
        "active": True,
    }
    create_response = client.post(
        "/api/admin/pickup-locations",
        headers=_headers(),
        json=payload,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["active"] is True
    assert created["id"] in {
        location["id"] for location in client.get("/api/pickup-locations").json()
    }

    update_response = client.patch(
        f"/api/admin/pickup-locations/{created['id']}",
        headers=_headers(),
        json={**payload, "address_line": "Ny testgate 2", "active": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["address_line"] == "Ny testgate 2"
    assert update_response.json()["active"] is False
    assert created["id"] not in {
        location["id"] for location in client.get("/api/pickup-locations").json()
    }

    meal, _ = _first_meal_and_location(engine)
    client.post(
        "/api/cart/items",
        headers=_headers(),
        json={"meal_id": str(meal.id), "quantity": 1},
    )
    checkout_response = client.post(
        "/api/orders",
        headers=_headers(),
        json={"pickup_location_id": created["id"]},
    )
    assert checkout_response.status_code == 409
    assert checkout_response.json() == {"detail": "Pickup location is unavailable"}


def test_pickup_location_admin_validates_input_and_duplicate_names(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _provision_user(client)
    _promote_admin(engine)
    payload = {
        "name": "Validated pickup",
        "address_line": "Testgata 3",
        "postal_code": "0151",
        "city": "Oslo",
        "active": True,
    }
    assert (
        client.post("/api/admin/pickup-locations", headers=_headers(), json=payload).status_code
        == 201
    )
    duplicate = client.post("/api/admin/pickup-locations", headers=_headers(), json=payload)
    assert duplicate.status_code == 409
    invalid = client.post(
        "/api/admin/pickup-locations",
        headers=_headers(),
        json={**payload, "name": "Invalid postcode", "postal_code": "ABC"},
    )
    assert invalid.status_code == 422


def test_admin_can_inspect_orders_and_only_advance_valid_statuses(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _provision_user(client)
    created = _create_customer_order(client, engine)
    order_id = created["id"]
    assert client.get("/api/admin/orders", headers=_headers()).status_code == 403
    _promote_admin(engine)

    list_response = client.get("/api/admin/orders", headers=_headers())
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == order_id
    assert list_response.json()[0]["customer_email"] == "admin@example.com"

    detail_response = client.get(f"/api/admin/orders/{order_id}", headers=_headers())
    assert detail_response.status_code == 200
    assert detail_response.json()["items"] == created["items"]

    preparing_response = client.patch(
        f"/api/admin/orders/{order_id}/status",
        headers=_headers(),
        json={"status": "preparing"},
    )
    assert preparing_response.status_code == 200
    assert preparing_response.json()["status"] == "preparing"
    assert client.get(f"/api/orders/{order_id}", headers=_headers()).json()["status"] == "preparing"

    invalid_response = client.patch(
        f"/api/admin/orders/{order_id}/status",
        headers=_headers(),
        json={"status": "completed"},
    )
    assert invalid_response.status_code == 409
    assert "expected ready_for_pickup" in invalid_response.json()["detail"]

    for next_status in ("ready_for_pickup", "completed"):
        response = client.patch(
            f"/api/admin/orders/{order_id}/status",
            headers=_headers(),
            json={"status": next_status},
        )
        assert response.status_code == 200
        assert response.json()["status"] == next_status

    completed_again = client.patch(
        f"/api/admin/orders/{order_id}/status",
        headers=_headers(),
        json={"status": "completed"},
    )
    assert completed_again.status_code == 409
