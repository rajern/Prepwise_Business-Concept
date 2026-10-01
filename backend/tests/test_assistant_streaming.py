"""Offline SSE lifecycle and actual AssistantService streaming-branch regressions."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from types import SimpleNamespace, TracebackType
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionToolCall
from sqlalchemy.orm import Session
from test_assistant_api import StubAssistantService
from test_assistant_api import client_and_assistant as client_and_assistant

import prepwise_api.api.assistant as assistant_api
from prepwise_api.assistant import AssistantEventCallback, AssistantReply, AssistantService
from prepwise_api.assistant_tools import AssistantToolContext, AssistantToolRegistry
from prepwise_api.config import Settings
from prepwise_api.models import User
from prepwise_api.schemas import AssistantMessageRequest


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
