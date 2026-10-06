import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, Request
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
from prepwise_api.services.assistant_requests import (
    AssistantRequestConflict,
    AssistantRequestGuard,
    admit_assistant_request,
    check_assistant_request,
)
from prepwise_api.telemetry import record_safe_exception

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
_logger = logging.getLogger("prepwise.ai.api")


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
        return JSONResponse(
            status_code=503,
            content={
                "code": "service_unavailable",
                "detail": _detail(payload.lang, "disabled"),
                "request_id": request_id,
                "mutation_status": "none",
                "retry_safe": True,
            },
        )
    guard = AssistantRequestGuard(session, settings, request_id)
    try:
        check_assistant_request(session, user.id, payload, settings)
    except AssistantRequestConflict as error:
        return _conflict_response(error, payload.lang)
    except (SQLAlchemyError, RuntimeError) as error:
        record_safe_exception(error)
        return JSONResponse(
            status_code=503,
            content={
                "code": "service_unavailable",
                "detail": _detail(payload.lang, "unavailable"),
                "request_id": request_id,
                "mutation_status": "none",
                "retry_safe": True,
            },
        )
    try:
        reservation = reserve_assistant_request(session, user.id, settings)
    except AssistantQuotaExceeded as error:
        guard.finish(succeeded=False)
        return JSONResponse(
            status_code=429,
            content={
                "code": "rate_limit_exceeded",
                "detail": _detail(payload.lang, "limited"),
                "request_id": request_id,
                "mutation_status": "none",
                "retry_safe": True,
            },
            headers={"Retry-After": str(error.retry_after)},
        )
    except (SQLAlchemyError, RuntimeError) as error:
        guard.finish(succeeded=False)
        record_safe_exception(error)
        return JSONResponse(
            status_code=503,
            content={
                "code": "service_unavailable",
                "detail": _detail(payload.lang, "unavailable"),
                **guard.metadata(),
            },
        )
    try:
        guard = admit_assistant_request(session, user.id, payload, settings, request_id)
    except AssistantRequestConflict as error:
        release_assistant_request(session, reservation)
        return _conflict_response(error, payload.lang)
    except (SQLAlchemyError, RuntimeError) as error:
        release_assistant_request(session, reservation)
        record_safe_exception(error)
        return JSONResponse(
            status_code=503,
            content={
                "code": "service_unavailable",
                "detail": _detail(payload.lang, "unavailable"),
                **guard.metadata(),
            },
        )
    context = AssistantToolContext(
        session=session,
        user=user,
        request_id=request_id,
        message=payload.message,
        lang=payload.lang,
        history=tuple(payload.history),
    )
    if settings.assistant_streaming_enabled and "text/event-stream" in request.headers.get(
        "accept", ""
    ):

        async def events() -> AsyncIterator[str]:
            queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=64)
            released = False

            def release_once() -> None:
                nonlocal released
                if not released:
                    released = True
                    release_assistant_request(session, reservation)

            async def publish(event: dict[str, str]) -> None:
                if event.get("type") == "mutation":
                    guard.observe_mutation(event["mutation_status"])
                frame: dict[str, object] = {**event}
                if event.get("type") == "mutation":
                    frame.update(guard.metadata())
                # A stalled/disconnected browser must not retain a producer/lease
                # indefinitely, including terminal frames outside the model timeout.
                async with asyncio.timeout(2):
                    await queue.put(frame)

            async def produce() -> None:
                succeeded = False
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
                    succeeded = True
                    async with asyncio.timeout(2):
                        await queue.put(
                            {
                                "type": "done",
                                "reply": reply.text,
                                "model": reply.model,
                                "response_id": reply.response_id,
                                **guard.metadata(),
                            }
                        )
                except Exception as error:
                    _record_error(error, guard)
                    with suppress(TimeoutError):
                        async with asyncio.timeout(2):
                            await queue.put(
                                {"type": "error", **_error_data(error, payload.lang, guard)}
                            )
                finally:
                    try:
                        # End read/failed-write transactions even if the socket remains
                        # stalled. All valid tool writes commit themselves before return.
                        session.rollback()
                    finally:
                        guard.finish(succeeded=succeeded)
                        release_once()

            task = asyncio.create_task(produce())
            try:
                yield 'data: {"type":"progress","stage":"thinking"}\n\n'
                while True:
                    if task.done() and queue.empty():
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "error",
                                    **_error_data(AssistantUnavailableError(), payload.lang, guard),
                                }
                            )
                            + "\n\n"
                        )
                        break
                    event = await queue.get()
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                    if event["type"] in {"done", "error"}:
                        break
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                guard.finish(succeeded=False)
                release_once()

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
    try:
        if isinstance(assistant, AssistantService):

            async def observe(event: dict[str, str]) -> None:
                if event.get("type") == "mutation":
                    guard.observe_mutation(event["mutation_status"])

            reply = await assistant.respond_with_events(
                message=payload.message,
                request_id=request_id,
                tool_context=context,
                on_event=observe,
                stream_output=False,
            )
        else:
            reply = await assistant.respond(
                message=payload.message,
                request_id=request_id,
                tool_context=context,
            )
        guard.finish(succeeded=True)
    except Exception as error:
        guard.finish(succeeded=False)
        _record_error(error, guard)
        data = _error_data(error, payload.lang, guard)
        return JSONResponse(status_code=int(str(data.pop("status"))), content=data)
    finally:
        session.rollback()
        guard.finish(succeeded=False)
        release_assistant_request(session, reservation)

    if payload.idempotency_key is not None:
        return JSONResponse(
            content={
                "reply": reply.text,
                "model": reply.model,
                "response_id": reply.response_id,
                **guard.metadata(),
            }
        )
    return AssistantMessageResponse(
        reply=reply.text,
        model=reply.model,
        response_id=reply.response_id,
    )


def _record_error(error: Exception, guard: AssistantRequestGuard) -> None:
    record_safe_exception(error)
    _logger.warning(
        "AI workflow failed",
        extra={
            "event": "ai.workflow.failed",
            "error_type": type(error).__name__,
            "request_id": guard.request_id,
            "mutation_status": guard.mutation_status,
        },
    )


def _conflict_response(error: AssistantRequestConflict, lang: str) -> JSONResponse:
    key = (
        "in_progress"
        if error.code == "request_in_progress"
        else "completed"
        if error.code == "assistant_request_completed"
        else "conflict"
        if error.code == "assistant_request_conflict"
        else "unsafe"
    )
    return JSONResponse(
        status_code=409,
        content={
            "code": error.code,
            "detail": _detail(lang, key),
            "request_id": error.request_id,
            "mutation_status": error.mutation_status,
            "retry_safe": False,
        },
        headers={"Retry-After": str(error.retry_after)} if error.retry_after else None,
    )


def _error_data(error: Exception, lang: str, guard: AssistantRequestGuard) -> dict[str, object]:
    key = (
        "configuration"
        if isinstance(error, AssistantConfigurationError)
        else ("timeout" if isinstance(error, AssistantTimeoutError) else "unavailable")
    )
    unsafe = guard.mutation_status != "none"
    return {
        "status": "504" if key == "timeout" else "503",
        "code": "assistant_outcome_unknown"
        if unsafe
        else ("gateway_timeout" if key == "timeout" else "service_unavailable"),
        "detail": _detail(lang, "unsafe" if unsafe else key),
        **guard.metadata(),
    }


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
        "unsafe": (
            "Handlingen kan allerede være gjennomført. Kontroller handlekurven og bestillingene "
            "før du sender en ny forespørsel; denne meldingen blir ikke kjørt på nytt.",
            "The action may already have been applied. Check your cart and orders before "
            "sending a new request; this message will not be run again.",
        ),
        "in_progress": (
            "Denne meldingen behandles allerede. Vent og kontroller handlekurven.",
            "This message is already being processed. Wait and check your cart.",
        ),
        "conflict": (
            "Denne forespørselsnøkkelen tilhører en annen melding.",
            "This request key belongs to a different message.",
        ),
        "completed": (
            "Denne meldingen er allerede behandlet. Send en ny melding hvis du trenger mer hjelp.",
            "This message was already processed. Send a new message if you need more help.",
        ),
    }
    return messages[key][0 if lang == "no" else 1]
