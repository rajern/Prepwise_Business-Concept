import json
import logging
import re
import sys
import traceback
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_SAFE_EXTRA_FIELDS = (
    "event",
    "request_id",
    "trace_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "error_type",
    "order_id",
    "item_count",
    "total_nok",
    "from_status",
    "to_status",
    "model",
    "provider_request_id",
    "input_tokens",
    "output_tokens",
)


class JsonLogFormatter(logging.Formatter):
    """Render one machine-readable JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context_request_id = _request_id.get()
        if context_request_id:
            payload["request_id"] = context_request_id
        for field in _SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            exception_type, _, exception_traceback = record.exc_info
            payload["exception"] = {
                "type": exception_type.__name__ if exception_type else "Exception",
                "stack": [
                    {
                        "file": frame.filename,
                        "line": frame.lineno,
                        "function": frame.name,
                    }
                    for frame in traceback.extract_tb(exception_traceback)
                ]
                if exception_traceback
                else [],
            }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    """Configure Prepwise application logs without altering third-party loggers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    app_logger = logging.getLogger("prepwise")
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.setLevel(level)
    app_logger.propagate = False


def resolve_request_id(candidate: str | None) -> str:
    """Accept a safe caller correlation ID or create an opaque UUID."""
    if candidate and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)
