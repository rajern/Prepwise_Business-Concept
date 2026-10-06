"""Durable AI replay-safety metadata; never customer conversation content."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from prepwise_api.models.base import Base, UuidPrimaryKeyMixin


class AssistantRequest(UuidPrimaryKeyMixin, Base):
    __tablename__ = "assistant_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_assistant_requests_user_key"),
        CheckConstraint("state IN ('running', 'completed', 'failed')", name="state"),
        CheckConstraint(
            "mutation_status IN ('none', 'unknown', 'applied')", name="mutation_status"
        ),
        Index("ix_assistant_requests_user_started", "user_id", "started_at"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    idempotency_key: Mapped[UUID] = mapped_column(Uuid)
    payload_hash: Mapped[str] = mapped_column(String(64))
    first_request_id: Mapped[str] = mapped_column(String(128))
    attempt_id: Mapped[UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(16))
    mutation_status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
