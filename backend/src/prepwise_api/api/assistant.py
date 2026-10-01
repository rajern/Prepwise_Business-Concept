import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from prepwise_api.assistant import (
    AssistantConfigurationError,
    AssistantResponder,
    AssistantService,
    AssistantTimeoutError,
    AssistantUnavailableError,
    get_assistant_service,
)
from prepwise_api.assistant_tools import AssistantToolContext
from prepwise_api.auth import get_current_user
from prepwise_api.config import Settings, get_settings
from prepwise_api.database import get_session
from prepwise_api.models import User
from prepwise_api.schemas import AssistantMessageRequest, AssistantMessageResponse
from prepwise_api.services.assistant_quota import (
    AssistantQuotaExceeded,
    release_assistant_request,
    reserve_assistant_request,
)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/messages", response_model=AssistantMessageResponse)
async def create_assistant_message(
    payload: AssistantMessageRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    assistant: Annotated[AssistantResponder, Depends(get_assistant_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssistantMessageResponse | JSONResponse | StreamingResponse:
    """Send one authenticated customer message to the configured model."""
    request_id = str(request.state.request_id)
    if not settings.assistant_enabled:
        raise HTTPException(status_code=503, detail=_detail(payload.lang, "disabled"))
    try:
        reservation = reserve_assistant_request(session, user.id, settings)
    except AssistantQuotaExceeded as error:
        return JSONResponse(
            status_code=429,
            content={
                "code": "rate_limit_exceeded",
                "detail": _detail(payload.lang, "limited"),
                "request_id": request_id,
            },
            headers={"Retry-After": str(error.retry_after)},
        )
    except (SQLAlchemyError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=_detail(payload.lang, "unavailable")) from error
    context = AssistantToolContext(
        session=session,
        user=user,
        request_id=request_id,
        message=payload.message,
        lang=payload.lang,
        history=tuple(payload.history),
    )
    if "text/event-stream" in request.headers.get("accept", ""):

        async def events() -> AsyncIterator[str]:
            queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=64)
            released = False

            def release_once() -> None:
                nonlocal released
                if not released:
                    released = True
                    release_assistant_request(session, reservation)

            async def publish(event: dict[str, str]) -> None:
                # A stalled/disconnected browser must not retain a producer/lease
                # indefinitely, including terminal frames outside the model timeout.
                async with asyncio.timeout(2):
                    await queue.put(event)

            async def produce() -> None:
                try:
                    if isinstance(assistant, AssistantService):
                        reply = await assistant.respond_with_events(
                            message=payload.message,
                            request_id=request_id,
                            tool_context=context,
                            on_event=publish,
                        )
                    else:
                        # Compatibility with offline responders; no provider fallback/retry.
                        reply = await assistant.respond(
                            message=payload.message,
                            request_id=request_id,
                            tool_context=context,
                        )
                    await publish(
                        {
                            "type": "done",
                            "reply": reply.text,
                            "model": reply.model,
                            "response_id": reply.response_id,
                        }
                    )
                except Exception as error:
                    key = "timeout" if isinstance(error, AssistantTimeoutError) else "unavailable"
                    with suppress(TimeoutError):
                        await publish(
                            {
                                "type": "error",
                                "status": "504" if key == "timeout" else "503",
                                "detail": _detail(payload.lang, key),
                            }
                        )
                finally:
                    try:
                        # End read/failed-write transactions even if the socket remains
                        # stalled. All valid tool writes commit themselves before return.
                        session.rollback()
                    finally:
                        release_once()

            task = asyncio.create_task(produce())
            try:
                yield 'data: {"type":"progress","stage":"thinking"}\n\n'
                while True:
                    if task.done() and queue.empty():
                        yield 'data: {"type":"error","status":"503"}\n\n'
                        break
                    event = await queue.get()
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                    if event["type"] in {"done", "error"}:
                        break
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                release_once()

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
    try:
        reply = await assistant.respond(
            message=payload.message,
            request_id=request_id,
            tool_context=context,
        )
    except AssistantConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_detail(payload.lang, "configuration"),
        ) from error
    except AssistantTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_detail(payload.lang, "timeout"),
        ) from error
    except AssistantUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_detail(payload.lang, "unavailable"),
        ) from error
    finally:
        release_assistant_request(session, reservation)

    return AssistantMessageResponse(
        reply=reply.text,
        model=reply.model,
        response_id=reply.response_id,
    )


def _detail(lang: str, key: str) -> str:
    messages = {
        "configuration": (
            "AI-assistenten er ikke konfigurert",
            "The AI assistant is not configured",
        ),
        "timeout": (
            "AI-assistenten brukte for lang tid. Prøv igjen.",
            "The AI assistant timed out. Please try again.",
        ),
        "unavailable": (
            "AI-assistenten er midlertidig utilgjengelig",
            "The AI assistant is temporarily unavailable",
        ),
        "disabled": (
            "AI-assistenten er midlertidig deaktivert",
            "The AI assistant is temporarily disabled",
        ),
        "limited": (
            "Bruksgrensen er nådd, eller en melding behandles allerede. Prøv igjen senere.",
            "The usage limit was reached, or a message is already being processed. "
            "Try again later.",
        ),
    }
    return messages[key][0 if lang == "no" else 1]
