import json
import logging
from io import StringIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import prepwise_api.main as main_module
from prepwise_api.main import app
from prepwise_api.observability import JsonLogFormatter

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_does_not_require_database() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_checks_database(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def successful_check() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(main_module, "check_database_connection", successful_check)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert calls == 1


def test_readiness_returns_safe_503_when_database_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_check() -> None:
        raise RuntimeError("database credential must not escape")

    monkeypatch.setattr(main_module, "check_database_connection", failed_check)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
    assert "credential" not in response.text


def test_request_log_and_response_share_safe_correlation_id() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("prepwise.http")
    logger.addHandler(handler)
    try:
        response = client.get(
            "/health/live?secret=query-value",
            headers={
                "X-Request-ID": "test-correlation-123",
                "Authorization": "Bearer secret-token",
            },
        )
    finally:
        logger.removeHandler(handler)

    log = json.loads(stream.getvalue().splitlines()[-1])
    assert response.headers["X-Request-ID"] == "test-correlation-123"
    assert log["event"] == "request.completed"
    assert log["request_id"] == "test-correlation-123"
    assert log["method"] == "GET"
    assert log["path"] == "/health/live"
    assert log["status_code"] == 200
    assert "secret-token" not in stream.getvalue()
    assert "query-value" not in stream.getvalue()


def test_invalid_correlation_id_is_replaced() -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "bad value"})

    assert response.headers["X-Request-ID"] != "bad value"
    UUID(response.headers["X-Request-ID"])


def test_exception_log_keeps_type_and_stack_without_runtime_message() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("prepwise.test")
    logger.addHandler(handler)
    try:
        try:
            raise RuntimeError("runtime-secret-value")
        except RuntimeError:
            logger.exception("Safe exception summary", extra={"event": "test.exception"})
    finally:
        logger.removeHandler(handler)

    log = json.loads(stream.getvalue().splitlines()[-1])
    assert log["exception"]["type"] == "RuntimeError"
    assert log["exception"]["stack"]
    assert "runtime-secret-value" not in stream.getvalue()
