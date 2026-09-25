import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from prepwise_api.api import (
    admin_meals_router,
    admin_orders_router,
    admin_pickup_locations_router,
    admin_router,
    assistant_router,
    cart_router,
    meals_router,
    orders_router,
    pickup_locations_router,
    users_router,
)
from prepwise_api.config import get_settings
from prepwise_api.database import check_database_connection
from prepwise_api.errors import install_exception_handlers
from prepwise_api.observability import (
    REQUEST_ID_HEADER,
    bind_request_id,
    configure_logging,
    reset_request_id,
    resolve_request_id,
)
from prepwise_api.telemetry import correlate_request_span, record_safe_exception

settings = get_settings()
configure_logging(settings.log_level)
request_logger = logging.getLogger("prepwise.http")
health_logger = logging.getLogger("prepwise.health")

app = FastAPI(
    title="Prepwise API",
    version="0.1.0",
)
install_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
app.include_router(meals_router)
app.include_router(assistant_router)
app.include_router(cart_router)
app.include_router(pickup_locations_router)
app.include_router(orders_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(admin_meals_router)
app.include_router(admin_pickup_locations_router)
app.include_router(admin_orders_router)


@app.middleware("http")
async def log_request(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Correlate and log requests without recording headers, tokens or query values."""
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    trace_id = correlate_request_span(request_id)
    token = bind_request_id(request_id)
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception as error:
        request_logger.exception(
            "Unhandled request exception",
            extra={
                "event": "request.exception",
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "error_type": type(error).__name__,
                "trace_id": trace_id,
            },
        )
        raise
    else:
        response.headers[REQUEST_ID_HEADER] = request_id
        request_logger.info(
            "Request completed",
            extra={
                "event": "request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "trace_id": trace_id,
            },
        )
        return response
    finally:
        reset_request_id(token)


@app.get("/health", tags=["health"])
@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    """Confirm that the application process is alive and serving requests."""
    return {"status": "ok"}


@app.get("/health/database", tags=["health"])
@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    """Confirm that critical dependencies are ready for application traffic."""
    try:
        check_database_connection()
    except Exception as error:
        record_safe_exception(error)
        health_logger.exception(
            "Readiness check failed",
            extra={
                "event": "health.readiness_failed",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from None
    return {"status": "ok"}
