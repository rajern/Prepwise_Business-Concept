"""add knowledge chunks

Revision ID: f7b7f40b50a1
Revises: a24a50b792ac
Create Date: 2026-09-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "f7b7f40b50a1"
down_revision: str | None = "a24a50b792ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the pgvector-backed knowledge chunk index."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_chunks",
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("source_title", sa.String(length=300), nullable=False),
        sa.Column("section_title", sa.String(length=300), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding", Vector(dim=1536), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_chunks")),
        sa.UniqueConstraint(
            "source_path",
            "chunk_index",
            name="uq_knowledge_chunks_source_chunk",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_chunks_source_path"),
        "knowledge_chunks",
        ["source_path"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Remove knowledge chunks while leaving the shared vector extension installed."""
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_source_path"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
