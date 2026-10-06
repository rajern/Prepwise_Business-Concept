"""Replay-safety row locks verified only in isolated disposable local schemas."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Table, create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from prepwise_api.config import Settings
from prepwise_api.models import Base, User
from prepwise_api.models.assistant_request import AssistantRequest
from prepwise_api.schemas.assistant import AssistantMessageRequest
from prepwise_api.services.assistant_requests import (
    AssistantRequestConflict,
    admit_assistant_request,
)


@pytest.fixture
def request_database() -> Iterator[tuple[Engine, UUID]]:
    value = os.environ.get("PREPWISE_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set PREPWISE_TEST_DATABASE_URL for local PostgreSQL request-safety tests")
    url = make_url(value)
    assert url.host in {"127.0.0.1", "localhost"} and url.drivername.startswith("postgresql")
    assert url.database and url.database.endswith(("_test", "_ci"))
    schema = "assistant_request_test_" + uuid4().hex
    base_engine = create_engine(url, connect_args={"connect_timeout": 5})
    with base_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = base_engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(
        engine, tables=[cast(Table, User.__table__), cast(Table, AssistantRequest.__table__)]
    )
    with Session(engine) as session:
        user = User(external_subject="request-concurrency-customer")
        session.add(user)
        session.commit()
        user_id = user.id
    try:
        yield engine, user_id
    finally:
        assert schema.startswith("assistant_request_test_") and len(schema) == 55
        with base_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base_engine.dispose()


def test_parallel_key_admission_has_exactly_one_owner(
    request_database: tuple[Engine, UUID],
) -> None:
    engine, user_id = request_database
    payload = AssistantMessageRequest(message="Show meals", idempotency_key=uuid4())
    barrier = Barrier(6)

    def admit(index: int) -> bool:
        with Session(engine) as session:
            barrier.wait()
            try:
                admit_assistant_request(
                    session, user_id, payload, Settings(app_env="production"), f"concurrent-{index}"
                )
            except AssistantRequestConflict as conflict:
                assert conflict.code == "request_in_progress"
                return False
            return True

    with ThreadPoolExecutor(max_workers=6) as pool:
        accepted = list(pool.map(admit, range(6)))
    assert sum(accepted) == 1
    with Session(engine) as restarted:
        assert restarted.scalar(select(func.count()).select_from(AssistantRequest)) == 1


def test_read_only_failure_can_retry_but_expired_attempt_cannot_write(
    request_database: tuple[Engine, UUID],
) -> None:
    engine, user_id = request_database
    settings = Settings(app_env="production")
    payload = AssistantMessageRequest(message="Show meals", idempotency_key=uuid4())
    with Session(engine) as source:
        first = admit_assistant_request(source, user_id, payload, settings, "failed-read")
        first.finish(succeeded=False)
        old = admit_assistant_request(source, user_id, payload, settings, "retry-read")
        assert old.attempt_id != first.attempt_id and old.metadata()["retry_safe"] is True
        with Session(engine) as expire, expire.begin():
            record = expire.scalar(select(AssistantRequest))
            assert record is not None
            record.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        fresh = admit_assistant_request(source, user_id, payload, settings, "fresh-read")
        with pytest.raises(AssistantRequestConflict):
            old.observe_mutation("unknown")
        old.finish(succeeded=False)
        with Session(engine) as reader:
            current = reader.scalar(select(AssistantRequest))
            assert current is not None and current.attempt_id == fresh.attempt_id
            assert current.state == "running" and current.mutation_status == "none"


def test_completed_read_only_key_is_rejected_after_worker_restart(
    request_database: tuple[Engine, UUID],
) -> None:
    engine, user_id = request_database
    settings = Settings(app_env="production")
    payload = AssistantMessageRequest(message="Show meals", idempotency_key=uuid4())
    with Session(engine) as source:
        guard = admit_assistant_request(source, user_id, payload, settings, "completed-read")
        guard.finish(succeeded=True)
    with Session(engine) as restarted, pytest.raises(AssistantRequestConflict) as duplicate:
        admit_assistant_request(restarted, user_id, payload, settings, "duplicate")
    assert duplicate.value.code == "assistant_request_completed"
    assert duplicate.value.mutation_status == "none"


@pytest.mark.parametrize("mutation", ["unknown", "applied"])
def test_mutation_marker_survives_tool_rollback_and_worker_restart(
    request_database: tuple[Engine, UUID],
    mutation: str,
) -> None:
    engine, user_id = request_database
    settings = Settings(app_env="production")
    payload = AssistantMessageRequest(message="Add two meals", idempotency_key=uuid4())
    with Session(engine) as source:
        guard = admit_assistant_request(source, user_id, payload, settings, "mutation-owner")
        source.scalar(select(User).where(User.id == user_id))  # Tool's independent transaction.
        guard.observe_mutation("unknown")
        if mutation == "applied":
            guard.observe_mutation("applied")
            guard.observe_mutation("unknown")
        source.rollback()
        guard.finish(succeeded=mutation == "applied")
    with Session(engine) as restarted:
        with pytest.raises(AssistantRequestConflict) as duplicate:
            admit_assistant_request(restarted, user_id, payload, settings, "retry")
        assert duplicate.value.code == (
            "assistant_request_already_applied"
            if mutation == "applied"
            else "assistant_outcome_unknown"
        )
        assert duplicate.value.mutation_status == mutation
        row = restarted.scalar(select(AssistantRequest))
        assert row is not None and row.mutation_status == mutation
