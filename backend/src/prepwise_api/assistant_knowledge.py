import logging
from collections.abc import Mapping
from typing import Protocol, cast

from openai import pydantic_function_tool
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, field_validator
from sqlalchemy.orm import Session

from prepwise_api.config import Settings
from prepwise_api.knowledge import (
    EmbeddingConfigurationError,
    EmbeddingUnavailableError,
    KnowledgeMatch,
    KnowledgeRetriever,
    OpenAIEmbeddingProvider,
)
from prepwise_api.schemas.assistant_tools import AssistantToolError, AssistantToolResult

knowledge_tool_logger = logging.getLogger("prepwise.ai.knowledge_tool")


class SearchKnowledgeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1_000)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


class KnowledgeSearchBackend(Protocol):
    async def retrieve(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 4,
        minimum_score: float = 0.15,
    ) -> list[KnowledgeMatch]: ...


class AssistantKnowledgeSearcher(Protocol):
    name: str

    def definition(self) -> dict[str, object]: ...

    async def execute_json(
        self,
        arguments: str | Mapping[str, object],
        session: Session,
    ) -> str: ...


class AssistantKnowledgeTool:
    """Expose source-aware semantic retrieval as a bounded assistant tool."""

    name = "search_knowledge"

    def __init__(
        self,
        settings: Settings,
        retriever: KnowledgeSearchBackend | None = None,
    ) -> None:
        self._retriever = retriever or KnowledgeRetriever(OpenAIEmbeddingProvider(settings))

    def definition(self) -> dict[str, object]:
        chat_tool = pydantic_function_tool(
            SearchKnowledgeArguments,
            name=self.name,
            description=(
                "Search the curated Prepwise service knowledge base for FAQ, pickup policy, "
                "storage, reheating, allergens, nutrition guidance, orders and account guidance. "
                "Do not use for current meals, cart contents, customer orders or active pickup "
                "locations."
            ),
        )
        return {"type": "function", **dict(chat_tool["function"])}

    async def execute_json(
        self,
        arguments: str | Mapping[str, object],
        session: Session,
    ) -> str:
        try:
            parsed = (
                SearchKnowledgeArguments.model_validate_json(arguments)
                if isinstance(arguments, str)
                else SearchKnowledgeArguments.model_validate(dict(arguments))
            )
        except ValidationError:
            return AssistantToolResult(
                ok=False,
                error=AssistantToolError(
                    code="invalid_tool_arguments",
                    message="Knowledge search arguments failed validation",
                ),
            ).model_dump_json(exclude_none=True)

        try:
            matches = await self._retriever.retrieve(
                session,
                parsed.query,
                limit=4,
                minimum_score=0.15,
            )
        except (EmbeddingConfigurationError, EmbeddingUnavailableError):
            knowledge_tool_logger.warning(
                "AI knowledge search unavailable",
                extra={"event": "ai.knowledge_search.unavailable"},
            )
            return AssistantToolResult(
                ok=False,
                error=AssistantToolError(
                    code="knowledge_unavailable",
                    message="The Prepwise knowledge base is temporarily unavailable",
                ),
            ).model_dump_json(exclude_none=True)

        knowledge_tool_logger.info(
            "AI knowledge search completed",
            extra={
                "event": "ai.knowledge_search.completed",
                "result_count": len(matches),
            },
        )
        return AssistantToolResult(
            ok=True,
            data=_matches_json(matches),
        ).model_dump_json(exclude_none=True)


def _matches_json(matches: list[KnowledgeMatch]) -> JsonValue:
    return cast(JsonValue, [match.model_dump(mode="json") for match in matches])
