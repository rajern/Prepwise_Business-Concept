import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from openai import pydantic_function_tool
from pydantic import BaseModel, JsonValue, ValidationError
from sqlalchemy.orm import Session

from prepwise_api.models import User
from prepwise_api.schemas.assistant_tools import (
    AddToCartToolArguments,
    AssistantToolError,
    AssistantToolResult,
    AssistantToolValidationIssue,
    EmptyToolArguments,
    GetMealDetailsToolArguments,
    RemoveFromCartToolArguments,
    SearchMealsToolArguments,
)
from prepwise_api.services import ApplicationServiceError
from prepwise_api.services.cart import (
    add_user_cart_item,
    get_user_cart,
    remove_user_cart_item,
)
from prepwise_api.services.catalog import (
    MealSearchFilters,
    get_meal_details,
    search_available_meals,
)
from prepwise_api.services.orders import list_user_orders
from prepwise_api.services.pickup_locations import list_active_pickup_locations

tool_logger = logging.getLogger("prepwise.ai.tools")


@dataclass(frozen=True, slots=True)
class AssistantToolContext:
    """Server-created context; callers cannot choose the authenticated user."""

    session: Session
    user: User


class AssistantToolRegistry:
    """Validated, allow-listed application capabilities exposed to the model."""

    def definitions(self) -> list[dict[str, object]]:
        return [
            _tool_definition(
                "search_meals",
                (
                    "Search currently available Prepwise meals by text, minimum protein, "
                    "maximum calories and maximum price."
                ),
                SearchMealsToolArguments,
            ),
            _tool_definition(
                "get_meal_details",
                "Get full details and current availability for one Prepwise meal by ID.",
                GetMealDetailsToolArguments,
            ),
            _tool_definition(
                "get_cart",
                "Get the authenticated customer's current cart and authoritative totals.",
                EmptyToolArguments,
            ),
            _tool_definition(
                "add_to_cart",
                "Add an available meal to the authenticated customer's cart.",
                AddToCartToolArguments,
            ),
            _tool_definition(
                "remove_from_cart",
                "Remove an owned cart item from the authenticated customer's cart.",
                RemoveFromCartToolArguments,
            ),
            _tool_definition(
                "get_user_orders",
                "List orders belonging only to the authenticated customer, newest first.",
                EmptyToolArguments,
            ),
            _tool_definition(
                "get_pickup_locations",
                "List pickup locations that are currently active and selectable.",
                EmptyToolArguments,
            ),
        ]

    def execute(
        self,
        name: str,
        arguments: str | Mapping[str, object],
        context: AssistantToolContext,
    ) -> AssistantToolResult:
        try:
            payload = _parse_arguments(arguments)
            result = self._execute_validated(name, payload, context)
        except ValidationError as error:
            return _validation_error_result(error)
        except InvalidToolArgumentsError as error:
            return _error_result("invalid_tool_arguments", str(error))
        except ApplicationServiceError as error:
            tool_logger.info(
                "AI tool rejected an application request",
                extra={"event": "ai.tool.rejected", "tool_name": name, "error_type": error.code},
            )
            return _error_result(error.code, error.message)

        tool_logger.info(
            "AI tool completed",
            extra={"event": "ai.tool.completed", "tool_name": name},
        )
        return AssistantToolResult(ok=True, data=result)

    def execute_json(
        self,
        name: str,
        arguments: str | Mapping[str, object],
        context: AssistantToolContext,
    ) -> str:
        """Return provider-ready JSON without leaking ORM or Python-specific values."""
        return self.execute(name, arguments, context).model_dump_json(exclude_none=True)

    def _execute_validated(
        self,
        name: str,
        payload: dict[str, object],
        context: AssistantToolContext,
    ) -> JsonValue:
        if name == "search_meals":
            search_arguments = SearchMealsToolArguments.model_validate(payload)
            meals = search_available_meals(
                context.session,
                MealSearchFilters(
                    query=search_arguments.query,
                    min_protein_grams=_optional_decimal(search_arguments.min_protein_grams),
                    max_calories=search_arguments.max_calories,
                    max_price_nok=_optional_decimal(search_arguments.max_price_nok),
                    limit=search_arguments.limit,
                ),
            )
            return _model_list_json(meals)
        if name == "get_meal_details":
            detail_arguments = GetMealDetailsToolArguments.model_validate(payload)
            return _model_json(get_meal_details(context.session, detail_arguments.meal_id))
        if name == "get_cart":
            EmptyToolArguments.model_validate(payload)
            return _model_json(get_user_cart(context.session, context.user.id))
        if name == "add_to_cart":
            add_arguments = AddToCartToolArguments.model_validate(payload)
            return _model_json(
                add_user_cart_item(
                    context.session,
                    context.user.id,
                    add_arguments.meal_id,
                    add_arguments.quantity,
                )
            )
        if name == "remove_from_cart":
            remove_arguments = RemoveFromCartToolArguments.model_validate(payload)
            return _model_json(
                remove_user_cart_item(
                    context.session,
                    context.user.id,
                    remove_arguments.cart_item_id,
                )
            )
        if name == "get_user_orders":
            EmptyToolArguments.model_validate(payload)
            return _model_list_json(list_user_orders(context.session, context.user.id))
        if name == "get_pickup_locations":
            EmptyToolArguments.model_validate(payload)
            return _model_list_json(list_active_pickup_locations(context.session))
        raise InvalidToolArgumentsError(f"Unknown tool: {name}")


class InvalidToolArgumentsError(Exception):
    pass


def _tool_definition(
    name: str,
    description: str,
    arguments_model: type[BaseModel],
) -> dict[str, object]:
    chat_tool = pydantic_function_tool(arguments_model, name=name, description=description)
    return {"type": "function", **dict(chat_tool["function"])}


def _parse_arguments(arguments: str | Mapping[str, object]) -> dict[str, object]:
    if isinstance(arguments, str):
        try:
            decoded: object = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise InvalidToolArgumentsError("Tool arguments must be valid JSON") from error
        if not isinstance(decoded, dict):
            raise InvalidToolArgumentsError("Tool arguments must be a JSON object")
        if not all(isinstance(key, str) for key in decoded):
            raise InvalidToolArgumentsError("Tool argument names must be strings")
        return cast(dict[str, object], decoded)
    return dict(arguments)


def _model_json(model: BaseModel) -> JsonValue:
    return cast(JsonValue, model.model_dump(mode="json"))


def _model_list_json(models: Sequence[BaseModel]) -> JsonValue:
    return cast(JsonValue, [model.model_dump(mode="json") for model in models])


def _optional_decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _validation_error_result(error: ValidationError) -> AssistantToolResult:
    details = [
        AssistantToolValidationIssue(
            field=".".join(str(part) for part in issue["loc"]),
            message=issue["msg"],
            type=issue["type"],
        )
        for issue in error.errors(include_input=False, include_url=False)
    ]
    return AssistantToolResult(
        ok=False,
        error=AssistantToolError(
            code="invalid_tool_arguments",
            message="Tool arguments failed validation",
            details=details,
        ),
    )


def _error_result(code: str, message: str) -> AssistantToolResult:
    return AssistantToolResult(ok=False, error=AssistantToolError(code=code, message=message))


def get_assistant_tool_registry() -> AssistantToolRegistry:
    return AssistantToolRegistry()
