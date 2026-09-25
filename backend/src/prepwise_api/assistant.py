import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from opentelemetry import trace
from opentelemetry.trace import Span

from prepwise_api.config import Settings, get_settings
from prepwise_api.telemetry import record_safe_exception

assistant_logger = logging.getLogger("prepwise.ai")
_tracer = trace.get_tracer("prepwise.ai")

_ASSISTANT_INSTRUCTIONS = """You are the Prepwise customer assistant.
Be concise, honest and helpful. You do not yet have access to the live meal catalogue, carts,
orders or service knowledge. Never invent Prepwise-specific facts. If a request requires live
application data or an action, explain that the capability is not available yet.
"""


class AssistantConfigurationError(Exception):
    """The assistant is missing required server-side configuration."""


class AssistantTimeoutError(Exception):
    """The model provider did not respond before the configured deadline."""


class AssistantUnavailableError(Exception):
    """The model provider could not complete the request safely."""


@dataclass(frozen=True, slots=True)
class AssistantReply:
    text: str
    model: str
    response_id: str


class AssistantResponder(Protocol):
    async def respond(self, *, message: str, request_id: str) -> AssistantReply: ...


class AssistantService:
    """Call the OpenAI Responses API without recording customer content in telemetry."""

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings
        self._client = client

    def _resolve_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if self._settings.openai_api_key is None:
            raise AssistantConfigurationError

        self._client = AsyncOpenAI(
            api_key=self._settings.openai_api_key.get_secret_value(),
            timeout=self._settings.openai_timeout_seconds,
            max_retries=self._settings.openai_max_retries,
        )
        return self._client

    async def respond(self, *, message: str, request_id: str) -> AssistantReply:
        client = self._resolve_client()
        model = self._settings.openai_model

        try:
            with _tracer.start_as_current_span(
                "openai.responses.create",
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                _set_request_span_attributes(span, model, self._settings.openai_reasoning_effort)
                response = await client.responses.create(
                    model=model,
                    reasoning={"effort": self._settings.openai_reasoning_effort},
                    instructions=_ASSISTANT_INSTRUCTIONS,
                    input=message,
                    store=False,
                    extra_headers={"X-Client-Request-Id": request_id},
                )
                response_text = response.output_text.strip()
                if not response_text:
                    raise AssistantUnavailableError

                provider_request_id = getattr(response, "_request_id", None)
                _set_response_span_attributes(span, response, provider_request_id)
                assistant_logger.info(
                    "AI response completed",
                    extra={
                        "event": "ai.response.completed",
                        "model": response.model,
                        "provider_request_id": provider_request_id,
                        "input_tokens": response.usage.input_tokens if response.usage else None,
                        "output_tokens": response.usage.output_tokens if response.usage else None,
                    },
                )
                return AssistantReply(
                    text=response_text,
                    model=response.model,
                    response_id=response.id,
                )
        except APITimeoutError as error:
            _record_failure(error, model, "ai.response.timeout")
            raise AssistantTimeoutError from error
        except (APIConnectionError, RateLimitError, APIStatusError) as error:
            _record_failure(error, model, "ai.response.unavailable")
            raise AssistantUnavailableError from error


def _set_request_span_attributes(span: Span, model: str, reasoning_effort: str) -> None:
    span.set_attribute("gen_ai.provider.name", "openai")
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", model)
    span.set_attribute("gen_ai.request.reasoning_effort", reasoning_effort)


def _set_response_span_attributes(
    span: Span,
    response: object,
    provider_request_id: str | None,
) -> None:
    response_id = getattr(response, "id", None)
    response_model = getattr(response, "model", None)
    usage = getattr(response, "usage", None)
    if isinstance(response_id, str):
        span.set_attribute("gen_ai.response.id", response_id)
    if isinstance(response_model, str):
        span.set_attribute("gen_ai.response.model", response_model)
    if isinstance(provider_request_id, str):
        span.set_attribute("openai.request_id", provider_request_id)
    if usage is not None:
        span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)


def _record_failure(error: Exception, model: str, event: str) -> None:
    record_safe_exception(error)
    assistant_logger.warning(
        "AI request failed",
        extra={
            "event": event,
            "model": model,
            "error_type": type(error).__name__,
        },
    )


@lru_cache
def get_assistant_service() -> AssistantResponder:
    return AssistantService(get_settings())
