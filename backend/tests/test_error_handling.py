from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from prepwise_api.auth import (
    AccessTokenClaims,
    SigningKeysUnavailableError,
    get_access_token_validator,
)
from prepwise_api.database import get_session
from prepwise_api.errors import install_exception_handlers
from prepwise_api.main import app


class UnavailableAccessTokenValidator:
    def validate(self, token: str) -> AccessTokenClaims:
        del token
        raise SigningKeysUnavailableError


def test_validation_errors_are_structured_without_echoing_input() -> None:
    response = TestClient(app).get(
        "/api/meals/not-a-secret-uuid",
        headers={"X-Request-ID": "validation-test"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["detail"] == "Invalid request data"
    assert body["request_id"] == "validation-test"
    assert body["errors"][0]["location"] == "path.meal_id"
    assert body["errors"][0]["type"] == "uuid_parsing"
    assert "not-a-secret-uuid" not in response.text
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_external_authentication_failure_returns_safe_service_error() -> None:
    app.dependency_overrides[get_access_token_validator] = UnavailableAccessTokenValidator
    try:
        response = TestClient(app).get(
            "/api/me",
            headers={"Authorization": "Bearer opaque-secret-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"
    assert response.json()["detail"] == "Authentication service is temporarily unavailable"
    assert "opaque-secret-token" not in response.text


def test_database_failures_return_safe_service_error() -> None:
    def failed_session() -> Iterator[Session]:
        raise OperationalError("SELECT secret", {}, RuntimeError("database-secret"))
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = failed_session
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/api/meals")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"
    assert response.json()["detail"] == "The service is temporarily unavailable"
    assert "database-secret" not in response.text
    assert "SELECT secret" not in response.text


def test_unhandled_failures_do_not_expose_exception_details() -> None:
    isolated_app = FastAPI()
    install_exception_handlers(isolated_app)

    @isolated_app.get("/failure")
    def fail() -> None:
        raise RuntimeError("internal-secret")

    response = TestClient(isolated_app, raise_server_exceptions=False).get("/failure")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert response.json()["detail"] == "An unexpected error occurred"
    assert "internal-secret" not in response.text
