from typing import Annotated

from pydantic import BaseModel, StringConstraints

AssistantMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class AssistantMessageRequest(BaseModel):
    message: AssistantMessage


class AssistantMessageResponse(BaseModel):
    reply: str
    model: str
    response_id: str
