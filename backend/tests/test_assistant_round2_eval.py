import asyncio
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionToolCall

from prepwise_api.assistant_round2_eval import (
    BoundedResponses,
    EvalBudget,
    EvalBudgetExceeded,
    LiveCase,
    conservative_reservation,
    run_one,
)
from prepwise_api.config import Settings


def _kwargs() -> dict[str, Any]:
    return {
        "model": "gpt-5.6-terra",
        "max_output_tokens": 800,
        "store": False,
        "input": [{"role": "user", "content": "synthetic test"}],
        "instructions": "Test instructions",
        "tools": [],
    }


def _budget(tmp_path: Path) -> EvalBudget:
    budget = EvalBudget(tmp_path / "journal.json")
    budget.initialize()
    return budget


def test_global_ten_attempt_limit_and_no_rerun(tmp_path: Path) -> None:
    budget = _budget(tmp_path)
    for _ in range(10):
        budget.reserve(_kwargs())
    with pytest.raises(EvalBudgetExceeded):
        budget.reserve(_kwargs())
    with pytest.raises(FileExistsError):
        EvalBudget(budget.journal).initialize()
    assert len(json.loads(budget.journal.read_text())["attempts"]) == 10


def test_one_dollar_bound_rejects_before_reserving(tmp_path: Path) -> None:
    budget = _budget(tmp_path)
    budget.reserved_usd = Decimal("0.999")
    with pytest.raises(EvalBudgetExceeded):
        budget.reserve(_kwargs())
    assert not budget.attempts
    assert budget.reserved_usd == Decimal("0.999")


def test_utf8_input_reservation_and_oversize_guard() -> None:
    kwargs = _kwargs()
    small = conservative_reservation(kwargs)
    kwargs["instructions"] = "ø" * 100
    assert conservative_reservation(kwargs) > small
    kwargs["instructions"] = "x" * 60000
    with pytest.raises(EvalBudgetExceeded):
        conservative_reservation(kwargs)


def test_network_failure_is_counted_and_never_releases_cost(tmp_path: Path) -> None:
    budget = _budget(tmp_path)
    create = AsyncMock(side_effect=RuntimeError("simulated network failure"))
    client = cast(
        AsyncOpenAI, SimpleNamespace(max_retries=0, responses=SimpleNamespace(create=create))
    )
    bounded = BoundedResponses(client, budget)
    with pytest.raises(RuntimeError):
        asyncio.run(bounded.create(**_kwargs()))
    assert len(budget.attempts) == 1
    assert budget.reserved_usd > 0
    assert budget.attempts[0]["error_type"] == "RuntimeError"
    assert create.await_count == 1


def test_incomplete_is_recorded_with_usage_and_standard_tier(tmp_path: Path) -> None:
    budget = _budget(tmp_path)
    response = cast(
        Response,
        SimpleNamespace(
            status="incomplete",
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=800,
                output_tokens_details=SimpleNamespace(reasoning_tokens=790),
            ),
        ),
    )
    create = AsyncMock(return_value=response)
    client = cast(
        AsyncOpenAI, SimpleNamespace(max_retries=0, responses=SimpleNamespace(create=create))
    )
    assert asyncio.run(BoundedResponses(client, budget).create(**_kwargs())) is response
    assert budget.attempts[0]["status"] == "incomplete"
    assert budget.attempts[0]["output_tokens"] == 800
    assert create.await_args is not None
    assert create.await_args.kwargs["service_tier"] == "default"


@pytest.mark.parametrize(
    "field,value", [("model", "other"), ("max_output_tokens", 801), ("store", True)]
)
def test_unapproved_parameters_rejected_before_network(
    tmp_path: Path, field: str, value: object
) -> None:
    budget = _budget(tmp_path)
    create = AsyncMock()
    client = cast(
        AsyncOpenAI, SimpleNamespace(max_retries=0, responses=SimpleNamespace(create=create))
    )
    kwargs = _kwargs()
    kwargs[field] = value
    with pytest.raises(EvalBudgetExceeded):
        asyncio.run(BoundedResponses(client, budget).create(**kwargs))
    create.assert_not_awaited()
    assert not budget.attempts


def test_sdk_retries_rejected_before_network(tmp_path: Path) -> None:
    budget = _budget(tmp_path)
    create = AsyncMock()
    client = cast(
        AsyncOpenAI, SimpleNamespace(max_retries=1, responses=SimpleNamespace(create=create))
    )
    with pytest.raises(EvalBudgetExceeded):
        asyncio.run(BoundedResponses(client, budget).create(**_kwargs()))
    create.assert_not_awaited()


def test_run_one_uses_fresh_database_and_real_cart_tool() -> None:
    def response(output: list[object], text: str) -> object:
        return SimpleNamespace(
            id="synthetic",
            model="gpt-5.6-terra",
            output_text=text,
            output=output,
            usage=SimpleNamespace(input_tokens=100, output_tokens=100),
            status="completed",
        )

    case = LiveCase("offline-cart", "en", "What is in my cart?", required_tools=("get_cart",))
    for _ in range(2):
        create = AsyncMock(
            side_effect=[
                response(
                    [
                        ResponseFunctionToolCall(
                            type="function_call", name="get_cart", arguments="{}", call_id="cart"
                        )
                    ],
                    "",
                ),
                response([], "Your cart is empty."),
            ]
        )
        client = cast(AsyncOpenAI, SimpleNamespace(responses=SimpleNamespace(create=create)))
        result = asyncio.run(run_one(case, client, Settings(openai_max_retries=0)))
        assert result["structural_checks_pass"] is True
        assert result["tools"] == ["get_cart"]
        assert result["before"]["cart_quantity"] == 0
        assert result["after"]["order_count"] == 0
        assert create.await_count == 2
