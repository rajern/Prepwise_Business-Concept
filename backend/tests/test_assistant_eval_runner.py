from prepwise_api.assistant_eval_runner import (
    StateSnapshot,
    ToolCallRecord,
    score_case,
)
from prepwise_api.assistant_evals import AssistantEvalCase, load_assistant_eval_cases


def _case(case_id: str) -> AssistantEvalCase:
    return next(case for case in load_assistant_eval_cases() if case.id == case_id)


def _empty_state() -> StateSnapshot:
    return StateSnapshot(cart_quantity=0, order_count=0, confirmation_count=0)


def test_scores_tool_selection_arguments_constraints_and_safe_state() -> None:
    case = _case("nutrition_protein_calorie_filter")
    constraints = case.expect.meal_constraints
    assert constraints is not None
    expected_names = constraints.expected_meal_names
    calls = [
        ToolCallRecord(
            name="search_meals",
            arguments={"min_protein_grams": 40, "max_calories": 799, "limit": 20},
            result={"ok": True, "data": []},
        )
    ]

    metrics, failures = score_case(
        case,
        "\n".join(expected_names),
        calls,
        _empty_state(),
        _empty_state(),
    )

    assert metrics.tool_selection == 1
    assert metrics.tool_arguments == 1
    assert metrics.constraint_satisfaction == 1
    assert metrics.workflow_outcome == 1
    assert metrics.unwanted_side_effects == 1
    assert metrics.overall == 1
    assert failures == []


def test_scores_retrieval_and_grounding_from_recorded_source() -> None:
    case = _case("rag_reheating")
    calls = [
        ToolCallRecord(
            name="search_knowledge",
            arguments={"query": "reheating Prepwise meals"},
            result={
                "ok": True,
                "data": [
                    {
                        "source_path": "reheating_guidance.md",
                        "content": "Heat until thoroughly hot. Do not reheat more than once.",
                    }
                ],
            },
        )
    ]

    metrics, failures = score_case(
        case,
        "Heat it until thoroughly hot. Do not reheat it more than once.",
        calls,
        _empty_state(),
        _empty_state(),
    )

    assert metrics.retrieval_relevance == 1
    assert metrics.grounding == 1
    assert metrics.overall == 1
    assert failures == []


def test_retrieval_score_penalizes_expected_source_ranked_second() -> None:
    case = _case("rag_reheating")
    calls = [
        ToolCallRecord(
            name="search_knowledge",
            arguments={"query": "reheating"},
            result={
                "ok": True,
                "data": [
                    {"source_path": "faq.md", "content": "Other guidance"},
                    {
                        "source_path": "reheating_guidance.md",
                        "content": "Heat until thoroughly hot. Do not reheat more than once.",
                    },
                ],
            },
        )
    ]

    metrics, failures = score_case(
        case,
        "Heat until thoroughly hot. Do not reheat more than once.",
        calls,
        _empty_state(),
        _empty_state(),
    )

    assert metrics.retrieval_relevance == 0.5
    assert any(failure.metric == "retrieval_relevance" for failure in failures)


def test_reports_forbidden_write_and_unwanted_state_change() -> None:
    case = _case("unsafe_prompt_injection_write")
    calls = [
        ToolCallRecord(
            name="add_to_cart",
            arguments={"meal_id": "00000000-0000-0000-0000-000000000000", "quantity": 1},
            result={"ok": True},
        )
    ]
    after = StateSnapshot(cart_quantity=1, order_count=0, confirmation_count=0)

    metrics, failures = score_case(
        case,
        "Prepwise is a meal service.",
        calls,
        _empty_state(),
        after,
    )

    assert metrics.tool_selection < 1
    assert metrics.workflow_outcome < 1
    assert metrics.unwanted_side_effects == 0
    assert {failure.metric for failure in failures} >= {
        "tool_selection",
        "workflow_outcome",
        "unwanted_side_effects",
    }
