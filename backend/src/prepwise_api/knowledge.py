import argparse
import asyncio
import hashlib
import json
import logging
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from prepwise_api.config import Settings, get_settings
from prepwise_api.database import get_engine
from prepwise_api.models import KnowledgeChunk
from prepwise_api.models.knowledge import KNOWLEDGE_EMBEDDING_DIMENSIONS
from prepwise_api.telemetry import record_safe_exception

knowledge_logger = logging.getLogger("prepwise.ai.knowledge")

_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_DEFAULT_CHUNK_CHARACTERS = 1_200
_DEFAULT_OVERLAP_WORDS = 30


class EmbeddingConfigurationError(Exception):
    """The embedding provider is missing required server-side configuration."""


class EmbeddingUnavailableError(Exception):
    """The embedding provider could not complete the request safely."""


class KnowledgeIndexError(Exception):
    """Knowledge documents or generated vectors are invalid."""


class EmbeddingProvider(Protocol):
    @property
    def model(self) -> str: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    """Generate fixed-width embeddings without logging source or query content."""

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings
        self._client = client

    @property
    def model(self) -> str:
        return self._settings.openai_embedding_model

    def _resolve_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if self._settings.openai_api_key is None:
            raise EmbeddingConfigurationError
        self._client = AsyncOpenAI(
            api_key=self._settings.openai_api_key.get_secret_value(),
            timeout=self._settings.openai_timeout_seconds,
            max_retries=self._settings.openai_max_retries,
        )
        return self._client

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = await self._resolve_client().embeddings.create(
                model=self.model,
                input=list(texts),
                encoding_format="float",
                dimensions=KNOWLEDGE_EMBEDDING_DIMENSIONS,
            )
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as error:
            record_safe_exception(error)
            knowledge_logger.warning(
                "Embedding request failed",
                extra={
                    "event": "ai.embedding.failed",
                    "model": self.model,
                    "error_type": type(error).__name__,
                    "input_count": len(texts),
                },
            )
            raise EmbeddingUnavailableError from error

        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in ordered]
        _validate_embeddings(vectors, expected_count=len(texts))
        knowledge_logger.info(
            "Embedding request completed",
            extra={
                "event": "ai.embedding.completed",
                "model": self.model,
                "input_count": len(texts),
                "input_tokens": response.usage.prompt_tokens,
            },
        )
        return vectors


@dataclass(frozen=True, slots=True)
class KnowledgeChunkDraft:
    source_path: str
    source_title: str
    section_title: str | None
    chunk_index: int
    content: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class KnowledgeIndexSummary:
    documents: int
    chunks: int
    created: int
    updated: int
    unchanged: int
    deleted: int


class KnowledgeMatch(BaseModel):
    content: str
    source_path: str
    source_title: str
    section_title: str | None
    chunk_index: int
    score: float = Field(ge=-1, le=1)


def load_knowledge_chunks(
    directory: Path,
    *,
    max_characters: int = _DEFAULT_CHUNK_CHARACTERS,
    overlap_words: int = _DEFAULT_OVERLAP_WORDS,
) -> list[KnowledgeChunkDraft]:
    """Load Markdown documents and split them into deterministic semantic chunks."""
    if max_characters < 200:
        raise ValueError("max_characters must be at least 200")
    if overlap_words < 0:
        raise ValueError("overlap_words cannot be negative")
    if not directory.is_dir():
        raise KnowledgeIndexError(f"Knowledge directory does not exist: {directory}")

    markdown_paths = sorted(path for path in directory.rglob("*.md") if path.is_file())
    if not markdown_paths:
        raise KnowledgeIndexError(f"No Markdown documents found in: {directory}")

    drafts: list[KnowledgeChunkDraft] = []
    for path in markdown_paths:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise KnowledgeIndexError(f"Knowledge document is empty: {path.name}")
        source_path = path.relative_to(directory).as_posix()
        drafts.extend(
            _chunk_markdown_document(
                source_path,
                text,
                max_characters=max_characters,
                overlap_words=overlap_words,
            )
        )
    return drafts


def _chunk_markdown_document(
    source_path: str,
    text: str,
    *,
    max_characters: int,
    overlap_words: int,
) -> list[KnowledgeChunkDraft]:
    source_title = Path(source_path).stem.replace("_", " ").replace("-", " ").title()
    sections: list[tuple[str | None, list[str]]] = []
    current_section: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        heading = _MARKDOWN_HEADING.match(line.strip())
        if heading:
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            if level == 1 and not sections and not current_lines:
                source_title = heading_text
                continue
            if current_lines:
                sections.append((current_section, current_lines))
            current_section = heading_text
            current_lines = []
            continue
        current_lines.append(line)
    if current_lines:
        sections.append((current_section, current_lines))

    chunks: list[KnowledgeChunkDraft] = []
    for section_title, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        prefix = f"# {source_title}"
        if section_title is not None:
            prefix += f"\n\n## {section_title}"
        available_characters = max_characters - len(prefix) - 2
        if available_characters < 100:
            raise ValueError("max_characters is too small for document headings")
        for body_part in _split_text(body, available_characters, overlap_words):
            content = f"{prefix}\n\n{body_part}".strip()
            chunks.append(
                KnowledgeChunkDraft(
                    source_path=source_path,
                    source_title=source_title,
                    section_title=section_title,
                    chunk_index=len(chunks),
                    content=content,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )

    if not chunks:
        raise KnowledgeIndexError(f"Knowledge document has no indexable content: {source_path}")
    return chunks


def _split_text(text: str, max_characters: int, overlap_words: int) -> list[str]:
    if len(text) <= max_characters:
        return [text]
    words = text.split()
    parts: list[str] = []
    start = 0
    while start < len(words):
        end = start
        current_length = 0
        while end < len(words):
            next_length = current_length + len(words[end]) + (1 if end > start else 0)
            if next_length > max_characters and end > start:
                break
            current_length = next_length
            end += 1
        parts.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = max(start + 1, end - overlap_words)
    return parts


class KnowledgeIndexer:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    async def index(self, session: Session, directory: Path) -> KnowledgeIndexSummary:
        drafts = load_knowledge_chunks(directory)
        existing = session.scalars(select(KnowledgeChunk)).all()
        existing_by_key = {(chunk.source_path, chunk.chunk_index): chunk for chunk in existing}
        draft_by_key = {(draft.source_path, draft.chunk_index): draft for draft in drafts}

        changed = [
            draft
            for key, draft in draft_by_key.items()
            if key not in existing_by_key
            or existing_by_key[key].content_hash != draft.content_hash
            or existing_by_key[key].embedding_model != self._provider.model
        ]
        vectors = await self._provider.embed([draft.content for draft in changed])
        _validate_embeddings(vectors, expected_count=len(changed))

        created = 0
        updated = 0
        for draft, embedding in zip(changed, vectors, strict=True):
            key = (draft.source_path, draft.chunk_index)
            chunk = existing_by_key.get(key)
            if chunk is None:
                chunk = KnowledgeChunk()
                session.add(chunk)
                created += 1
            else:
                updated += 1
            chunk.source_path = draft.source_path
            chunk.source_title = draft.source_title
            chunk.section_title = draft.section_title
            chunk.chunk_index = draft.chunk_index
            chunk.content = draft.content
            chunk.content_hash = draft.content_hash
            chunk.embedding_model = self._provider.model
            chunk.embedding = embedding

        stale_keys = set(existing_by_key) - set(draft_by_key)
        for key in stale_keys:
            session.delete(existing_by_key[key])

        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

        return KnowledgeIndexSummary(
            documents=len({draft.source_path for draft in drafts}),
            chunks=len(drafts),
            created=created,
            updated=updated,
            unchanged=len(drafts) - len(changed),
            deleted=len(stale_keys),
        )


class KnowledgeRetriever:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    async def retrieve(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 4,
        minimum_score: float = 0.15,
    ) -> list[KnowledgeMatch]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank")
        if len(normalized_query) > 1_000:
            raise ValueError("query cannot exceed 1000 characters")
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        if not -1 <= minimum_score <= 1:
            raise ValueError("minimum_score must be between -1 and 1")

        vectors = await self._provider.embed([normalized_query])
        query_embedding = vectors[0]
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            ranked = _postgresql_matches(
                session,
                query_embedding,
                self._provider.model,
                limit,
            )
        else:
            ranked = _portable_matches(
                session,
                query_embedding,
                self._provider.model,
                limit,
            )

        return [
            KnowledgeMatch(
                content=chunk.content,
                source_path=chunk.source_path,
                source_title=chunk.source_title,
                section_title=chunk.section_title,
                chunk_index=chunk.chunk_index,
                score=score,
            )
            for chunk, score in ranked
            if score >= minimum_score
        ]


def _postgresql_matches(
    session: Session,
    query_embedding: list[float],
    embedding_model: str,
    limit: int,
) -> list[tuple[KnowledgeChunk, float]]:
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance")
    rows = session.execute(
        select(KnowledgeChunk, distance)
        .where(KnowledgeChunk.embedding_model == embedding_model)
        .order_by(distance)
        .limit(limit)
    ).all()
    return [
        (
            cast(KnowledgeChunk, chunk),
            _clamp_similarity(1.0 - cast(float, value)),
        )
        for chunk, value in rows
    ]


def _portable_matches(
    session: Session,
    query_embedding: list[float],
    embedding_model: str,
    limit: int,
) -> list[tuple[KnowledgeChunk, float]]:
    chunks = session.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.embedding_model == embedding_model)
    ).all()
    ranked = [(chunk, _cosine_similarity(query_embedding, chunk.embedding)) for chunk in chunks]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:limit]


def _cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    if len(left_values) != len(right_values):
        raise KnowledgeIndexError("Embedding dimensions do not match")
    dot_product = sum(a * b for a, b in zip(left_values, right_values, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return _clamp_similarity(dot_product / (left_norm * right_norm))


def _clamp_similarity(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _validate_embeddings(vectors: Sequence[Sequence[float]], *, expected_count: int) -> None:
    if len(vectors) != expected_count:
        raise KnowledgeIndexError("Embedding provider returned an unexpected vector count")
    if any(len(vector) != KNOWLEDGE_EMBEDDING_DIMENSIONS for vector in vectors):
        raise KnowledgeIndexError(
            f"Embeddings must contain {KNOWLEDGE_EMBEDDING_DIMENSIONS} dimensions"
        )


def _default_knowledge_directory() -> Path:
    candidates = [Path("docs/knowledge-base"), Path("../docs/knowledge-base")]
    return next((path for path in candidates if path.is_dir()), candidates[0])


async def _index_from_cli(arguments: argparse.Namespace) -> KnowledgeIndexSummary:
    settings = get_settings()
    provider = OpenAIEmbeddingProvider(settings)
    with Session(get_engine()) as session:
        return await KnowledgeIndexer(provider).index(session, arguments.documents)


async def _retrieve_from_cli(arguments: argparse.Namespace) -> list[KnowledgeMatch]:
    settings = get_settings()
    provider = OpenAIEmbeddingProvider(settings)
    with Session(get_engine()) as session:
        return await KnowledgeRetriever(provider).retrieve(
            session,
            arguments.query,
            limit=arguments.limit,
            minimum_score=arguments.minimum_score,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Prepwise knowledge-base Markdown files")
    parser.add_argument(
        "--documents",
        type=Path,
        default=_default_knowledge_directory(),
        help="Path to the Markdown knowledge-base directory",
    )
    arguments = parser.parse_args()
    summary = asyncio.run(_index_from_cli(arguments))
    print(
        "Knowledge index synchronized: "
        f"{summary.documents} documents, {summary.chunks} chunks, "
        f"{summary.created} created, {summary.updated} updated, "
        f"{summary.unchanged} unchanged, {summary.deleted} deleted."
    )


def retrieve_main() -> None:
    parser = argparse.ArgumentParser(description="Query the Prepwise knowledge index")
    parser.add_argument("query", help="Natural-language retrieval query")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--minimum-score", type=float, default=0.15)
    arguments = parser.parse_args()
    matches = asyncio.run(_retrieve_from_cli(arguments))
    print(
        json.dumps(
            [match.model_dump(mode="json") for match in matches],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
