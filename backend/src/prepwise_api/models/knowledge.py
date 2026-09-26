from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from prepwise_api.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

KNOWLEDGE_EMBEDDING_DIMENSIONS = 1536


class KnowledgeChunk(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_path", "chunk_index", name="uq_knowledge_chunks_source_chunk"),
    )

    source_path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(300))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(KNOWLEDGE_EMBEDDING_DIMENSIONS),
        nullable=False,
    )
