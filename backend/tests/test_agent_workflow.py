import asyncio
from collections.abc import Iterator, Mapping
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from openai import AsyncOpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.assistant import AssistantService
from prepwise_api.assistant_tools import AssistantToolContext, AssistantToolRegistry
from prepwise_api.config import Settings
from prepwise_api.models import Base, Meal, User
from prepwise_api.seed import seed_database
from prepwise_api.services.cart import get_user_cart


@pytest.fixture
def engine() -> Iterator[Engine]:
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    seed_database(test_engine)
    with Session(test_engine) as session:
        session.add(User(external_subject="workflow-user", email="workflow@example.com"))
        session.commit()
    try:
        yield test_engine
    finally:
        test_engine.dispose()


class StockChangeRegistry(AssistantToolRegistry):
    def __init__(self, unavailable_after_search: UUID) -> None:
        self._unavailable_after_search = unavailable_after_search
        self._changed = False
        self.calls: list[str] = []

    def execute_json(
        self,
        name: str,
        arguments: str | Mapping[str, object],
        context: AssistantToolContext,
    ) -> str:
        self.calls.append(name)
        output = super().execute_json(name, arguments, context)
        if name == "search_meals" and not self._changed:
            meal = context.session.get(Meal, self._unavailable_after_search)
            assert meal is not None
            meal.available = False
            context.session.commit()
            self._changed = True
        return output


def _tool_response(name: str, arguments: str, index: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"resp_{index}",
        model="gpt-5.6-terra",
        output_text="",
        output=[
            ResponseFunctionToolCall(
                type="function_call",
                name=name,
                arguments=arguments,
                call_id=f"call_{index}",
            )
        ],
        usage=None,
        _request_id=f"req_{index}",
    )


def _text_response(text: str, index: int, *, preserve_output: bool = False) -> SimpleNamespace:
    output = [SimpleNamespace(type="message", content=[])] if preserve_output else []
    return SimpleNamespace(
        id=f"resp_{index}",
        model="gpt-5.6-terra",
        output_text=text,
        output=output,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        _request_id=f"req_{index}",
    )


def _workflow_context(session: Session) -> AssistantToolContext:
    user = session.scalar(select(User).where(User.external_subject == "workflow-user"))
    assert user is not None
    return AssistantToolContext(session=session, user=user)


def _eligible_meals(session: Session, limit: int) -> list[Meal]:
    return list(
        session.scalars(
            select(Meal)
            .where(
                Meal.available.is_(True),
                Meal.protein_grams >= Decimal("40"),
                Meal.calories < 800,
            )
            .order_by(Meal.name)
            .limit(limit)
        ).all()
    )


def test_multi_step_workflow_forces_final_cart_verification(engine: Engine) -> None:
    with Session(engine) as session:
        context = _workflow_context(session)
        meals = _eligible_meals(session, 5)
        assert len(meals) == 5
        expected_names = {meal.name for meal in meals}
        responses = [
            _tool_response(
                "search_meals",
                '{"min_protein_grams":40,"max_calories":799,"limit":5}',
                0,
            ),
            *[
                _tool_response(
                    "add_to_cart",
                    f'{{"meal_id":"{meal.id}","quantity":1}}',
                    index,
                )
                for index, meal in enumerate(meals, start=1)
            ],
            _text_response("I added five meals.", 6, preserve_output=True),
            _tool_response("get_cart", "{}", 7),
            _text_response("Added five matching meals and verified the cart.", 8),
        ]
        create = AsyncMock(side_effect=responses)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        service = AssistantService(
            Settings(openai_api_key=SecretStr("test-key")),
            cast(AsyncOpenAI, client),
        )

        reply = asyncio.run(
            service.respond(
                message=(
                    "Find five meals with at least 40 g protein and under 800 kcal and add them "
                    "to my cart."
                ),
                request_id="workflow-success",
                tool_context=context,
            )
        )
        cart = get_user_cart(session, context.user.id)

    assert reply.text == "Added five matching meals and verified the cart."
    assert cart.total_quantity == 5
    assert {item.meal.name for item in cart.items} == expected_names
    assert create.await_count == 9
    assert create.await_args_list[7].kwargs["tool_choice"] == {
        "type": "function",
        "name": "get_cart",
    }
    final_input = create.await_args_list[8].kwargs["input"]
    assert final_input[-1]["type"] == "function_call_output"
    assert all(name in final_input[-1]["output"] for name in expected_names)


def test_multi_step_workflow_recovers_from_stock_change_and_blocks_repeat(
    engine: Engine,
) -> None:
    with Session(engine) as session:
        context = _workflow_context(session)
        candidates = _eligible_meals(session, 6)
        assert len(candidates) == 6
        failed_candidate, *alternatives = candidates
        failed_name = failed_candidate.name
        alternative_names = {meal.name for meal in alternatives}
        registry = StockChangeRegistry(failed_candidate.id)
        responses = [
            _tool_response(
                "search_meals",
                '{"min_protein_grams":40,"max_calories":799,"limit":6}',
                0,
            ),
            _tool_response(
                "add_to_cart",
                f'{{"meal_id":"{failed_candidate.id}","quantity":1}}',
                1,
            ),
            _tool_response(
                "add_to_cart",
                f'{{"quantity":1,"meal_id":"{failed_candidate.id}"}}',
                2,
            ),
            *[
                _tool_response(
                    "add_to_cart",
                    f'{{"meal_id":"{meal.id}","quantity":1}}',
                    index,
                )
                for index, meal in enumerate(alternatives, start=3)
            ],
            _tool_response("get_cart", "{}", 8),
            _text_response("Recovered from the stock change and verified five meals.", 9),
        ]
        create = AsyncMock(side_effect=responses)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        service = AssistantService(
            Settings(openai_api_key=SecretStr("test-key")),
            cast(AsyncOpenAI, client),
            registry,
        )

        reply = asyncio.run(
            service.respond(
                message=(
                    "Find five meals with at least 40 g protein and under 800 kcal and add them "
                    "to my cart."
                ),
                request_id="workflow-recovery",
                tool_context=context,
            )
        )
        cart = get_user_cart(session, context.user.id)

    assert reply.text == "Recovered from the stock change and verified five meals."
    assert cart.total_quantity == 5
    assert {item.meal.name for item in cart.items} == alternative_names
    assert failed_name not in {item.meal.name for item in cart.items}
    assert registry.calls.count("add_to_cart") == 6
    assert create.await_count == 10
    final_input = create.await_args_list[-1].kwargs["input"]
    tool_outputs = [
        item["output"]
        for item in final_input
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert any("repeated_tool_failure" in output for output in tool_outputs)
