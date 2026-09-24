import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import HTTPExceptionHandler

from prepwise_api.observability import REQUEST_ID_HEADER, resolve_request_id

error_logger = logging.getLogger("prepwise.errors")

_ERROR_CODES = {
    400: "bad_request",
    401: "authentication_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    503: "service_unavailable",
}


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str):
        return request_id
    return resolve_request_id(None)


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    detail: str,
    headers: Mapping[str, str] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body: dict[str, Any] = {
        "code": code,
        "detail": detail,
        "request_id": request_id,
    }
    if errors:
        body["errors"] = errors
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(status_code=status_code, content=body, headers=response_headers)


async def http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    detail = (
        exception.detail
        if isinstance(exception.detail, str)
        else HTTPStatus(exception.status_code).phrase
        if exception.status_code in HTTPStatus._value2member_map_
        else "Request failed"
    )
    return _error_response(
        request,
        status_code=exception.status_code,
        code=_ERROR_CODES.get(exception.status_code, "http_error"),
        detail=detail,
        headers=exception.headers,
    )


async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    issues = [
        {
            "location": ".".join(str(part) for part in issue["loc"]),
            "message": str(issue["msg"]),
            "type": str(issue["type"]),
        }
        for issue in exception.errors()
    ]
    return _error_response(
        request,
        status_code=422,
        code="validation_error",
        detail="Invalid request data",
        errors=issues,
    )


async def database_exception_handler(
    request: Request,
    exception: SQLAlchemyError,
) -> JSONResponse:
    error_logger.exception(
        "Database request failed",
        exc_info=exception,
        extra={
            "event": "request.database_error",
            "request_id": _request_id(request),
            "path": request.url.path,
            "error_type": type(exception).__name__,
        },
    )
    return _error_response(
        request,
        status_code=503,
        code="database_unavailable",
        detail="The service is temporarily unavailable",
    )


async def unhandled_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    error_logger.exception(
        "Unhandled application error",
        exc_info=exception,
        extra={
            "event": "request.unhandled_error",
            "request_id": _request_id(request),
            "path": request.url.path,
            "error_type": type(exception).__name__,
        },
    )
    return _error_response(
        request,
        status_code=500,
        code="internal_error",
        detail="An unexpected error occurred",
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        StarletteHTTPException, cast(HTTPExceptionHandler, http_exception_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast(HTTPExceptionHandler, validation_exception_handler)
    )
    app.add_exception_handler(
        SQLAlchemyError, cast(HTTPExceptionHandler, database_exception_handler)
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
