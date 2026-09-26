from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from prepwise_api.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class OrderConfirmation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One-use server-side authorization for a later assistant order request."""

    __tablename__ = "order_confirmations"
    __table_args__ = (Index("ix_order_confirmations_user_created_at", "user_id", "created_at"),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    pickup_location_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("pickup_locations.id", ondelete="CASCADE"),
    )
    cart_fingerprint: Mapped[str] = mapped_column(String(64))
    issued_request_id: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
