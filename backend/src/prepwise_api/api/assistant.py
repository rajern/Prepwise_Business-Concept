from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from prepwise_api.database import get_session
from prepwise_api.models import User
from prepwise_api.schemas import AssistantMessageRequest, AssistantMessageResponse

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/messages", response_model=AssistantMessageResponse)
async def create_assistant_message(
    payload: AssistantMessageRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    assistant: Annotated[AssistantResponder, Depends(get_assistant_service)],
) -> AssistantMessageResponse:
    """Send one authenticated customer message to the configured model."""
    request_id = str(request.state.request_id)
    try:
        reply = await assistant.respond(
            message=payload.message,
            request_id=request_id,
            tool_context=AssistantToolContext(
                session=session,
                user=user,
                request_id=request_id,
                message=payload.message,
            ),
        )
    except AssistantConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI assistant is not configured",
        ) from error
    except AssistantTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI assistant timed out. Please try again.",
        ) from error
    except AssistantUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI assistant is temporarily unavailable",
        ) from error

    return AssistantMessageResponse(
        reply=reply.text,
        model=reply.model,
        response_id=reply.response_id,
    )
