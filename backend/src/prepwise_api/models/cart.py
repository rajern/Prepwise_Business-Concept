from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prepwise_api.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from prepwise_api.models.catalog import Meal
    from prepwise_api.models.user import User


class CartItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "meal_id"),
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

    user: Mapped[User] = relationship(back_populates="cart_items")
    meal: Mapped[Meal] = relationship(back_populates="cart_items")
