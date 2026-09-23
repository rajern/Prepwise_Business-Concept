from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.auth import (
    AccessTokenClaims,
    InvalidAccessTokenError,
    get_access_token_validator,
)
from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.models import Base, User


class StubAccessTokenValidator:
    def validate(self, token: str) -> AccessTokenClaims:
        if token != "valid-token":
            raise InvalidAccessTokenError

        return AccessTokenClaims(
            tenant_id="1a782388-bf90-4ea8-af8f-bcc755f5cd7e",
            object_id="d074c8a4-4494-4597-9d33-2df93b5f9959",
            subject="pairwise-subject",
            email="customer@example.com",
            display_name="Prepwise Customer",
        )


@pytest.fixture
def client_and_engine() -> Iterator[tuple[TestClient, object]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

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


def test_protected_endpoint_rejects_missing_token(
    client_and_engine: tuple[TestClient, object],
) -> None:
    client, _ = client_and_engine

    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_protected_endpoint_rejects_invalid_token(
    client_and_engine: tuple[TestClient, object],
) -> None:
    client, _ = client_and_engine

    response = client.get("/api/me", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_authenticated_request_creates_and_reuses_local_customer(
    client_and_engine: tuple[TestClient, object],
) -> None:
    client, engine = client_and_engine
    headers = {"Authorization": "Bearer valid-token"}

    first_response = client.get("/api/me", headers=headers)
    second_response = client.get("/api/me", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    assert first_response.json() == {
        "id": first_response.json()["id"],
        "email": "customer@example.com",
        "display_name": "Prepwise Customer",
        "role": "customer",
    }

    with Session(engine) as session:  # type: ignore[arg-type]
        assert session.scalar(select(func.count()).select_from(User)) == 1
        user = session.scalar(select(User))
        assert user is not None
        assert user.external_subject.endswith(":d074c8a4-4494-4597-9d33-2df93b5f9959")
