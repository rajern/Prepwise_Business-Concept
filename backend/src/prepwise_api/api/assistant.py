from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from prepwise_api.assistant import (
    AssistantConfigurationError,
    AssistantResponder,
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
) -> AssistantMessageResponse | JSONResponse:
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
    try:
        reply = await assistant.respond(
            message=payload.message,
            request_id=request_id,
            tool_context=AssistantToolContext(
                session=session,
                user=user,
                request_id=request_id,
                message=payload.message,
                lang=payload.lang,
                history=tuple(payload.history),
            ),
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
