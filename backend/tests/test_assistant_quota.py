from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.config import Settings
from prepwise_api.models import AssistantUsageEvent, Base, User
from prepwise_api.services.assistant_quota import (
    AssistantQuotaExceeded,
    release_assistant_request,
    reserve_assistant_request,
)


@pytest.fixture
def quota_db() -> Iterator[tuple[Engine, list[UUID]]]:
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users = [
            User(external_subject=f"quota-{index}", email=f"quota-{index}@example.com")
            for index in range(4)
        ]
        session.add_all(users)
        session.commit()
        ids = [user.id for user in users]
    try:
        yield engine, ids
    finally:
        engine.dispose()


def test_sliding_limit_is_durable_and_recovers_at_window_boundary(
    quota_db: tuple[Engine, list[UUID]],
) -> None:
    engine, users = quota_db
    start = datetime(2026, 9, 30, 8, tzinfo=UTC)
    for index in range(15):
        with Session(engine) as session:
            event = reserve_assistant_request(
                session, users[0], Settings(), now=start + timedelta(seconds=index)
            )
            release_assistant_request(session, event)
    with Session(engine) as session:
        with pytest.raises(AssistantQuotaExceeded) as rejected:
            reserve_assistant_request(
                session, users[0], Settings(), now=start + timedelta(seconds=15)
            )
        assert rejected.value.retry_after == 585
        reserve_assistant_request(session, users[0], Settings(), now=start + timedelta(minutes=10))
        assert session.scalar(select(func.count()).select_from(AssistantUsageEvent)) == 16


def test_one_active_request_and_crash_lease_expiry(
    quota_db: tuple[Engine, list[UUID]],
) -> None:
    engine, users = quota_db
    start = datetime(2026, 9, 30, 8, tzinfo=UTC)
    with Session(engine) as session:
        reserve_assistant_request(session, users[0], Settings(), now=start)
    with Session(engine) as restarted_process:
        with pytest.raises(AssistantQuotaExceeded) as rejected:
            reserve_assistant_request(restarted_process, users[0], Settings(), now=start)
        assert rejected.value.retry_after == 60
        reserve_assistant_request(
            restarted_process, users[0], Settings(), now=start + timedelta(seconds=60)
        )


@pytest.mark.parametrize(
    "start",
    [
        datetime(2026, 9, 30, 21, 40, tzinfo=UTC),
        datetime(2026, 10, 25, 22, 40, tzinfo=UTC),
    ],
)
def test_user_daily_limit_resets_at_oslo_midnight_including_dst(
    quota_db: tuple[Engine, list[UUID]],
    start: datetime,
) -> None:
    engine, users = quota_db
    with Session(engine) as session:
        for index in range(45):
            instant = start - timedelta(minutes=(44 - index) * 11)
            event = reserve_assistant_request(session, users[0], Settings(), now=instant)
            release_assistant_request(session, event)
        with pytest.raises(AssistantQuotaExceeded) as rejected:
            reserve_assistant_request(session, users[0], Settings(), now=start)
        assert rejected.value.retry_after == 1200
        reserve_assistant_request(session, users[0], Settings(), now=start + timedelta(minutes=20))


def test_global_quota_shared_between_users_and_failures(
    quota_db: tuple[Engine, list[UUID]],
) -> None:
    engine, users = quota_db
    start = datetime(2026, 9, 30, 8, tzinfo=UTC)
    with Session(engine) as session:
        for index in range(100):
            event = reserve_assistant_request(
                session, users[index % 4], Settings(), now=start + timedelta(minutes=index)
            )
            # Releasing an unsuccessful request does not refund its count.
            release_assistant_request(session, event)
        with pytest.raises(AssistantQuotaExceeded):
            reserve_assistant_request(
                session, users[0], Settings(), now=start + timedelta(minutes=100)
            )
        assert session.scalar(select(func.count()).select_from(AssistantUsageEvent)) == 100


def test_production_refuses_non_postgresql_limiter(quota_db: tuple[Engine, list[UUID]]) -> None:
    engine, users = quota_db
    with Session(engine) as session, pytest.raises(RuntimeError, match="requires PostgreSQL"):
        reserve_assistant_request(session, users[0], Settings(app_env="production"))


def test_rolling_window_continues_across_daily_reset(
    quota_db: tuple[Engine, list[UUID]],
) -> None:
    engine, users = quota_db
    start = datetime(2026, 9, 30, 21, 59, tzinfo=UTC)  # 23:59 Oslo
    with Session(engine) as session:
        for index in range(15):
            event = reserve_assistant_request(
                session, users[0], Settings(), now=start + timedelta(seconds=index)
            )
            release_assistant_request(session, event)
        with pytest.raises(AssistantQuotaExceeded) as rejected:
            reserve_assistant_request(
                session, users[0], Settings(), now=start + timedelta(minutes=1)
            )
        assert rejected.value.retry_after == 540
