from typing import TYPE_CHECKING

from prepwise_api.config import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

_telemetry_configured = False


def configure_telemetry(settings: Settings | None = None) -> bool:
    """Configure Azure Monitor once when its production connection string is present."""
    global _telemetry_configured
    if _telemetry_configured:
        return True

    resolved_settings = settings or get_settings()
    connection_string = resolved_settings.applicationinsights_connection_string
    if not connection_string:
        return False

    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.sdk.resources import Resource

    configure_azure_monitor(
        connection_string=connection_string,
        disable_logging=True,
        enable_live_metrics=True,
        resource=Resource.create(
            {
                "service.name": resolved_settings.otel_service_name,
                "deployment.environment.name": resolved_settings.app_env,
            }
        ),
    )
    _telemetry_configured = True
    return True


def instrument_sqlalchemy(engine: "Engine") -> None:
    """Create dependency spans for SQLAlchemy without exposing connection credentials."""
    if not _telemetry_configured:
        return

    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=engine)


def correlate_request_span(request_id: str) -> str | None:
    """Attach the application request ID and return the active trace ID for logs."""
    if not _telemetry_configured:
        return None

    from opentelemetry import trace

    span = trace.get_current_span()
    span.set_attribute("prepwise.request_id", request_id)
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")


def record_safe_exception(exception: Exception) -> None:
    """Mark the active trace as failed while exporting only the exception type."""
    if not _telemetry_configured:
        return

    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    span = trace.get_current_span()
    if not span.is_recording():
        return
    error_type = type(exception).__name__
    span.add_event("exception", {"exception.type": error_type})
    span.set_status(Status(StatusCode.ERROR, error_type))
