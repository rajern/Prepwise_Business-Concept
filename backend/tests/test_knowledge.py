import asyncio
import shutil
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from openai import AsyncOpenAI
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.config import Settings
from prepwise_api.knowledge import (
    KnowledgeIndexer,
    KnowledgeRetriever,
    OpenAIEmbeddingProvider,
    load_knowledge_chunks,
)
from prepwise_api.models import Base, KnowledgeChunk
from prepwise_api.models.knowledge import KNOWLEDGE_EMBEDDING_DIMENSIONS

KNOWLEDGE_DIRECTORY = Path(__file__).parents[2] / "docs" / "knowledge-base"


class KeywordEmbeddingProvider:
    model = "test-embedding-model"

    def __init__(self) -> None:
        self.nonempty_calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if texts:
            self.nonempty_calls.append(list(texts))
        return [_keyword_vector(text) for text in texts]


def _keyword_vector(text: str) -> list[float]:
    normalized = text.casefold()
    vector = [0.0] * KNOWLEDGE_EMBEDDING_DIMENSIONS
    keyword_groups = [
        ("pickup", "collect", "location", "ready"),
        ("reheat", "microwave", "oven", "hot", "heating"),
        ("allergen", "allergy", "nutrition"),
        ("storage", "refrigerated", "chilled"),
        ("account", "sign in", "order history"),
    ]
    for index, keywords in enumerate(keyword_groups):
        vector[index] = float(sum(normalized.count(keyword) for keyword in keywords))
    if not any(vector):
        vector[len(keyword_groups)] = 1.0
    return vector


def _copy_knowledge_base(destination: Path) -> Path:
    target = destination / "knowledge-base"
    shutil.copytree(KNOWLEDGE_DIRECTORY, target)
    return target


def _create_test_engine() -> Engine:
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_markdown_documents_are_chunked_with_source_metadata() -> None:
    chunks = load_knowledge_chunks(KNOWLEDGE_DIRECTORY)

    assert {chunk.source_path for chunk in chunks} == {
        "allergens_and_nutrition.md",
        "faq.md",
        "orders_and_accounts.md",
        "pickup_policy.md",
        "reheating_guidance.md",
        "storage_guidance.md",
    }
    assert len(chunks) == 11
    faq_sections = {chunk.section_title for chunk in chunks if chunk.source_path == "faq.md"}
    assert "What is Prepwise?" in faq_sections
    assert "Does Prepwise deliver?" in faq_sections
    assert all(chunk.content_hash for chunk in chunks)
    assert all(len(chunk.content) <= 1_200 for chunk in chunks)


def test_indexer_is_idempotent_and_reindexes_only_changed_chunks(tmp_path: Path) -> None:
    knowledge_directory = _copy_knowledge_base(tmp_path)
    provider = KeywordEmbeddingProvider()
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            first = asyncio.run(KnowledgeIndexer(provider).index(session, knowledge_directory))
            second = asyncio.run(KnowledgeIndexer(provider).index(session, knowledge_directory))
            faq_path = knowledge_directory / "faq.md"
            faq_path.write_text(
                faq_path.read_text(encoding="utf-8")
                + "\n\n## Is catering available?\n\nNo, not currently.\n",
                encoding="utf-8",
            )
            third = asyncio.run(KnowledgeIndexer(provider).index(session, knowledge_directory))
            stored = session.scalars(select(KnowledgeChunk)).all()
    finally:
        engine.dispose()

    assert first.documents == 6
    assert first.created == 11
    assert second.unchanged == 11
    assert second.created == 0
    assert second.updated == 0
    assert third.created == 1
    assert third.updated == 0
    assert len(stored) == 12
    assert len(provider.nonempty_calls) == 2
    assert len(provider.nonempty_calls[0]) == 11
    assert len(provider.nonempty_calls[1]) == 1


def test_retrieval_is_independently_evaluable_and_preserves_metadata(tmp_path: Path) -> None:
    knowledge_directory = _copy_knowledge_base(tmp_path)
    provider = KeywordEmbeddingProvider()
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            asyncio.run(KnowledgeIndexer(provider).index(session, knowledge_directory))
            matches = asyncio.run(
                KnowledgeRetriever(provider).retrieve(
                    session,
                    "How should I reheat a meal in a microwave?",
                    limit=3,
                    minimum_score=0,
                )
            )
    finally:
        engine.dispose()

    assert matches
    assert matches[0].source_path == "reheating_guidance.md"
    assert matches[0].source_title == "Reheating Guidance"
    assert matches[0].chunk_index == 0
    assert "thoroughly hot" in matches[0].content
    assert matches[0].score > 0.8


def test_openai_embedding_provider_uses_configured_model_and_fixed_dimensions() -> None:
    embedding = [0.001] * KNOWLEDGE_EMBEDDING_DIMENSIONS
    response = SimpleNamespace(
        data=[SimpleNamespace(index=0, embedding=embedding)],
        usage=SimpleNamespace(prompt_tokens=7),
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    settings = Settings(
        openai_api_key=SecretStr("test-key"),
        openai_embedding_model="text-embedding-3-small",
    )
    provider = OpenAIEmbeddingProvider(settings, cast(AsyncOpenAI, client))

    result = asyncio.run(provider.embed(["Storage guidance"]))

    assert result == [embedding]
    create.assert_awaited_once_with(
        model="text-embedding-3-small",
        input=["Storage guidance"],
        encoding_format="float",
        dimensions=KNOWLEDGE_EMBEDDING_DIMENSIONS,
    )
