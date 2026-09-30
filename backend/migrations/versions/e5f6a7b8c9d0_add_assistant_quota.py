"""Add durable assistant usage admission and leases."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("assistant_quota_lock", sa.Column("id", sa.Integer(), primary_key=True))
    op.bulk_insert(sa.table("assistant_quota_lock", sa.column("id", sa.Integer())), [{"id": 1}])
    op.create_table(
        "assistant_usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_assistant_usage_user_started", "assistant_usage_events", ["user_id", "started_at"]
    )
    op.create_index("ix_assistant_usage_started", "assistant_usage_events", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_assistant_usage_started", "assistant_usage_events")
    op.drop_index("ix_assistant_usage_user_started", "assistant_usage_events")
    op.drop_table("assistant_usage_events")
    op.drop_table("assistant_quota_lock")
