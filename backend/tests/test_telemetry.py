from unittest.mock import Mock

import pytest
from opentelemetry import trace

import prepwise_api.telemetry as telemetry
from prepwise_api.config import Settings


def test_telemetry_stays_disabled_without_connection_string() -> None:
    telemetry._telemetry_configured = False

    assert telemetry.configure_telemetry(Settings()) is False


def test_sqlalchemy_instrumentation_is_a_noop_when_telemetry_is_disabled() -> None:
    telemetry._telemetry_configured = False
    engine = Mock()

    telemetry.instrument_sqlalchemy(engine)

    assert engine.mock_calls == []


def test_exception_telemetry_records_type_without_runtime_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    span = Mock()
    span.is_recording.return_value = True
    monkeypatch.setattr(trace, "get_current_span", lambda: span)
    telemetry._telemetry_configured = True
    try:
        telemetry.record_safe_exception(RuntimeError("credential-must-not-escape"))
    finally:
        telemetry._telemetry_configured = False

    span.add_event.assert_called_once_with(
        "exception",
        {"exception.type": "RuntimeError"},
    )
    assert "credential-must-not-escape" not in str(span.mock_calls)


def test_request_id_is_attached_to_current_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    span = Mock()
    span_context = Mock(is_valid=True, trace_id=0xABC)
    span.get_span_context.return_value = span_context
    monkeypatch.setattr(trace, "get_current_span", lambda: span)
    telemetry._telemetry_configured = True
    try:
        trace_id = telemetry.correlate_request_span("request-123")
    finally:
        telemetry._telemetry_configured = False

    span.set_attribute.assert_called_once_with("prepwise.request_id", "request-123")
    assert trace_id == "00000000000000000000000000000abc"
