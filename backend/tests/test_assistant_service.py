import asyncio
from collections.abc import Mapping
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import httpx
from openai import APITimeoutError, AsyncOpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import SecretStr
from sqlalchemy.orm import Session

from prepwise_api.assistant import (
    AssistantService,
    AssistantTimeoutError,
    AssistantUnavailableError,
)
from prepwise_api.assistant_tools import (
    AssistantToolContext,
    AssistantToolRegistry,
)
from prepwise_api.config import Settings
from prepwise_api.models import User


class RecordingToolRegistry(AssistantToolRegistry):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def definitions(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "name": "search_meals",
                "description": "Search meals",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                "strict": True,
            }
        ]

    def execute_json(
        self,
        name: str,
        arguments: str | Mapping[str, object],
        context: AssistantToolContext,
    ) -> str:
        self.calls.append((name, str(arguments), context.user.external_subject))
        return '{"ok":true,"data":[{"name":"Protein Bowl","protein_grams":"45.00"}]}'


class RecordingKnowledgeTool:
    name = "search_knowledge"

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def definition(self) -> dict[str, object]:
        return {
            "type": "function",
            "name": self.name,
            "description": "Search Prepwise guidance",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    async def execute_json(
        self,
        arguments: str | Mapping[str, object],
        session: Session,
    ) -> str:
        self.calls.append((str(arguments), session))
        return (
            '{"ok":true,"data":[{"content":"Heat until thoroughly hot.",'
            '"source_path":"reheating_guidance.md",'
            '"source_title":"Reheating Guidance","section_title":null,'
            '"chunk_index":0,"score":0.91}]}'
        )


def _tool_context() -> AssistantToolContext:
    return AssistantToolContext(
        session=cast(Session, object()),
        user=User(external_subject="assistant-user", email="assistant@example.com"),
    )


def test_service_calls_responses_api_with_safe_configuration() -> None:
    response = SimpleNamespace(
        id="resp_123",
        model="gpt-5.6-terra",
        output_text="A concise answer.",
        output=[],
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

    reply = asyncio.run(
        service.respond(
            message="Hello",
            request_id="request-123",
            tool_context=_tool_context(),
        )
    )

    assert reply.text == "A concise answer."
    assert reply.response_id == "resp_123"
    create.assert_awaited_once()
    assert create.await_args is not None
    call = create.await_args.kwargs
    assert call["model"] == "gpt-5.6-terra"
    assert call["reasoning"] == {"effort": "low"}
    assert call["input"] == [{"role": "user", "content": "Hello"}]
    assert call["tool_choice"] == "auto"
    assert call["parallel_tool_calls"] is False
    assert len(list(call["tools"])) == 8
    assert call["store"] is False
    assert call["extra_headers"] == {"X-Client-Request-Id": "request-123"}
    assert "Prepwise" in call["instructions"]
    assert "only authoritative source" in call["instructions"]
    assert "explicitly asks" in call["instructions"]
    assert "call search_knowledge" in call["instructions"]
    assert "retrieved passages" in call["instructions"]


def test_service_executes_function_call_and_returns_grounded_follow_up() -> None:
    function_call = ResponseFunctionToolCall(
        type="function_call",
        name="search_meals",
        arguments='{"min_protein_grams":40,"max_calories":800}',
        call_id="call_123",
    )
    first_response = SimpleNamespace(
        id="resp_tools",
        model="gpt-5.6-terra",
        output_text="",
        output=[function_call],
        usage=None,
        _request_id="req_tools",
    )
    final_response = SimpleNamespace(
        id="resp_final",
        model="gpt-5.6-terra",
        output_text="Protein Bowl has 45 g protein.",
        output=[],
        usage=SimpleNamespace(input_tokens=40, output_tokens=10),
        _request_id="req_final",
    )
    create = AsyncMock(side_effect=[first_response, final_response])
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    registry = RecordingToolRegistry()
    knowledge_tool = RecordingKnowledgeTool()
    settings = Settings(openai_api_key=SecretStr("test-key"))
    service = AssistantService(
        settings,
        cast(AsyncOpenAI, client),
        registry,
        knowledge_tool,
    )

    reply = asyncio.run(
        service.respond(
            message="Find meals with at least 40 g protein and below 800 kcal.",
            request_id="request-123",
            tool_context=_tool_context(),
        )
    )

    assert reply.text == "Protein Bowl has 45 g protein."
    assert registry.calls == [
        (
            "search_meals",
            '{"min_protein_grams":40,"max_calories":800}',
            "assistant-user",
        )
    ]
    assert knowledge_tool.calls == []
    assert create.await_count == 2
    second_call = create.await_args_list[1].kwargs
    assert second_call["input"][0] == {
        "role": "user",
        "content": "Find meals with at least 40 g protein and below 800 kcal.",
    }
    assert second_call["input"][1] is function_call
    assert second_call["input"][2] == {
        "type": "function_call_output",
        "call_id": "call_123",
        "output": ('{"ok":true,"data":[{"name":"Protein Bowl","protein_grams":"45.00"}]}'),
    }


def test_service_uses_retrieval_for_unstructured_guidance() -> None:
    function_call = ResponseFunctionToolCall(
        type="function_call",
        name="search_knowledge",
        arguments='{"query":"How should I reheat a Prepwise meal?"}',
        call_id="call_knowledge",
    )
    first_response = SimpleNamespace(
        id="resp_knowledge",
        model="gpt-5.6-terra",
        output_text="",
        output=[function_call],
        usage=None,
        _request_id="req_knowledge",
    )
    final_response = SimpleNamespace(
        id="resp_final",
        model="gpt-5.6-terra",
        output_text=("According to Reheating Guidance, heat the meal until it is thoroughly hot."),
        output=[],
        usage=SimpleNamespace(input_tokens=45, output_tokens=14),
        _request_id="req_final",
    )
    create = AsyncMock(side_effect=[first_response, final_response])
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    registry = RecordingToolRegistry()
    knowledge_tool = RecordingKnowledgeTool()
    service = AssistantService(
        Settings(openai_api_key=SecretStr("test-key")),
        cast(AsyncOpenAI, client),
        registry,
        knowledge_tool,
    )
    context = _tool_context()

    reply = asyncio.run(
        service.respond(
            message="How should I reheat a Prepwise meal?",
            request_id="request-knowledge",
            tool_context=context,
        )
    )

    assert reply.text.startswith("According to Reheating Guidance")
    assert registry.calls == []
    assert knowledge_tool.calls == [
        ('{"query":"How should I reheat a Prepwise meal?"}', context.session)
    ]
    assert create.await_count == 2
    tool_output = create.await_args_list[1].kwargs["input"][2]
    assert tool_output["type"] == "function_call_output"
    assert tool_output["call_id"] == "call_knowledge"
    assert "reheating_guidance.md" in tool_output["output"]
    assert "Heat until thoroughly hot" in tool_output["output"]


def test_service_stops_an_unbounded_tool_loop() -> None:
    responses = [
        SimpleNamespace(
            id=f"resp_{index}",
            model="gpt-5.6-terra",
            output_text="",
            output=[
                ResponseFunctionToolCall(
                    type="function_call",
                    name="search_meals",
                    arguments="{}",
                    call_id=f"call_{index}",
                )
            ],
            usage=None,
            _request_id=f"req_{index}",
        )
        for index in range(6)
    ]
    create = AsyncMock(side_effect=responses)
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    service = AssistantService(
        Settings(openai_api_key=SecretStr("test-key")),
        cast(AsyncOpenAI, client),
        RecordingToolRegistry(),
    )

    try:
        asyncio.run(
            service.respond(
                message="Keep searching forever",
                request_id="request-123",
                tool_context=_tool_context(),
            )
        )
    except AssistantUnavailableError:
        pass
    else:
        raise AssertionError("Expected AssistantUnavailableError")

    assert create.await_count == 6


def test_service_maps_provider_timeout() -> None:
    create = AsyncMock(
        side_effect=APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    settings = Settings(openai_api_key=SecretStr("test-key"))
    service = AssistantService(settings, cast(AsyncOpenAI, client))

    try:
        asyncio.run(
            service.respond(
                message="Hello",
                request_id="request-123",
                tool_context=_tool_context(),
            )
        )
    except AssistantTimeoutError:
        pass
    else:
        raise AssertionError("Expected AssistantTimeoutError")
