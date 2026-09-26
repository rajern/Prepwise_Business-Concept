from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class AssistantToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyToolArguments(AssistantToolArguments):
    pass


class SearchMealsToolArguments(AssistantToolArguments):
    query: str | None = Field(default=None, min_length=1, max_length=200)
    min_protein_grams: float | None = Field(default=None, ge=0, le=5000)
    max_calories: int | None = Field(default=None, ge=0, le=10000)
    max_price_nok: float | None = Field(default=None, ge=0, le=10000)
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


class GetMealDetailsToolArguments(AssistantToolArguments):
    meal_id: UUID


class AddToCartToolArguments(AssistantToolArguments):
    meal_id: UUID
    quantity: int = Field(ge=1, le=99)


class RemoveFromCartToolArguments(AssistantToolArguments):
    cart_item_id: UUID


class PrepareOrderToolArguments(AssistantToolArguments):
    pickup_location_id: UUID


class CreateOrderToolArguments(AssistantToolArguments):
    confirmation_token: UUID


class AssistantToolValidationIssue(BaseModel):
    field: str
    message: str
    type: str


class AssistantToolError(BaseModel):
    code: str
    message: str
    details: list[AssistantToolValidationIssue] = Field(default_factory=list)


class AssistantToolResult(BaseModel):
    ok: bool
    data: JsonValue | None = None
    error: AssistantToolError | None = None
