import json
from collections import Counter
from pathlib import Path

import pytest

from prepwise_api.assistant_evals import (
    EvalCategory,
    load_assistant_eval_cases,
)
from prepwise_api.assistant_tools import AssistantToolRegistry
from prepwise_api.seed_data import MEALS, PICKUP_LOCATIONS

WRITE_TOOLS = {"add_to_cart", "remove_from_cart", "prepare_order", "create_order"}


def test_eval_dataset_is_complete_unique_and_balanced() -> None:
    cases = load_assistant_eval_cases()
    category_counts = Counter(case.category for case in cases)

    assert len(cases) >= 32
    assert len({case.id for case in cases}) == len(cases)
    assert set(category_counts) == set(EvalCategory)
    assert all(count >= 3 for count in category_counts.values())
    assert any("norwegian" in case.tags for case in cases)
    assert any("english" in case.tags for case in cases)


def test_eval_cases_reference_only_supported_tools_and_valid_fixtures() -> None:
    cases = load_assistant_eval_cases()
    application_tools = {
        str(definition["name"]) for definition in AssistantToolRegistry().definitions()
    }
    supported_tools = application_tools | {"search_knowledge"}
    meal_names = {meal.name for meal in MEALS}
    pickup_names = {location.name for location in PICKUP_LOCATIONS}

    for case in cases:
        required_tools = {expectation.name for expectation in case.expect.required_tools}
        allowed_tools = set(case.expect.allowed_tools)
        forbidden_tools = set(case.expect.forbidden_tools)
        assert required_tools <= allowed_tools, case.id
        assert not allowed_tools & forbidden_tools, case.id
        assert allowed_tools | forbidden_tools <= supported_tools, case.id
        assert all(item.meal_name in meal_names for item in case.setup.cart), case.id
        assert set(case.setup.unavailable_meals) <= meal_names, case.id
        if case.setup.pickup_location_name is not None:
            assert case.setup.pickup_location_name in pickup_names, case.id
        if case.setup.issue_order_confirmation:
            assert case.setup.cart, case.id
            assert case.setup.pickup_location_name is not None, case.id
            assert "{{confirmation_phrase}}" in case.message, case.id
        if case.expect.requires_clarification:
            assert not allowed_tools & WRITE_TOOLS, case.id


def test_eval_knowledge_sources_exist() -> None:
    cases = load_assistant_eval_cases()
    knowledge_root = Path(__file__).parents[2] / "docs" / "knowledge-base"

    for case in cases:
        for source in case.expect.knowledge_sources:
            assert (knowledge_root / source).is_file(), f"{case.id}: {source}"


def test_eval_dataset_covers_every_t12_scoring_dimension() -> None:
    cases = load_assistant_eval_cases()

    assert any(case.expect.required_tools for case in cases)
    assert any(tool.arguments for case in cases for tool in case.expect.required_tools)
    assert any(case.expect.meal_constraints is not None for case in cases)
    assert any(case.expect.knowledge_sources for case in cases)
    assert any(case.expect.response_must_include for case in cases)
    assert any(
        case.expect.cart_quantity_delta
        or case.expect.order_count_delta
        or case.expect.confirmation_count_delta
        for case in cases
    )
    assert any(WRITE_TOOLS & set(case.expect.forbidden_tools) for case in cases)


def test_eval_loader_reports_line_and_duplicate_id(tmp_path: Path) -> None:
    valid_case = load_assistant_eval_cases()[0].model_dump(mode="json")
    duplicate_path = tmp_path / "duplicates.jsonl"
    duplicate_path.write_text(
        "\n".join([json.dumps(valid_case), json.dumps(valid_case)]),
        encoding="utf-8",
    )
    invalid_path = tmp_path / "invalid.jsonl"
    invalid_path.write_text('{"id":"broken"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate eval case id on line 2"):
        load_assistant_eval_cases(duplicate_path)
    with pytest.raises(ValueError, match="Invalid eval case on line 1"):
        load_assistant_eval_cases(invalid_path)
