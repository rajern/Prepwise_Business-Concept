"""Offline SSE lifecycle and actual AssistantService streaming-branch regressions."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Generator, Mapping
from pathlib import Path
from types import SimpleNamespace, TracebackType
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionToolCall
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_assistant_api import StubAssistantService
from test_assistant_api import client_and_assistant as client_and_assistant

import prepwise_api.api.assistant as assistant_api
from prepwise_api.assistant import (
    AssistantEventCallback,
    AssistantReply,
    AssistantService,
    AssistantUnavailableError,
    get_assistant_service,
)
from prepwise_api.assistant_tools import AssistantToolContext, AssistantToolRegistry
from prepwise_api.config import Settings
from prepwise_api.database import get_session
from prepwise_api.main import app
from prepwise_api.models import User
from prepwise_api.models.assistant_request import AssistantRequest
from prepwise_api.schemas import AssistantMessageRequest
from prepwise_api.services.assistant_quota import AssistantQuotaExceeded


@pytest.fixture(autouse=True)
def streaming_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSISTANT_STREAMING_ENABLED", "true")


def test_delivery_setting_defaults_to_streaming(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ASSISTANT_STREAMING_ENABLED", raising=False)
    monkeypatch.chdir(tmp_path)
    assert Settings().assistant_streaming_enabled is True


def test_json_recovery_retains_key_guard_for_sse_browser(
    client_and_assistant: tuple[TestClient, StubAssistantService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASSISTANT_STREAMING_ENABLED", "false")
    client, assistant = client_and_assistant
    headers = {"Authorization": "Bearer valid-token", "Accept": "text/event-stream"}
    payload = {"message": "Inspect my cart", "idempotency_key": str(uuid4())}
    response = client.post("/api/assistant/messages", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["mutation_status"] == "none"
    duplicate = client.post("/api/assistant/messages", headers=headers, json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "assistant_request_completed"
    assert len(assistant.calls) == 1


class FakeStream:
    def __init__(self, response: Response, *, hold: bool = False) -> None:
        self.response = response
        self.hold = hold
        self.closed = False

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.closed = True

    async def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        yield SimpleNamespace(type="response.output_text.delta", delta=self.response.output_text)
        if self.hold:
            await asyncio.Event().wait()

    async def get_final_response(self) -> Response:
        return self.response


class FakeResponses:
    def __init__(self, streams: list[FakeStream]) -> None:
        self.streams = streams
        self.calls: list[dict[str, object]] = []
        self.nonstream_calls = 0

    def stream(self, **kwargs: object) -> FakeStream:
        self.calls.append(kwargs)
        return self.streams[len(self.calls) - 1]

    async def create(self, **kwargs: object) -> Response:
        self.nonstream_calls += 1
        raise AssertionError("Streaming must not silently retry through non-streaming API")


class ReadRegistry(AssistantToolRegistry):
    def __init__(self) -> None:
        self.executions = 0

    def execute_json(
        self, name: str, arguments: str | Mapping[str, object], context: AssistantToolContext
    ) -> str:
        self.executions += 1
        return '{"ok":true,"data":{"items":[],"groups":[],"total_quantity":0,"total_nok":"0.00"}}'


def _response(
    text: str, *, call: bool = False, usage: bool = True, status: str = "completed"
) -> Response:
    return cast(
        Response,
        SimpleNamespace(
            id="synthetic-response",
            model="gpt-5.6-terra",
            output_text=text,
            status=status,
            output=[
                ResponseFunctionToolCall(
                    type="function_call", name="get_cart", arguments="{}", call_id="synthetic-call"
                )
            ]
            if call
            else [],
            usage=SimpleNamespace(input_tokens=20, output_tokens=10) if usage else None,
        ),
    )


def _service(streams: list[FakeStream]) -> tuple[AssistantService, FakeResponses, ReadRegistry]:
    responses = FakeResponses(streams)
    registry = ReadRegistry()
    service = AssistantService(
        Settings(app_env="test"), cast(AsyncOpenAI, SimpleNamespace(responses=responses)), registry
    )
    return service, responses, registry


async def _route(service: AssistantService, session: Session) -> StreamingResponse:
    request = Request(
        {
            "type": "http",
            "headers": [(b"accept", b"text/event-stream")],
            "state": {"request_id": "synthetic-stream"},
        }
    )
    response = await assistant_api.create_assistant_message(
        AssistantMessageRequest(message="Inspect my cart"),
        request,
        User(id=uuid4(), external_subject="synthetic-customer"),
        session,
        service,
        Settings(app_env="test"),
    )
    assert isinstance(response, StreamingResponse)
    return response


def _events(frames: list[str | bytes | memoryview[int]]) -> list[dict[str, object]]:
    return [
        cast(
            dict[str, object],
            json.loads((frame if isinstance(frame, str) else bytes(frame).decode())[6:]),
        )
        for frame in frames
    ]


def test_sse_requires_authentication_and_preserves_quota(
    client_and_assistant: tuple[TestClient, StubAssistantService],
) -> None:
    client, service = client_and_assistant
    anonymous = client.post(
        "/api/assistant/messages",
        headers={"Accept": "text/event-stream"},
        json={"message": "Hello"},
    )
    assert anonymous.status_code == 401 and service.calls == []
    headers = {"Accept": "text/event-stream", "Authorization": "Bearer valid-token"}
    for _ in range(15):
        response = client.post(
            "/api/assistant/messages", headers=headers, json={"message": "Hello"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert '"type": "done"' in response.text
    denied = client.post("/api/assistant/messages", headers=headers, json={"message": "Hello"})
    assert denied.status_code == 429 and denied.json()["code"] == "rate_limit_exceeded"
    assert int(denied.headers["Retry-After"]) > 0
    assert len(service.calls) == 15


def test_sdk_stream_draft_resets_before_tools_and_only_final_reply_is_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = MagicMock()
    monkeypatch.setattr(assistant_api, "reserve_assistant_request", lambda *args: uuid4())
    monkeypatch.setattr(assistant_api, "release_assistant_request", release)
    session = MagicMock(spec=Session)
    streams = [
        FakeStream(_response("Draft before checking", call=True)),
        FakeStream(_response("Verified final answer")),
    ]
    service, responses, registry = _service(streams)

    async def run() -> list[dict[str, object]]:
        response = await _route(service, session)
        return _events([frame async for frame in response.body_iterator])

    events = asyncio.run(run())
    first = next(
        index for index, event in enumerate(events) if event.get("text") == "Draft before checking"
    )
    reset = next(index for index, event in enumerate(events) if event.get("type") == "reset")
    assert first < reset
    assert events[-1]["type"] == "done" and events[-1]["reply"] == "Verified final answer"
    assert sum(event.get("type") == "done" for event in events) == 1
    assert registry.executions == 1 and len(responses.calls) == 2 and responses.nonstream_calls == 0
    assert all(stream.closed for stream in streams)
    release.assert_called_once()
    session.rollback.assert_called_once()
    assert all(
        call["store"] is False and call["max_output_tokens"] == 800 for call in responses.calls
    )


@pytest.mark.parametrize("failure", ["missing-usage", "incomplete"])
def test_streamed_incomplete_or_unmetered_output_never_confirms_or_executes_tools(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    release = MagicMock()
    monkeypatch.setattr(assistant_api, "reserve_assistant_request", lambda *args: uuid4())
    monkeypatch.setattr(assistant_api, "release_assistant_request", release)
    stream = FakeStream(
        _response(
            "Unconfirmed partial draft",
            call=True,
            usage=failure != "missing-usage",
            status="incomplete" if failure == "incomplete" else "completed",
        )
    )
    service, responses, registry = _service([stream])

    async def run() -> list[dict[str, object]]:
        response = await _route(service, MagicMock(spec=Session))
        return _events([frame async for frame in response.body_iterator])

    events = asyncio.run(run())
    assert any(event.get("type") == "delta" for event in events)
    assert events[-1]["type"] == "error" and events[-1]["status"] == "503"
    assert not any(event.get("type") == "done" for event in events)
    assert registry.executions == 0 and len(responses.calls) == 1
    release.assert_called_once()


def test_disconnect_cancels_provider_without_retry_and_releases_lease_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = MagicMock()
    monkeypatch.setattr(assistant_api, "reserve_assistant_request", lambda *args: uuid4())
    monkeypatch.setattr(assistant_api, "release_assistant_request", release)
    stream = FakeStream(_response("Pending draft"), hold=True)
    service, responses, _ = _service([stream])

    async def run() -> None:
        response = await _route(service, MagicMock(spec=Session))
        iterator = response.body_iterator
        assert isinstance(iterator, AsyncIterator)
        while True:
            frame = await anext(iterator)
            if "Pending draft" in str(frame):
                break
        await asyncio.wait_for(iterator.aclose(), timeout=1)  # type: ignore[attr-defined]
        assert stream.closed

    asyncio.run(run())
    assert len(responses.calls) == 1 and responses.nonstream_calls == 0
    release.assert_called_once()


class SaturatingAssistant(AssistantService):
    async def respond_with_events(
        self,
        *,
        message: str,
        request_id: str,
        tool_context: AssistantToolContext,
        on_event: AssistantEventCallback | None = None,
        stream_output: bool = True,
    ) -> AssistantReply:
        assert callable(on_event)
        for _ in range(65):
            await on_event({"type": "delta", "text": "draft"})
        raise AssertionError("Queue must bound abandoned consumers")


def test_stalled_consumer_releases_lease_after_bounded_terminal_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    released = asyncio.Event()
    release = MagicMock(side_effect=lambda *args: released.set())
    monkeypatch.setattr(assistant_api, "reserve_assistant_request", lambda *args: uuid4())
    monkeypatch.setattr(assistant_api, "release_assistant_request", release)

    async def run() -> None:
        response = await _route(
            SaturatingAssistant(Settings(app_env="test")), MagicMock(spec=Session)
        )
        iterator = response.body_iterator
        assert isinstance(iterator, AsyncIterator)
        await anext(iterator)
        await asyncio.wait_for(released.wait(), timeout=5)
        await iterator.aclose()  # type: ignore[attr-defined]

    asyncio.run(run())
    release.assert_called_once()


def _wire_response(output: list[dict[str, object]], identifier: str) -> dict[str, object]:
    return {
        "id": identifier,
        "object": "response",
        "created_at": 1,
        "model": "gpt-5.6-terra",
        "status": "completed",
        "output": output,
        "parallel_tool_calls": False,
        "store": False,
        "usage": {
            "input_tokens": 20,
            "output_tokens": 10,
            "total_tokens": 30,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def test_real_async_sdk_sse_round_trip_only_replays_api_fields() -> None:
    """Use the actual SDK parser and HTTP serialization, never fake Responses methods."""
    requests: list[dict[str, object]] = []
    first = _wire_response(
        [
            {
                "type": "reasoning",
                "id": "rs_local",
                "summary": [],
                "encrypted_content": "synthetic-encrypted-reasoning",
            },
            {
                "type": "message",
                "id": "msg_local",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "Checking", "annotations": []}],
            },
            {
                "type": "function_call",
                "id": "fc_local",
                "call_id": "call_local",
                "name": "get_cart",
                "arguments": "{}",
                "status": "completed",
            },
        ],
        "resp_first",
    )
    final = _wire_response(
        [
            {
                "type": "message",
                "id": "msg_final",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": "Verified empty cart", "annotations": []}
                ],
            },
        ],
        "resp_final",
    )

    async def transport(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        response = first if len(requests) == 1 else final
        events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {**response, "status": "in_progress", "output": []},
            },
            {"type": "response.completed", "sequence_number": 1, "response": response},
        ]
        content = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)

    async def run() -> AssistantReply:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            async with AsyncOpenAI(
                api_key="offline-synthetic", http_client=http, max_retries=0
            ) as sdk:
                registry = ReadRegistry()
                service = AssistantService(Settings(app_env="test"), sdk, registry)

                async def ignore(event: dict[str, str]) -> None:
                    pass

                reply = await service.respond_with_events(
                    message="Show my cart",
                    request_id="offline-wire-test",
                    tool_context=AssistantToolContext(
                        session=MagicMock(spec=Session),
                        user=User(id=uuid4(), external_subject="wire"),
                    ),
                    on_event=ignore,
                )
                assert registry.executions == 1
                return reply

    assert asyncio.run(run()).text == "Verified empty cart"
    assert len(requests) == 2
    items = requests[1]["input"]
    assert isinstance(items, list)
    call = next(item for item in items if item.get("type") == "function_call")
    message = next(item for item in items if item.get("type") == "message")
    reasoning = next(item for item in items if item.get("type") == "reasoning")
    assert call["call_id"] == "call_local" and call["arguments"] == "{}"
    assert "parsed_arguments" not in call
    assert "parsed" not in message["content"][0]
    assert reasoning["encrypted_content"] == "synthetic-encrypted-reasoning"
    assert sum(item.get("type") == "function_call_output" for item in items) == 1
    assert all(body["store"] is False and body["max_output_tokens"] == 800 for body in requests)


class AppliedThenFailedAssistant(AssistantService):
    def __init__(self) -> None:
        super().__init__(Settings(app_env="test"))
        self.executions = 0

    async def respond_with_events(
        self,
        *,
        message: str,
        request_id: str,
        tool_context: AssistantToolContext,
        on_event: AssistantEventCallback | None = None,
        stream_output: bool = True,
    ) -> AssistantReply:
        assert callable(on_event)
        await on_event({"type": "mutation", "mutation_status": "unknown"})
        self.executions += 1
        await on_event({"type": "mutation", "mutation_status": "applied"})
        raise AssistantUnavailableError


@pytest.mark.parametrize("stream", [False, True])
def test_partial_failure_and_duplicate_key_are_safe_for_json_and_sse(
    client_and_assistant: tuple[TestClient, StubAssistantService],
    stream: bool,
) -> None:
    client, _ = client_and_assistant
    service = AppliedThenFailedAssistant()
    app.dependency_overrides[get_assistant_service] = lambda: service
    headers = {"Authorization": "Bearer valid-token", "X-Request-ID": "original-apply"}
    if stream:
        headers["Accept"] = "text/event-stream"
    payload = {"message": "Add two meals", "lang": "en", "idempotency_key": str(uuid4())}
    response = client.post("/api/assistant/messages", headers=headers, json=payload)
    if stream:
        frames = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data:")
        ]
        mutation = next(frame for frame in frames if frame.get("type") == "mutation")
        assert mutation["retry_safe"] is False and mutation["mutation_status"] == "unknown"
        error = frames[-1]
    else:
        assert response.status_code == 503
        error = response.json()
    assert error["code"] == "assistant_outcome_unknown"
    assert error["mutation_status"] == "applied" and error["retry_safe"] is False
    assert error["request_id"] == "original-apply"
    duplicate = client.post("/api/assistant/messages", headers=headers, json=payload)
    assert duplicate.status_code == 409 and service.executions == 1
    assert duplicate.json()["code"] == "assistant_outcome_unknown"
    assert duplicate.json()["retry_safe"] is False


class GuardCheckingWriteRegistry(ReadRegistry):
    def execute_json(
        self, name: str, arguments: str | Mapping[str, object], context: AssistantToolContext
    ) -> str:
        with Session(context.session.get_bind()) as reader:
            record = reader.scalar(select(AssistantRequest))
            assert record is not None and record.mutation_status == "unknown"
        return super().execute_json(name, arguments, context)


def test_real_service_persists_guard_before_tool_then_reports_applied_on_later_failure(
    client_and_assistant: tuple[TestClient, StubAssistantService],
) -> None:
    client, _ = client_and_assistant
    first = _response("Checking before adding", call=True)
    first.output[0].name = "add_to_cart"  # type: ignore[union-attr]
    responses = FakeResponses(
        [
            FakeStream(first),
            FakeStream(_response("Never confirmed", status="incomplete")),
        ]
    )
    registry = GuardCheckingWriteRegistry()
    service = AssistantService(
        Settings(app_env="test"), cast(AsyncOpenAI, SimpleNamespace(responses=responses)), registry
    )
    app.dependency_overrides[get_assistant_service] = lambda: service
    headers = {"Accept": "text/event-stream", "Authorization": "Bearer valid-token"}
    payload = {"message": "Add two meals", "idempotency_key": str(uuid4())}
    result = client.post("/api/assistant/messages", headers=headers, json=payload)
    frames = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith("data:")]
    assert registry.executions == 1
    assert frames[-1]["code"] == "assistant_outcome_unknown"
    assert frames[-1]["mutation_status"] == "applied" and frames[-1]["retry_safe"] is False
    assert not any(frame.get("type") == "done" for frame in frames)
    duplicate = client.post("/api/assistant/messages", headers=headers, json=payload)
    assert duplicate.status_code == 409 and registry.executions == 1


@pytest.mark.parametrize("stream", [False, True])
def test_successful_read_only_key_is_not_run_again(
    client_and_assistant: tuple[TestClient, StubAssistantService],
    stream: bool,
) -> None:
    client, service = client_and_assistant
    headers = {"Authorization": "Bearer valid-token"}
    if stream:
        headers["Accept"] = "text/event-stream"
    payload = {"message": "Show meals", "lang": "en", "idempotency_key": str(uuid4())}
    first = client.post("/api/assistant/messages", headers=headers, json=payload)
    assert first.status_code == 200
    duplicate = client.post("/api/assistant/messages", headers=headers, json=payload)
    assert duplicate.status_code == 409 and len(service.calls) == 1
    error = duplicate.json()
    assert error["code"] == "assistant_request_completed"
    assert error["mutation_status"] == "none" and error["retry_safe"] is False
    assert (
        "already processed" in error["detail"]
        and "already have been applied" not in error["detail"]
    )


def test_quota_rejected_random_keys_cannot_grow_request_metadata(
    client_and_assistant: tuple[TestClient, StubAssistantService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, service = client_and_assistant

    def reject(*args: object) -> None:
        raise AssistantQuotaExceeded(30)

    monkeypatch.setattr(assistant_api, "reserve_assistant_request", reject)
    for _ in range(5):
        result = client.post(
            "/api/assistant/messages",
            headers={"Authorization": "Bearer valid-token"},
            json={"message": "Show meals", "idempotency_key": str(uuid4())},
        )
        assert result.status_code == 429
    iterator = cast(Generator[Session, None, None], app.dependency_overrides[get_session]())
    try:
        reader = next(iterator)
        assert reader.scalar(select(AssistantRequest)) is None
    finally:
        iterator.close()
    assert service.calls == []
