import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import httpx
from openai import APITimeoutError, AsyncOpenAI
from pydantic import SecretStr

from prepwise_api.assistant import AssistantService, AssistantTimeoutError
from prepwise_api.config import Settings


def test_service_calls_responses_api_with_safe_configuration() -> None:
    response = SimpleNamespace(
        id="resp_123",
        model="gpt-5.6-terra",
        output_text="A concise answer.",
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        _request_id="req_123",
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    settings = Settings(
        openai_api_key=SecretStr("test-key"),
        openai_model="gpt-5.6-terra",
        openai_reasoning_effort="low",
    )
    service = AssistantService(settings, cast(AsyncOpenAI, client))

    reply = asyncio.run(service.respond(message="Hello", request_id="request-123"))

    assert reply.text == "A concise answer."
    assert reply.response_id == "resp_123"
    create.assert_awaited_once()
    assert create.await_args is not None
    call = create.await_args.kwargs
    assert call["model"] == "gpt-5.6-terra"
    assert call["reasoning"] == {"effort": "low"}
    assert call["input"] == "Hello"
    assert call["store"] is False
    assert call["extra_headers"] == {"X-Client-Request-Id": "request-123"}
    assert "Prepwise" in call["instructions"]


def test_service_maps_provider_timeout() -> None:
    create = AsyncMock(
        side_effect=APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    settings = Settings(openai_api_key=SecretStr("test-key"))
    service = AssistantService(settings, cast(AsyncOpenAI, client))

    try:
        asyncio.run(service.respond(message="Hello", request_id="request-123"))
    except AssistantTimeoutError:
        pass
    else:
        raise AssertionError("Expected AssistantTimeoutError")
