from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

AssistantMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]


class AssistantHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(min_length=1, max_length=4000)]


class AssistantMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: AssistantMessage
    lang: Literal["no", "en"] = "no"
    history: list[AssistantHistoryMessage] = Field(default_factory=list, max_length=10)
    idempotency_key: UUID | None = None

    @model_validator(mode="after")
    def bound_history(self) -> "AssistantMessageRequest":
        if sum(len(item.content) for item in self.history) > 8000:
            raise ValueError("Chat history may not exceed 8000 characters")
        return self


class AssistantMessageResponse(BaseModel):
    reply: str
    model: str
    response_id: str
