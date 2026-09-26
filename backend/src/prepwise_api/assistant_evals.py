import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

EvalId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{2,79}$")]
ToolName = Literal[
    "search_meals",
    "get_meal_details",
    "get_cart",
    "add_to_cart",
    "remove_from_cart",
    "get_user_orders",
    "get_pickup_locations",
    "prepare_order",
    "create_order",
    "search_knowledge",
]


class EvalCategory(StrEnum):
    MEAL_SEARCH = "meal_search"
    NUTRITIONAL_CONSTRAINTS = "nutritional_constraints"
    ALLERGENS = "allergens"
    CART_OPERATIONS = "cart_operations"
    ORDER_QUESTIONS = "order_questions"
    RAG_QUESTIONS = "rag_questions"
    AMBIGUOUS_REQUESTS = "ambiguous_requests"
    INVALID_OR_UNSAFE_ACTIONS = "invalid_or_unsafe_actions"


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CartSetup(EvalModel):
    meal_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=99)


class EvalSetup(EvalModel):
    cart: list[CartSetup] = Field(default_factory=list)
    existing_order_count: int = Field(default=0, ge=0, le=20)
    unavailable_meals: list[str] = Field(default_factory=list)
    issue_order_confirmation: bool = False
    pickup_location_name: str | None = None


class ToolExpectation(EvalModel):
    name: ToolName
    min_calls: int = Field(default=1, ge=0, le=20)
    max_calls: int = Field(default=1, ge=1, le=20)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_call_range(self) -> "ToolExpectation":
        if self.min_calls > self.max_calls:
            raise ValueError("min_calls cannot exceed max_calls")
        return self


class MealConstraintExpectation(EvalModel):
    min_protein_grams: float | None = Field(default=None, ge=0)
    max_calories_exclusive: int | None = Field(default=None, ge=0)
    max_price_nok: float | None = Field(default=None, ge=0)
    excluded_allergens: list[str] = Field(default_factory=list)
    expected_meal_names: list[str] = Field(default_factory=list)


class EvalExpectation(EvalModel):
    required_tools: list[ToolExpectation] = Field(default_factory=list)
    allowed_tools: list[ToolName] = Field(default_factory=list)
    forbidden_tools: list[ToolName] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)
    response_must_include: list[str] = Field(default_factory=list)
    response_must_not_include: list[str] = Field(default_factory=list)
    meal_constraints: MealConstraintExpectation | None = None
    cart_quantity_delta: int = Field(default=0, ge=-99, le=99)
    order_count_delta: int = Field(default=0, ge=0, le=1)
    confirmation_count_delta: int = Field(default=0, ge=0, le=1)
    requires_clarification: bool = False
    requires_refusal: bool = False

    @model_validator(mode="after")
    def validate_tool_boundaries(self) -> "EvalExpectation":
        required = {expectation.name for expectation in self.required_tools}
        allowed = set(self.allowed_tools)
        forbidden = set(self.forbidden_tools)
        if not required <= allowed:
            raise ValueError("required tools must also be allowed")
        if allowed & forbidden:
            raise ValueError("allowed and forbidden tools must be disjoint")
        return self


class AssistantEvalCase(EvalModel):
    id: EvalId
    category: EvalCategory
    description: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    setup: EvalSetup = Field(default_factory=EvalSetup)
    expect: EvalExpectation

    @model_validator(mode="after")
    def validate_confirmation_template(self) -> "AssistantEvalCase":
        if self.setup.issue_order_confirmation:
            if not self.setup.cart or self.setup.pickup_location_name is None:
                raise ValueError("confirmation setup requires a cart and pickup location")
            if "{{confirmation_phrase}}" not in self.message:
                raise ValueError("confirmation setup requires the confirmation phrase template")
        return self


DEFAULT_EVAL_DATASET = Path(__file__).resolve().parents[2] / "evals" / "assistant_cases.jsonl"


def load_assistant_eval_cases(path: Path = DEFAULT_EVAL_DATASET) -> list[AssistantEvalCase]:
    """Load and strictly validate the version-controlled assistant evaluation dataset."""
    cases: list[AssistantEvalCase] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as dataset:
        for line_number, line in enumerate(dataset, start=1):
            if not line.strip():
                continue
            try:
                case = AssistantEvalCase.model_validate_json(line)
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(f"Invalid eval case on line {line_number}: {error}") from error
            if case.id in seen_ids:
                raise ValueError(f"Duplicate eval case id on line {line_number}: {case.id}")
            seen_ids.add(case.id)
            cases.append(case)
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    return cases
