"""Fenced admission and conservative replay safety for customer AI requests."""

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from prepwise_api.config import Settings
from prepwise_api.models.assistant_request import AssistantRequest
from prepwise_api.schemas.assistant import AssistantMessageRequest

_logger = logging.getLogger("prepwise.ai.requests")


class AssistantRequestConflict(Exception):
    def __init__(
        self, code: str, request_id: str, mutation_status: str, retry_after: int | None = None
    ) -> None:
        self.code = code
        self.request_id = request_id
        self.mutation_status = mutation_status
        self.retry_after = retry_after


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _clock(session: Session, settings: Settings, now: datetime | None = None) -> datetime:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        session.execute(text("SET LOCAL lock_timeout = '2000ms'"))
        session.execute(text("SET LOCAL statement_timeout = '2000ms'"))
        instant = now or session.scalar(select(func.clock_timestamp()))
        if not isinstance(instant, datetime):
            raise RuntimeError("Unable to resolve database clock")
        return _utc(instant)
    if dialect == "sqlite" and settings.app_env != "production":
        return _utc(now or datetime.now(UTC))
    raise RuntimeError("Production AI replay protection requires PostgreSQL")


def _payload_hash(payload: AssistantMessageRequest) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json", exclude={"idempotency_key"}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check_record(record: AssistantRequest, fingerprint: str, instant: datetime) -> None:
    if record.payload_hash != fingerprint:
        raise AssistantRequestConflict(
            "assistant_request_conflict", record.first_request_id, record.mutation_status
        )
    if record.state == "completed" and record.mutation_status == "none":
        raise AssistantRequestConflict(
            "assistant_request_completed", record.first_request_id, "none"
        )
    if record.mutation_status != "none":
        raise AssistantRequestConflict(
            "assistant_request_already_applied"
            if record.state == "completed" and record.mutation_status == "applied"
            else "assistant_outcome_unknown",
            record.first_request_id,
            record.mutation_status,
        )
    if record.state == "running" and _utc(record.lease_expires_at) > instant:
        raise AssistantRequestConflict(
            "request_in_progress",
            record.first_request_id,
            "none",
            max(1, math.ceil((_utc(record.lease_expires_at) - instant).total_seconds())),
        )


def check_assistant_request(
    source_session: Session,
    user_id: UUID,
    payload: AssistantMessageRequest,
    settings: Settings,
) -> None:
    """Read-only preflight: quota-rejected keys must never create records.

    Final admission repeats all checks under a row lock after quota reservation.
    """
    if payload.idempotency_key is None:
        return
    with Session(source_session.get_bind()) as session, session.begin():
        instant = _clock(session, settings)
        record = session.scalar(
            select(AssistantRequest).where(
                AssistantRequest.user_id == user_id,
                AssistantRequest.idempotency_key == payload.idempotency_key,
            )
        )
        if record is not None:
            _check_record(record, _payload_hash(payload), instant)


@dataclass
class AssistantRequestGuard:
    source_session: Session
    settings: Settings
    request_id: str
    record_id: UUID | None = None
    attempt_id: UUID | None = None
    mutation_status: str = "none"
    _finished: bool = field(default=False, init=False, repr=False)

    def metadata(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "mutation_status": self.mutation_status,
            "retry_safe": self.mutation_status == "none",
        }

    def observe_mutation(self, mutation_status: str) -> None:
        if mutation_status not in {"unknown", "applied"}:
            raise ValueError("Invalid AI mutation state")
        # Once any write succeeded, retain that fact even if a subsequent step fails.
        if self.mutation_status != "applied":
            self.mutation_status = mutation_status
        if self.record_id is None:
            return  # Legacy unkeyed callers still receive honest outcome metadata.
        with Session(self.source_session.get_bind()) as session, session.begin():
            instant = _clock(session, self.settings)
            record = session.scalar(
                select(AssistantRequest)
                .where(AssistantRequest.id == self.record_id)
                .with_for_update()
            )
            if (
                record is None
                or record.attempt_id != self.attempt_id
                or record.state != "running"
                or _utc(record.lease_expires_at) <= instant
            ):
                raise AssistantRequestConflict(
                    "assistant_outcome_unknown", self.request_id, self.mutation_status
                )
            if record.mutation_status != "applied":
                record.mutation_status = mutation_status
            # This independent transaction commits BEFORE control returns to the tool.

    def finish(self, *, succeeded: bool) -> None:
        if self._finished:
            return
        self._finished = True
        if self.record_id is None:
            return
        try:
            with Session(self.source_session.get_bind()) as session, session.begin():
                instant = _clock(session, self.settings)
                record = session.scalar(
                    select(AssistantRequest)
                    .where(AssistantRequest.id == self.record_id)
                    .with_for_update()
                )
                if record is not None and record.attempt_id == self.attempt_id:
                    record.state = "completed" if succeeded else "failed"
                    record.finished_at = instant
        except (SQLAlchemyError, RuntimeError):
            # Never erase the pre-write marker. An unreleased read-only lease may
            # expire; an uncertain mutation remains permanently protected.
            _logger.warning(
                "AI request finalization failed", extra={"event": "ai.request.finish_failed"}
            )


def admit_assistant_request(
    source_session: Session,
    user_id: UUID,
    payload: AssistantMessageRequest,
    settings: Settings,
    request_id: str,
    *,
    now: datetime | None = None,
) -> AssistantRequestGuard:
    guard = AssistantRequestGuard(source_session, settings, request_id)
    if payload.idempotency_key is None:
        return guard
    fingerprint = _payload_hash(payload)
    attempt_id = uuid4()
    with Session(source_session.get_bind()) as session, session.begin():
        instant = _clock(session, settings, now)
        lease_expires = instant + timedelta(
            seconds=settings.assistant_workflow_timeout_seconds + 15
        )
        insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
        session.execute(
            insert(AssistantRequest)
            .values(
                id=uuid4(),
                user_id=user_id,
                idempotency_key=payload.idempotency_key,
                payload_hash=fingerprint,
                first_request_id=request_id,
                attempt_id=attempt_id,
                state="running",
                mutation_status="none",
                started_at=instant,
                lease_expires_at=lease_expires,
                finished_at=None,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "idempotency_key"])
        )
        record = session.scalars(
            select(AssistantRequest)
            .where(
                AssistantRequest.user_id == user_id,
                AssistantRequest.idempotency_key == payload.idempotency_key,
            )
            .with_for_update()
        ).one()
        if record.attempt_id != attempt_id:
            _check_record(record, fingerprint, instant)
            record.attempt_id = attempt_id
            record.state = "running"
            record.lease_expires_at = lease_expires
            record.finished_at = None
        guard.record_id = record.id
        guard.attempt_id = attempt_id
    return guard
