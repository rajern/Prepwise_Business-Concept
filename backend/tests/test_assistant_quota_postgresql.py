"""Real row-lock tests; use only an explicitly configured disposable PostgreSQL DB."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Table, create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from prepwise_api.config import Settings
from prepwise_api.models import AssistantQuotaLock, AssistantUsageEvent, User
from prepwise_api.services.assistant_quota import (
    AssistantQuotaExceeded,
    reserve_assistant_request,
)


@pytest.fixture
def postgres_quota() -> Iterator[tuple[Engine, list[UUID]]]:
    database_url = os.environ.get("PREPWISE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set PREPWISE_TEST_DATABASE_URL to a disposable local/CI PostgreSQL DB")
    schema = "ai_quota_test_" + uuid4().hex
    base_engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    with base_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = base_engine.execution_options(schema_translate_map={None: schema})
    cast(Table, User.__table__).create(engine, checkfirst=True)
    cast(Table, AssistantQuotaLock.__table__).create(engine)
    cast(Table, AssistantUsageEvent.__table__).create(engine)
    with Session(engine) as session:
        users = [
            User(external_subject=f"pg-quota-{index}", email=f"pg-quota-{index}@example.com")
            for index in range(4)
        ]
        session.add_all(users)
        session.commit()
        ids = [user.id for user in users]
    try:
        yield engine, ids
    finally:
        # Exact generated test schema only; never drop or truncate public tables.
        assert schema.startswith("ai_quota_test_") and len(schema) == 46
        with base_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base_engine.dispose()


def test_parallel_same_user_admits_exactly_one_request(
    postgres_quota: tuple[Engine, list[UUID]],
) -> None:
    engine, users = postgres_quota
    barrier = Barrier(6)

    def admit(_: int) -> bool:
        with Session(engine) as session:
            barrier.wait()
            try:
                reserve_assistant_request(session, users[0], Settings(app_env="production"))
            except AssistantQuotaExceeded:
                return False
            return True

    with ThreadPoolExecutor(max_workers=6) as pool:
        accepted = list(pool.map(admit, range(6)))
    assert sum(accepted) == 1
    # A subsequent independent session cannot bypass the persisted lease.
    with Session(engine) as restarted_worker, pytest.raises(AssistantQuotaExceeded):
        reserve_assistant_request(restarted_worker, users[0], Settings(app_env="production"))


def test_parallel_global_final_slot_cannot_be_overspent(
    postgres_quota: tuple[Engine, list[UUID]],
) -> None:
    engine, users = postgres_quota
    # Noon avoids a test crossing the Oslo day boundary during fixture setup.
    now = datetime(2026, 9, 30, 10, tzinfo=UTC)
    with Session(engine) as session:
        session.add_all(
            [
                AssistantUsageEvent(
                    user_id=users[index % 4],
                    started_at=now - timedelta(minutes=11),
                    lease_expires_at=now - timedelta(minutes=10),
                    released_at=now - timedelta(minutes=10),
                )
                for index in range(99)
            ]
        )
        session.commit()
    barrier = Barrier(4)

    def admit(user_id: UUID) -> bool:
        with Session(engine) as session:
            barrier.wait()
            try:
                reserve_assistant_request(session, user_id, Settings(app_env="production"), now=now)
            except AssistantQuotaExceeded:
                return False
            return True

    with ThreadPoolExecutor(max_workers=4) as pool:
        accepted = list(pool.map(admit, users))
    assert sum(accepted) == 1
    with Session(engine) as restarted_worker:
        assert restarted_worker.scalar(select(func.count()).select_from(AssistantUsageEvent)) == 100
        with pytest.raises(AssistantQuotaExceeded):
            reserve_assistant_request(
                restarted_worker, users[0], Settings(app_env="production"), now=now
            )
