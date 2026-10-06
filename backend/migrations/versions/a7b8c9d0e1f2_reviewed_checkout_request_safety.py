"""Add owner-scoped checkout keys and content-free assistant replay guards."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("checkout_request_key", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("checkout_request_hash", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_orders_user_checkout_request", "orders", ["user_id", "checkout_request_key"]
    )
    op.create_check_constraint(
        "checkout_request_pair",
        "orders",
        "(checkout_request_key IS NULL AND checkout_request_hash IS NULL) OR "
        "(checkout_request_key IS NOT NULL AND checkout_request_hash IS NOT NULL)",
    )
    op.create_table(
        "assistant_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("first_request_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("mutation_status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_assistant_requests_user_key"),
        sa.CheckConstraint("state IN ('running', 'completed', 'failed')", name="state"),
        sa.CheckConstraint(
            "mutation_status IN ('none', 'unknown', 'applied')", name="mutation_status"
        ),
    )
    op.create_index(
        "ix_assistant_requests_user_started", "assistant_requests", ["user_id", "started_at"]
    )


def downgrade() -> None:
    # Losing replay receipts can repeat a committed order/cart mutation. Never
    # discard live safety metadata to make an incompatible old build start.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM assistant_requests) OR EXISTS "
        "(SELECT 1 FROM orders WHERE checkout_request_key IS NOT NULL) THEN RAISE EXCEPTION "
        "'Replay-safety receipts exist; reviewed compatible recovery required'; END IF; END $$"
    )
    op.drop_index("ix_assistant_requests_user_started", "assistant_requests")
    op.drop_table("assistant_requests")
    op.drop_constraint(op.f("ck_orders_checkout_request_pair"), "orders", type_="check")
    op.drop_constraint("uq_orders_user_checkout_request", "orders", type_="unique")
    op.drop_column("orders", "checkout_request_hash")
    op.drop_column("orders", "checkout_request_key")
