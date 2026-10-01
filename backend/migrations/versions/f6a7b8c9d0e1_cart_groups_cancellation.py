"""Add persistent pickup groups and a terminal cancellation status."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL commits enum additions before they can be used by transactions.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.create_table(
        "cart_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "pickup_location_id",
            sa.Uuid(),
            sa.ForeignKey("pickup_locations.id", ondelete="RESTRICT"),
        ),
        sa.Column("pickup_date", sa.Date()),
        sa.Column("pickup_slot", sa.String(5)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(pickup_date IS NULL) = (pickup_slot IS NULL)", name="pickup_selection_paired"
        ),
        sa.CheckConstraint(
            "pickup_slot IS NULL OR pickup_slot IN ('16-18', '18-20')", name="pickup_slot_valid"
        ),
    )
    op.create_index("ix_cart_groups_user_id", "cart_groups", ["user_id"])
    op.add_column("cart_items", sa.Column("group_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_cart_items_group_id_cart_groups",
        "cart_items",
        "cart_groups",
        ["group_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_cart_items_group_id", "cart_items", ["group_id"])
    op.drop_constraint("uq_cart_items_user_id", "cart_items", type_="unique")
    op.create_index(
        "uq_cart_items_group_meal",
        "cart_items",
        ["user_id", "group_id", "meal_id"],
        unique=True,
        postgresql_where=sa.text("group_id IS NOT NULL"),
    )
    op.create_index(
        "uq_cart_items_unassigned_meal",
        "cart_items",
        ["user_id", "meal_id"],
        unique=True,
        postgresql_where=sa.text("group_id IS NULL"),
    )


def downgrade() -> None:
    # Do not silently destroy pickup choices or collapse duplicate meal lines.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM cart_groups) OR EXISTS "
        "(SELECT 1 FROM orders WHERE status = 'cancelled') THEN RAISE EXCEPTION "
        "'Cart groups/cancelled orders exist; reviewed recovery plan required'; END IF; END $$"
    )
    op.drop_index("uq_cart_items_unassigned_meal", "cart_items")
    op.drop_index("uq_cart_items_group_meal", "cart_items")
    op.create_unique_constraint("uq_cart_items_user_id", "cart_items", ["user_id", "meal_id"])
    op.drop_index("ix_cart_items_group_id", "cart_items")
    op.drop_constraint("fk_cart_items_group_id_cart_groups", "cart_items", type_="foreignkey")
    op.drop_column("cart_items", "group_id")
    op.drop_index("ix_cart_groups_user_id", "cart_groups")
    op.drop_table("cart_groups")
    # PostgreSQL enum additions remain: removing one requires a type/data rewrite.
