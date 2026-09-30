from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from prepwise_api.models.base import Base, UuidPrimaryKeyMixin


class AssistantQuotaLock(Base):
    """A short-lived transaction lock serializes admissions across API workers."""

    __tablename__ = "assistant_quota_lock"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class AssistantUsageEvent(UuidPrimaryKeyMixin, Base):
    """Usage metadata only; no prompt, reply, token or tool content."""

    __tablename__ = "assistant_usage_events"
    __table_args__ = (
        Index("ix_assistant_usage_user_started", "user_id", "started_at"),
        Index("ix_assistant_usage_started", "started_at"),
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
