from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, SmallInteger, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prepwise_api.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from prepwise_api.models.catalog import Meal
    from prepwise_api.models.user import User


class CartGroup(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_groups"
    __table_args__ = (
        CheckConstraint(
            "(pickup_date IS NULL) = (pickup_slot IS NULL)", name="pickup_selection_paired"
        ),
        CheckConstraint(
            "pickup_slot IS NULL OR pickup_slot IN ('16-18', '18-20')", name="pickup_slot_valid"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    pickup_location_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("pickup_locations.id", ondelete="RESTRICT")
    )
    pickup_date: Mapped[date | None] = mapped_column(Date)
    pickup_slot: Mapped[str | None] = mapped_column(String(5))


class CartItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        Index(
            "uq_cart_items_group_meal",
            "user_id",
            "group_id",
            "meal_id",
            unique=True,
            postgresql_where=text("group_id IS NOT NULL"),
            sqlite_where=text("group_id IS NOT NULL"),
        ),
        Index(
            "uq_cart_items_unassigned_meal",
            "user_id",
            "meal_id",
            unique=True,
            postgresql_where=text("group_id IS NULL"),
            sqlite_where=text("group_id IS NULL"),
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("quantity <= 99", name="quantity_reasonable"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    meal_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("meals.id", ondelete="RESTRICT"),
    )
    quantity: Mapped[int] = mapped_column(SmallInteger)
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("cart_groups.id", ondelete="RESTRICT"), index=True
    )

    user: Mapped[User] = relationship(back_populates="cart_items")
    meal: Mapped[Meal] = relationship(back_populates="cart_items")
