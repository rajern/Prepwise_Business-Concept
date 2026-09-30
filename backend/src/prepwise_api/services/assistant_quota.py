"""Atomic, durable AI admission limits shared by all API processes."""

import logging
import math
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from prepwise_api.config import Settings
from prepwise_api.models.assistant_usage import AssistantQuotaLock, AssistantUsageEvent

_OSLO = ZoneInfo("Europe/Oslo")
_logger = logging.getLogger("prepwise.ai.quota")


class AssistantQuotaExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def reserve_assistant_request(
    source_session: Session,
    user_id: UUID,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> UUID:
    """Commit admission before any paid call; failures still count toward quotas.

    The lock covers counts AND insertion in one transaction. PostgreSQL FOR UPDATE
    protects independent workers. SQLite is supported only for sequential unit tests.
    Independent sessions prevent application writes from releasing the quota lock.
    """
    with Session(source_session.get_bind()) as session, session.begin():
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            session.execute(text("SET LOCAL lock_timeout = '2000ms'"))
            session.execute(text("SET LOCAL statement_timeout = '2000ms'"))
            session.execute(pg_insert(AssistantQuotaLock).values(id=1).on_conflict_do_nothing())
            session.execute(
                select(AssistantQuotaLock)
                .where(
                    AssistantQuotaLock.id == 1,
                )
                .with_for_update()
            ).scalar_one()
            # Database time prevents clock drift between API workers.
            clock = now or session.scalar(select(func.clock_timestamp()))
            if not isinstance(clock, datetime):
                raise RuntimeError("Unable to resolve database clock")
            instant = _utc(clock)
        elif dialect == "sqlite" and settings.app_env != "production":
            session.execute(sqlite_insert(AssistantQuotaLock).values(id=1).on_conflict_do_nothing())
            instant = _utc(now or datetime.now(UTC))
        else:
            raise RuntimeError("The production AI limiter requires PostgreSQL")

        local_day = instant.astimezone(_OSLO).date()
        day_start = datetime.combine(local_day, time.min, _OSLO).astimezone(UTC)
        next_day = datetime.combine(local_day + timedelta(days=1), time.min, _OSLO).astimezone(UTC)
        window_start = instant - timedelta(minutes=10)
        session.execute(
            delete(AssistantUsageEvent).where(
                AssistantUsageEvent.started_at < day_start - timedelta(days=2),
            )
        )
        events = list(
            session.scalars(
                select(AssistantUsageEvent).where(
                    AssistantUsageEvent.started_at >= min(day_start, window_start),
                )
            )
        )
        user_events = [event for event in events if event.user_id == user_id]
        daily = [event for event in events if _utc(event.started_at) >= day_start]
        recent = [event for event in user_events if _utc(event.started_at) > window_start]
        retry_until: list[datetime] = []
        if len(daily) >= settings.assistant_messages_per_day:
            retry_until.append(next_day)
        if (
            sum(event.user_id == user_id for event in daily)
            >= settings.assistant_messages_per_user_day
        ):
            retry_until.append(next_day)
        if len(recent) >= settings.assistant_messages_per_10_minutes:
            retry_until.append(
                min(_utc(event.started_at) for event in recent) + timedelta(minutes=10)
            )
        active = [
            event
            for event in user_events
            if event.released_at is None and _utc(event.lease_expires_at) > instant
        ]
        if active:
            retry_until.append(max(_utc(event.lease_expires_at) for event in active))
        if retry_until:
            raise AssistantQuotaExceeded(math.ceil((max(retry_until) - instant).total_seconds()))
        event = AssistantUsageEvent(
            user_id=user_id,
            started_at=instant,
            # Grace beyond the hard workflow deadline avoids a cancellation/release race.
            lease_expires_at=instant
            + timedelta(seconds=settings.assistant_workflow_timeout_seconds + 15),
        )
        session.add(event)
        session.flush()
        return event.id


def release_assistant_request(source_session: Session, event_id: UUID) -> None:
    """Best-effort release; on failure the durable lease expires conservatively."""
    try:
        with Session(source_session.get_bind()) as session, session.begin():
            session.execute(
                update(AssistantUsageEvent)
                .where(
                    AssistantUsageEvent.id == event_id,
                )
                .values(released_at=datetime.now(UTC))
            )
    except SQLAlchemyError:
        _logger.warning("AI lease release failed", extra={"event": "ai.quota.release_failed"})
