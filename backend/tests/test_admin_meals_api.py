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
from prepwise_api.models import Base, User, UserRole
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


def _promote_admin(client: TestClient, engine: Engine) -> None:
    assert client.get("/api/me", headers=_headers()).status_code == 200
    with Session(engine) as session, session.begin():
        user = session.scalar(select(User))
        assert user is not None
        user.role = UserRole.ADMIN


def _meal_payload() -> dict[str, object]:
    return {
        "name": "Admin test bowl",
        "description": "A meal created through the protected admin API.",
        "image_url": "https://example.com/meal.jpg",
        "price_nok": "137.50",
        "calories": 610,
        "protein_grams": "42.00",
        "carbohydrate_grams": "63.00",
        "fat_grams": "19.00",
        "ingredients": ["Kylling", "Admin test ingredient"],
        "allergen_codes": ["milk"],
        "available": True,
    }


def test_customer_cannot_use_meal_administration(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, _ = client_and_engine

    list_response = client.get("/api/admin/meals", headers=_headers())
    create_response = client.post(
        "/api/admin/meals",
        headers=_headers(),
        json=_meal_payload(),
    )

    assert list_response.status_code == 403
    assert create_response.status_code == 403


def test_admin_can_create_edit_and_change_meal_availability(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _promote_admin(client, engine)

    allergens_response = client.get("/api/admin/meals/allergens", headers=_headers())
    assert allergens_response.status_code == 200
    assert {item["code"] for item in allergens_response.json()} >= {"milk", "gluten"}

    create_response = client.post(
        "/api/admin/meals",
        headers=_headers(),
        json=_meal_payload(),
    )
    assert create_response.status_code == 201, create_response.json()
    created = create_response.json()
    assert created["name"] == "Admin test bowl"
    assert created["ingredients"] == ["Kylling", "Admin test ingredient"]
    assert created["allergens"] == [{"code": "milk", "name": "Melk"}]
    assert created["available"] is True
    assert "Admin test bowl" in {meal["name"] for meal in client.get("/api/meals").json()}

    updated_payload = {**_meal_payload(), "price_nok": "145.00", "available": False}
    update_response = client.patch(
        f"/api/admin/meals/{created['id']}",
        headers=_headers(),
        json=updated_payload,
    )
    assert update_response.status_code == 200
    assert update_response.json()["price_nok"] == "145.00"
    assert update_response.json()["available"] is False
    assert "Admin test bowl" not in {meal["name"] for meal in client.get("/api/meals").json()}

    admin_meals = client.get("/api/admin/meals", headers=_headers()).json()
    saved = next(meal for meal in admin_meals if meal["id"] == created["id"])
    assert saved["available"] is False


def test_admin_meal_inputs_are_validated_and_conflicts_are_safe(
    client_and_engine: tuple[TestClient, Engine],
) -> None:
    client, engine = client_and_engine
    _promote_admin(client, engine)
    assert (
        client.post("/api/admin/meals", headers=_headers(), json=_meal_payload()).status_code == 201
    )

    duplicate_response = client.post(
        "/api/admin/meals",
        headers=_headers(),
        json=_meal_payload(),
    )
    assert duplicate_response.status_code == 409

    negative_payload = {**_meal_payload(), "name": "Invalid price", "price_nok": "-1.00"}
    assert (
        client.post(
            "/api/admin/meals",
            headers=_headers(),
            json=negative_payload,
        ).status_code
        == 422
    )

    unknown_allergen_payload = {
        **_meal_payload(),
        "name": "Invalid allergen",
        "allergen_codes": ["unknown"],
    }
    unknown_response = client.post(
        "/api/admin/meals",
        headers=_headers(),
        json=unknown_allergen_payload,
    )
    assert unknown_response.status_code == 422
    assert unknown_response.json()["detail"] == "Unknown allergen codes: unknown"
    assert unknown_response.json()["code"] == "validation_error"
