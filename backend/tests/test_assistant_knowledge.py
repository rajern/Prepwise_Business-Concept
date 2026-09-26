import asyncio
import json
from collections.abc import Mapping
from typing import cast

from pydantic import SecretStr
from sqlalchemy.orm import Session

from prepwise_api.assistant_knowledge import AssistantKnowledgeTool
from prepwise_api.config import Settings
from prepwise_api.knowledge import KnowledgeMatch


class StubKnowledgeRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str, int, float]] = []

    async def retrieve(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 4,
        minimum_score: float = 0.15,
    ) -> list[KnowledgeMatch]:
        self.calls.append((session, query, limit, minimum_score))
        return [
            KnowledgeMatch(
                content="Reheat until thoroughly hot.",
                source_path="reheating_guidance.md",
                source_title="Reheating Guidance",
                section_title=None,
                chunk_index=0,
                score=0.91,
            )
        ]


def _settings() -> Settings:
    return Settings(openai_api_key=SecretStr("test-key"))


def test_knowledge_tool_definition_is_strict_and_scoped() -> None:
    definition = AssistantKnowledgeTool(_settings(), StubKnowledgeRetriever()).definition()

    assert definition["type"] == "function"
    assert definition["name"] == "search_knowledge"
    assert definition["strict"] is True
    parameters = cast(Mapping[str, object], definition["parameters"])
    assert parameters["required"] == ["query"]
    assert parameters["additionalProperties"] is False
    assert "Do not use for current meals" in str(definition["description"])


def test_knowledge_tool_returns_grounded_passages_with_source_metadata() -> None:
    retriever = StubKnowledgeRetriever()
    tool = AssistantKnowledgeTool(_settings(), retriever)
    session = cast(Session, object())

    result = json.loads(
        asyncio.run(tool.execute_json('{"query":"  How do I reheat a meal?  "}', session))
    )

    assert result["ok"] is True
    assert result["data"][0] == {
        "content": "Reheat until thoroughly hot.",
        "source_path": "reheating_guidance.md",
        "source_title": "Reheating Guidance",
        "section_title": None,
        "chunk_index": 0,
        "score": 0.91,
    }
    assert retriever.calls == [(session, "How do I reheat a meal?", 4, 0.15)]


def test_knowledge_tool_rejects_invalid_arguments_without_searching() -> None:
    retriever = StubKnowledgeRetriever()
    tool = AssistantKnowledgeTool(_settings(), retriever)

    result = json.loads(asyncio.run(tool.execute_json('{"query":"   "}', cast(Session, object()))))

    assert result == {
        "ok": False,
        "error": {
            "code": "invalid_tool_arguments",
            "message": "Knowledge search arguments failed validation",
            "details": [],
        },
    }
    assert retriever.calls == []
