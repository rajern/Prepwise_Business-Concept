from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prepwise_api.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from prepwise_api.models.enums import OrderStatus

if TYPE_CHECKING:
    from prepwise_api.models.catalog import Meal, PickupLocation
    from prepwise_api.models.user import User


class Order(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_nok >= 0", name="total_non_negative"),
        CheckConstraint("pickup_end_at > pickup_start_at", name="pickup_window_valid"),
        Index("ix_orders_user_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    pickup_location_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("pickup_locations.id", ondelete="RESTRICT"),
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            name="order_status",
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        default=OrderStatus.RECEIVED,
        server_default=OrderStatus.RECEIVED.value,
        index=True,
    )
    pickup_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pickup_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pickup_location_name: Mapped[str] = mapped_column(String(200))
    pickup_location_address: Mapped[str] = mapped_column(String(400))
    total_nok: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    user: Mapped[User] = relationship(back_populates="orders")
    pickup_location: Mapped[PickupLocation] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrderItem(UuidPrimaryKeyMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "meal_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_nok >= 0", name="unit_price_non_negative"),
    )

    order_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
    )
    meal_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("meals.id", ondelete="RESTRICT"),
    )
    meal_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(SmallInteger)
    unit_price_nok: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    meal: Mapped[Meal] = relationship(back_populates="order_items")
