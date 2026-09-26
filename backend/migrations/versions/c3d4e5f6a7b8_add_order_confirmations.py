"""add order confirmations

Revision ID: c3d4e5f6a7b8
Revises: f7b7f40b50a1
Create Date: 2026-09-26 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "f7b7f40b50a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store one-use confirmations for assistant-created orders."""
    op.create_table(
        "order_confirmations",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("pickup_location_id", sa.Uuid(), nullable=False),
        sa.Column("cart_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("issued_request_id", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pickup_location_id"],
            ["pickup_locations.id"],
            name=op.f("fk_order_confirmations_pickup_location_id_pickup_locations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_order_confirmations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_confirmations")),
    )
    op.create_index(
        "ix_order_confirmations_user_created_at",
        "order_confirmations",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove assistant order confirmations."""
    op.drop_index("ix_order_confirmations_user_created_at", table_name="order_confirmations")
    op.drop_table("order_confirmations")
