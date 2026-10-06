"""Offline replay protection tests: no provider traffic or chat persistence."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.config import Settings
from prepwise_api.models import Base, User
from prepwise_api.models.assistant_request import AssistantRequest
from prepwise_api.schemas.assistant import AssistantMessageRequest
from prepwise_api.services.assistant_requests import (
    AssistantRequestConflict,
    admit_assistant_request,
)


@pytest.fixture
def request_session() -> Iterator[tuple[Session, User]]:
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(external_subject="synthetic-request-user")
        session.add(user)
        session.commit()
        yield session, user
    engine.dispose()


def test_key_payload_binding_and_concurrent_admission(
    request_session: tuple[Session, User],
) -> None:
    session, user = request_session
    payload = AssistantMessageRequest(message="Add two meals", idempotency_key=uuid4())
    settings = Settings(app_env="test")
    guard = admit_assistant_request(session, user.id, payload, settings, "first")
    with pytest.raises(AssistantRequestConflict) as ongoing:
        admit_assistant_request(session, user.id, payload, settings, "second")
    assert ongoing.value.code == "request_in_progress"
    assert ongoing.value.retry_after is not None
    assert ongoing.value.request_id == "first"
    with pytest.raises(AssistantRequestConflict) as changed:
        admit_assistant_request(
            session,
            user.id,
            payload.model_copy(update={"message": "Different message"}),
            settings,
            "third",
        )
    assert changed.value.code == "assistant_request_conflict"
    guard.finish(succeeded=False)
    retry = admit_assistant_request(session, user.id, payload, settings, "safe-retry")
    assert retry.attempt_id != guard.attempt_id
    assert retry.metadata()["retry_safe"] is True


@pytest.mark.parametrize("succeeded", [False, True])
@pytest.mark.parametrize("mutation", ["unknown", "applied"])
def test_mutation_marker_survives_rollback_and_prevents_replay(
    request_session: tuple[Session, User],
    mutation: str,
    succeeded: bool,
) -> None:
    session, user = request_session
    payload = AssistantMessageRequest(message="Add two meals", idempotency_key=uuid4())
    settings = Settings(app_env="test")
    guard = admit_assistant_request(session, user.id, payload, settings, "first")
    guard.observe_mutation("unknown")
    if mutation == "applied":
        guard.observe_mutation("applied")
        guard.observe_mutation("unknown")  # Failed later step never hides an applied write.
    session.rollback()
    guard.finish(succeeded=succeeded)
    with pytest.raises(AssistantRequestConflict) as duplicate:
        admit_assistant_request(session, user.id, payload, settings, "retry")
    assert duplicate.value.code == (
        "assistant_request_already_applied"
        if succeeded and mutation == "applied"
        else "assistant_outcome_unknown"
    )
    assert duplicate.value.mutation_status == mutation
    assert guard.metadata()["retry_safe"] is False
    record = session.scalar(select(AssistantRequest))
    assert record is not None and record.mutation_status == mutation
    columns = set(AssistantRequest.__table__.columns.keys())
    assert not columns.intersection({"message", "history", "reply", "tool_arguments"})
    assert record.payload_hash != payload.message and len(record.payload_hash) == 64


def test_expired_read_only_attempt_is_fenced_from_future_writes(
    request_session: tuple[Session, User],
) -> None:
    session, user = request_session
    payload = AssistantMessageRequest(message="Show meals", idempotency_key=uuid4())
    settings = Settings(app_env="test")
    old = admit_assistant_request(
        session, user.id, payload, settings, "old", now=datetime.now(UTC) - timedelta(minutes=2)
    )
    fresh = admit_assistant_request(session, user.id, payload, settings, "fresh")
    with pytest.raises(AssistantRequestConflict):
        old.observe_mutation("unknown")
    old.finish(succeeded=False)
    record = session.scalar(select(AssistantRequest))
    assert record is not None and record.attempt_id == fresh.attempt_id
    assert record.state == "running" and record.mutation_status == "none"


def test_same_key_is_scoped_to_its_customer(request_session: tuple[Session, User]) -> None:
    session, user = request_session
    other = User(external_subject="other-request-user")
    session.add(other)
    session.commit()
    payload = AssistantMessageRequest(message="Show meals", idempotency_key=uuid4())
    settings = Settings(app_env="test")
    first = admit_assistant_request(session, user.id, payload, settings, "one")
    second = admit_assistant_request(session, other.id, payload, settings, "two")
    assert first.record_id != second.record_id


def test_successful_read_only_request_is_not_reexecuted(
    request_session: tuple[Session, User],
) -> None:
    session, user = request_session
    payload = AssistantMessageRequest(message="Show meals", idempotency_key=uuid4())
    settings = Settings(app_env="test")
    guard = admit_assistant_request(session, user.id, payload, settings, "completed-read")
    guard.finish(succeeded=True)
    with pytest.raises(AssistantRequestConflict) as duplicate:
        admit_assistant_request(session, user.id, payload, settings, "duplicate")
    assert duplicate.value.code == "assistant_request_completed"
    assert duplicate.value.mutation_status == "none"
