from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pytest import CaptureFixture

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"


def alembic_config() -> Config:
    return Config(ALEMBIC_INI)


def test_migration_history_has_one_linear_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())
    heads = scripts.get_heads()

    assert len(heads) == 1
    head = scripts.get_revision(heads[0])
    assert head is not None
    assert head.revision == "a7b8c9d0e1f2"
    assert head.down_revision == "f6a7b8c9d0e1"


def test_initial_migration_renders_postgresql_sql(
    capsys: CaptureFixture[str],
) -> None:
    command.upgrade(alembic_config(), "head", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE orders" in sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "CREATE TABLE knowledge_chunks" in sql
    assert "CREATE TABLE order_confirmations" in sql
    assert "CREATE TABLE assistant_quota_lock" in sql
    assert "CREATE TABLE assistant_usage_events" in sql
    assert "CREATE TABLE cart_groups" in sql
    assert "CREATE TABLE assistant_requests" in sql
    assert "uq_assistant_requests_user_key" in sql
    assert "uq_orders_user_checkout_request" in sql
    assert "ck_orders_checkout_request_pair" in sql
    assert "ADD VALUE IF NOT EXISTS 'cancelled'" in sql
    assert "uq_cart_items_unassigned_meal" in sql
    assert "vector(1536)" in sql.lower()
    assert "CREATE TYPE user_role" in sql
