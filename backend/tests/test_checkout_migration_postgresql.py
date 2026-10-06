"""Exercise the additive receipt migration only in a disposable local schema."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import String, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from prepwise_api.models import Base


def test_review_receipt_migration_and_fail_closed_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = os.environ.get("PREPWISE_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set PREPWISE_TEST_DATABASE_URL for disposable PostgreSQL migration checks")
    url = make_url(value)
    assert url.drivername.startswith("postgresql")
    assert url.host in {"localhost", "127.0.0.1"}
    assert url.database and url.database.endswith(("_test", "_ci"))
    schema = f"checkout_migration_test_{uuid4().hex}"
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    migration = (
        Path(__file__).parents[1]
        / "migrations/versions/a7b8c9d0e1f2_reviewed_checkout_request_safety.py"
    )
    spec = importlib.util.spec_from_file_location("receipt_migration", migration)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            # Only predecessor columns needed by this additive revision; not business data.
            connection.execute(text("CREATE TABLE users (id uuid PRIMARY KEY)"))
            connection.execute(
                text("CREATE TABLE orders (id uuid PRIMARY KEY, user_id uuid REFERENCES users(id))")
            )
            operations = Operations(
                MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
            )
            monkeypatch.setattr(module, "op", operations)
            module.upgrade()
            inspector = inspect(connection)
            actual = {
                column["name"]: column for column in inspector.get_columns("assistant_requests")
            }
            assert set(actual) == set(Base.metadata.tables["assistant_requests"].columns.keys())
            reference_type = actual["first_request_id"]["type"]
            hash_type = actual["payload_hash"]["type"]
            assert isinstance(reference_type, String) and reference_type.length == 128
            assert isinstance(hash_type, String) and hash_type.length == 64
            assert actual["finished_at"]["nullable"]
            assert not actual["mutation_status"]["nullable"]
            assert "uq_orders_user_checkout_request" in {
                constraint["name"] for constraint in inspector.get_unique_constraints("orders")
            }
            assert "ck_orders_checkout_request_pair" in {
                constraint["name"] for constraint in inspector.get_check_constraints("orders")
            }
            user_id, order_id, request_id = uuid4(), uuid4(), uuid4()
            connection.execute(text("INSERT INTO users (id) VALUES (:id)"), {"id": user_id})
            connection.execute(
                text(
                    "INSERT INTO assistant_requests (id, user_id, idempotency_key, payload_hash, "
                    "first_request_id, attempt_id, state, mutation_status, "
                    "started_at, lease_expires_at) "
                    "VALUES (:id, :user_id, :key, :hash, 'local-test', :attempt, "
                    "'failed', 'unknown', "
                    "now(), now())"
                ),
                {
                    "id": request_id,
                    "user_id": user_id,
                    "key": uuid4(),
                    "hash": "0" * 64,
                    "attempt": uuid4(),
                },
            )
            with (
                pytest.raises(DBAPIError, match="Replay-safety receipts exist"),
                connection.begin_nested(),
            ):
                module.downgrade()
            connection.execute(
                text("DELETE FROM assistant_requests WHERE id = :id"), {"id": request_id}
            )
            connection.execute(
                text(
                    "INSERT INTO orders (id, user_id, checkout_request_key, checkout_request_hash) "
                    "VALUES (:id, :user_id, :key, :hash)"
                ),
                {"id": order_id, "user_id": user_id, "key": uuid4(), "hash": "1" * 64},
            )
            with (
                pytest.raises(DBAPIError, match="Replay-safety receipts exist"),
                connection.begin_nested(),
            ):
                module.downgrade()
            connection.execute(text("DELETE FROM orders WHERE id = :id"), {"id": order_id})
            module.downgrade()
            assert "assistant_requests" not in inspect(connection).get_table_names()
            assert "checkout_request_key" not in {
                column["name"] for column in inspect(connection).get_columns("orders")
            }
            # Roll back the entire private schema, including fixture DDL. No shared DB writes.
            connection.rollback()
    finally:
        engine.dispose()
