from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.assistant import (
    AssistantConfigurationError,
    AssistantReply,
    AssistantTimeoutError,
    AssistantUnavailableError,
    get_assistant_service,
)
from prepwise_api.auth import (
    AccessTokenClaims,
    InvalidAccessTokenError,
    get_access_token_validator,
)
from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.models import Base


class StubAccessTokenValidator:
    def validate(self, token: str) -> AccessTokenClaims:
        if token != "valid-token":
            raise InvalidAccessTokenError
        return AccessTokenClaims(
            tenant_id="1a782388-bf90-4ea8-af8f-bcc755f5cd7e",
            object_id="assistant-customer",
            subject="assistant-customer",
            email="assistant@example.com",
            display_name="Assistant Customer",
        )


@dataclass
class StubAssistantService:
    error: Exception | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)

    async def respond(self, *, message: str, request_id: str) -> AssistantReply:
        self.calls.append((message, request_id))
        if self.error is not None:
            raise self.error
        return AssistantReply(
            text="Hello from Prepwise.",
            model="gpt-5.6-terra",
            response_id="resp_test",
        )


@pytest.fixture
def client_and_assistant() -> Iterator[tuple[TestClient, StubAssistantService]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    assistant = StubAssistantService()

    def override_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_access_token_validator] = StubAccessTokenValidator
    app.dependency_overrides[get_assistant_service] = lambda: assistant
    try:
        with TestClient(app) as client:
            yield client, assistant
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_assistant_rejects_unauthenticated_messages(
    client_and_assistant: tuple[TestClient, StubAssistantService],
) -> None:
    client, assistant = client_and_assistant

    response = client.post("/api/assistant/messages", json={"message": "Hello"})

    assert response.status_code == 401
    assert assistant.calls == []


def test_authenticated_customer_can_send_message(
    client_and_assistant: tuple[TestClient, StubAssistantService],
) -> None:
    client, assistant = client_and_assistant

    response = client.post(
        "/api/assistant/messages",
        json={"message": "  Hello  "},
        headers={
            "Authorization": "Bearer valid-token",
            "X-Request-ID": "assistant-request-123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Hello from Prepwise.",
        "model": "gpt-5.6-terra",
        "response_id": "resp_test",
    }
    assert assistant.calls == [("Hello", "assistant-request-123")]


def test_assistant_rejects_blank_message_before_model_call(
    client_and_assistant: tuple[TestClient, StubAssistantService],
) -> None:
    client, assistant = client_and_assistant

    response = client.post(
        "/api/assistant/messages",
        json={"message": "   "},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 422
    assert assistant.calls == []


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code", "expected_detail"),
    [
        (
            AssistantConfigurationError(),
            503,
            "service_unavailable",
            "The AI assistant is not configured",
        ),
        (
            AssistantTimeoutError(),
            504,
            "gateway_timeout",
            "The AI assistant timed out. Please try again.",
        ),
        (
            AssistantUnavailableError(),
            503,
            "service_unavailable",
            "The AI assistant is temporarily unavailable",
        ),
    ],
)
def test_assistant_failures_are_safe_and_explicit(
    client_and_assistant: tuple[TestClient, StubAssistantService],
    error: Exception,
    expected_status: int,
    expected_code: str,
    expected_detail: str,
) -> None:
    client, assistant = client_and_assistant
    assistant.error = error

    response = client.post(
        "/api/assistant/messages",
        json={"message": "Do not echo this customer content"},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == expected_status
    assert response.json()["code"] == expected_code
    assert response.json()["detail"] == expected_detail
    assert "customer content" not in response.text
