from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prepwise_api.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from prepwise_api.models.enums import UserRole

if TYPE_CHECKING:
    from prepwise_api.models.cart import CartItem
    from prepwise_api.models.order import Order


class User(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    external_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        default=UserRole.CUSTOMER,
        server_default=UserRole.CUSTOMER.value,
    )

    cart_items: Mapped[list[CartItem]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    orders: Mapped[list[Order]] = relationship(back_populates="user")
