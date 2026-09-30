from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prepwise_api.assistant import AssistantService, assistant_prompt_fingerprint
from prepwise_api.assistant_evals import (
    DEFAULT_EVAL_DATASET,
    AssistantEvalCase,
    EvalCategory,
    MealConstraintExpectation,
    load_assistant_eval_cases,
)
from prepwise_api.assistant_knowledge import AssistantKnowledgeTool
from prepwise_api.assistant_tools import AssistantToolContext, AssistantToolRegistry
from prepwise_api.config import Settings, get_settings
from prepwise_api.knowledge import (
    EmbeddingProvider,
    KnowledgeChunkDraft,
    KnowledgeMatch,
    OpenAIEmbeddingProvider,
    load_knowledge_chunks,
)
from prepwise_api.models import (
    Base,
    CartItem,
    Meal,
    Order,
    OrderConfirmation,
    PickupLocation,
    User,
)
from prepwise_api.seed import seed_database
from prepwise_api.seed_data import MEALS, MealSeed
from prepwise_api.services.cart import add_user_cart_item
from prepwise_api.services.orders import prepare_user_order_confirmation
from prepwise_api.services.pickup_schedule import list_pickup_options

_ROOT = Path(__file__).resolve().parents[3]
_KNOWLEDGE_ROOT = _ROOT / "docs" / "knowledge-base"
_DEFAULT_OUTPUT = _ROOT / "backend" / "eval-results"
_TOKEN = re.compile(r"[\wæøåÆØÅ-]+", re.UNICODE)
_WRITE_TOOLS = {"add_to_cart", "remove_from_cart", "prepare_order", "create_order"}
_CASE_PASS_THRESHOLD = 0.90


class EvalResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCallRecord(EvalResultModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class StateSnapshot(EvalResultModel):
    cart_quantity: int
    order_count: int
    confirmation_count: int


class MetricScores(EvalResultModel):
    tool_selection: float
    tool_arguments: float | None = None
    constraint_satisfaction: float | None = None
    retrieval_relevance: float | None = None
    grounding: float | None = None
    workflow_outcome: float
    unwanted_side_effects: float
    overall: float


class EvalFailure(EvalResultModel):
    metric: str
    message: str
    expected: Any | None = None
    actual: Any | None = None


class CaseResult(EvalResultModel):
    case_id: str
    category: EvalCategory
    passed: bool
    duration_ms: int
    response: str
    response_id: str
    tool_calls: list[ToolCallRecord]
    before: StateSnapshot
    after: StateSnapshot
    metrics: MetricScores
    failures: list[EvalFailure]


class AggregateScores(EvalResultModel):
    pass_rate: float
    mean_overall: float
    by_metric: dict[str, float]
    by_category: dict[str, float]


class BaselineComparison(EvalResultModel):
    baseline_path: str
    pass_rate_delta: float
    mean_overall_delta: float
    metric_deltas: dict[str, float]


class EvalRunReport(EvalResultModel):
    schema_version: int = 1
    run_id: str
    started_at: datetime
    completed_at: datetime
    model: str
    reasoning_effort: str
    embedding_model: str
    prompt_sha256: str
    dataset_sha256: str
    dataset_path: str
    case_count: int
    passed_count: int
    scores: AggregateScores
    results: list[CaseResult]
    baseline: BaselineComparison | None = None


class RecordingToolRegistry(AssistantToolRegistry):
    def __init__(self, calls: list[ToolCallRecord]) -> None:
        self.calls = calls

    def execute_json(
        self,
        name: str,
        arguments: str | Mapping[str, object],
        context: AssistantToolContext,
    ) -> str:
        result_json = super().execute_json(name, arguments, context)
        self.calls.append(
            ToolCallRecord(
                name=name,
                arguments=_arguments_dict(arguments),
                result=_json_object(result_json),
            )
        )
        return result_json


class InMemoryKnowledgeBackend:
    """Evaluate production embeddings/retrieval without touching a persistent database."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        drafts: Sequence[KnowledgeChunkDraft],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        self._provider = provider
        self._drafts = list(drafts)
        self._vectors = [list(vector) for vector in vectors]

    @classmethod
    async def create(
        cls,
        provider: EmbeddingProvider,
        knowledge_root: Path = _KNOWLEDGE_ROOT,
    ) -> InMemoryKnowledgeBackend:
        drafts = load_knowledge_chunks(knowledge_root)
        vectors = await provider.embed([draft.content for draft in drafts])
        return cls(provider, drafts, vectors)

    async def retrieve(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 4,
        minimum_score: float = 0.15,
    ) -> list[KnowledgeMatch]:
        del session
        query_vector = (await self._provider.embed([query]))[0]
        ranked = sorted(
            zip(self._drafts, self._vectors, strict=True),
            key=lambda item: _cosine_similarity(query_vector, item[1]),
            reverse=True,
        )
        return [
            KnowledgeMatch(
                content=draft.content,
                source_path=draft.source_path,
                source_title=draft.source_title,
                section_title=draft.section_title,
                chunk_index=draft.chunk_index,
                score=score,
            )
            for draft, vector in ranked[:limit]
            if (score := _cosine_similarity(query_vector, vector)) >= minimum_score
        ]


class RecordingKnowledgeTool(AssistantKnowledgeTool):
    def __init__(
        self,
        settings: Settings,
        backend: InMemoryKnowledgeBackend,
        calls: list[ToolCallRecord],
    ) -> None:
        super().__init__(settings, backend)
        self.calls = calls

    async def execute_json(
        self,
        arguments: str | Mapping[str, object],
        session: Session,
    ) -> str:
        result_json = await super().execute_json(arguments, session)
        self.calls.append(
            ToolCallRecord(
                name=self.name,
                arguments=_arguments_dict(arguments),
                result=_json_object(result_json),
            )
        )
        return result_json


def score_case(
    case: AssistantEvalCase,
    response: str,
    tool_calls: list[ToolCallRecord],
    before: StateSnapshot,
    after: StateSnapshot,
) -> tuple[MetricScores, list[EvalFailure]]:
    failures: list[EvalFailure] = []
    selection = _score_tool_selection(case, tool_calls, failures)
    arguments = _score_tool_arguments(case, tool_calls, failures)
    constraints = _score_constraints(case, response, failures)
    retrieval = _score_retrieval(case, tool_calls, failures)
    grounding = _score_grounding(case, response, failures)
    outcome = _score_workflow(case, response, before, after, failures)
    side_effects = _score_side_effects(case, tool_calls, before, after, failures)
    applicable = [
        score
        for score in (
            selection,
            arguments,
            constraints,
            retrieval,
            grounding,
            outcome,
            side_effects,
        )
        if score is not None
    ]
    overall = sum(applicable) / len(applicable)
    return (
        MetricScores(
            tool_selection=selection,
            tool_arguments=arguments,
            constraint_satisfaction=constraints,
            retrieval_relevance=retrieval,
            grounding=grounding,
            workflow_outcome=outcome,
            unwanted_side_effects=side_effects,
            overall=overall,
        ),
        failures,
    )


def _score_tool_selection(
    case: AssistantEvalCase,
    calls: list[ToolCallRecord],
    failures: list[EvalFailure],
) -> float:
    counts = Counter(call.name for call in calls)
    checks: list[bool] = []
    for expected in case.expect.required_tools:
        passed = expected.min_calls <= counts[expected.name] <= expected.max_calls
        checks.append(passed)
        if not passed:
            failures.append(
                EvalFailure(
                    metric="tool_selection",
                    message=f"Unexpected call count for {expected.name}",
                    expected=f"{expected.min_calls}..{expected.max_calls}",
                    actual=counts[expected.name],
                )
            )
    allowed = set(case.expect.allowed_tools)
    unexpected = sorted(name for name in counts if name not in allowed)
    checks.append(not unexpected)
    if unexpected:
        failures.append(
            EvalFailure(
                metric="tool_selection",
                message="Assistant called tools outside the allowlist",
                expected=sorted(allowed),
                actual=unexpected,
            )
        )
    forbidden = sorted(set(counts) & set(case.expect.forbidden_tools))
    checks.append(not forbidden)
    if forbidden:
        failures.append(
            EvalFailure(
                metric="tool_selection",
                message="Assistant called forbidden tools",
                expected=[],
                actual=forbidden,
            )
        )
    return sum(checks) / len(checks)


def _score_tool_arguments(
    case: AssistantEvalCase,
    calls: list[ToolCallRecord],
    failures: list[EvalFailure],
) -> float | None:
    expectations = [item for item in case.expect.required_tools if item.arguments]
    if not expectations:
        return None
    checks: list[bool] = []
    for expected in expectations:
        candidates = [call.arguments for call in calls if call.name == expected.name]
        matched = any(_arguments_match(expected.arguments, actual) for actual in candidates)
        checks.append(matched)
        if not matched:
            failures.append(
                EvalFailure(
                    metric="tool_arguments",
                    message=f"No {expected.name} call had the expected stable arguments",
                    expected=expected.arguments,
                    actual=candidates,
                )
            )
    return sum(checks) / len(checks)


def _score_constraints(
    case: AssistantEvalCase,
    response: str,
    failures: list[EvalFailure],
) -> float | None:
    expected = case.expect.meal_constraints
    if expected is None:
        return None
    mentioned = _mentioned_meals(response)
    checks: list[bool] = []
    for name in expected.expected_meal_names:
        checks.append(name in mentioned)
        if name not in mentioned:
            failures.append(
                EvalFailure(
                    metric="constraint_satisfaction",
                    message="Expected eligible meal missing from response",
                    expected=name,
                    actual=sorted(mentioned),
                )
            )
    meal_by_name = {meal.name: meal for meal in MEALS}
    for name in mentioned:
        meal = meal_by_name.get(name)
        if meal is None:
            continue
        passed = _meal_satisfies(meal, expected)
        checks.append(passed)
        if not passed:
            failures.append(
                EvalFailure(
                    metric="constraint_satisfaction",
                    message="Response included a meal outside the requested constraints",
                    expected=expected.model_dump(mode="json"),
                    actual=name,
                )
            )
    if not checks:
        failures.append(
            EvalFailure(
                metric="constraint_satisfaction",
                message="No meal result could be checked",
                expected=expected.model_dump(mode="json"),
                actual=response,
            )
        )
        return 0.0
    return sum(checks) / len(checks)


def _score_retrieval(
    case: AssistantEvalCase,
    calls: list[ToolCallRecord],
    failures: list[EvalFailure],
) -> float | None:
    expected = set(case.expect.knowledge_sources)
    if not expected:
        return None
    ranked_sources: list[str] = []
    for call in calls:
        if call.name != "search_knowledge":
            continue
        data = call.result.get("data")
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict) or "source_path" not in item:
                    continue
                source = str(item["source_path"])
                if source not in ranked_sources:
                    ranked_sources.append(source)
    actual = set(ranked_sources)
    recall = len(expected & actual) / len(expected)
    first_relevant_rank = next(
        (index for index, source in enumerate(ranked_sources, start=1) if source in expected),
        None,
    )
    reciprocal_rank = 1 / first_relevant_rank if first_relevant_rank is not None else 0.0
    score = recall * reciprocal_rank
    if score < 1:
        failures.append(
            EvalFailure(
                metric="retrieval_relevance",
                message="Expected knowledge source was missing or not ranked first",
                expected=sorted(expected),
                actual=ranked_sources,
            )
        )
    return score


def _score_grounding(
    case: AssistantEvalCase,
    response: str,
    failures: list[EvalFailure],
) -> float | None:
    required = case.expect.response_must_include
    forbidden = case.expect.response_must_not_include
    if not required and not forbidden:
        return None
    normalized = _normalize(response)
    checks: list[bool] = []
    for phrase in required:
        passed = _phrase_present(phrase, normalized)
        checks.append(passed)
        if not passed:
            failures.append(
                EvalFailure(
                    metric="grounding",
                    message="Required fact missing from response",
                    expected=phrase,
                    actual=response,
                )
            )
    for phrase in forbidden:
        passed = not _phrase_present(phrase, normalized)
        checks.append(passed)
        if not passed:
            failures.append(
                EvalFailure(
                    metric="grounding",
                    message="Forbidden claim present in response",
                    expected=f"not: {phrase}",
                    actual=response,
                )
            )
    return sum(checks) / len(checks)


def _score_workflow(
    case: AssistantEvalCase,
    response: str,
    before: StateSnapshot,
    after: StateSnapshot,
    failures: list[EvalFailure],
) -> float:
    checks = [bool(response.strip())]
    if case.expect.requires_clarification:
        checks.append(_is_clarification(response))
    if case.expect.requires_refusal:
        refusal_terms = (
            "kan ikke",
            "cannot",
            "can't",
            "ikke tilgang",
            "not able",
            "bare vise",
            "kun vise",
        )
        checks.append(any(term in response.casefold() for term in refusal_terms))
    expected_deltas = (
        case.expect.cart_quantity_delta,
        case.expect.order_count_delta,
        case.expect.confirmation_count_delta,
    )
    actual_deltas = (
        after.cart_quantity - before.cart_quantity,
        after.order_count - before.order_count,
        after.confirmation_count - before.confirmation_count,
    )
    checks.extend(
        expected == actual for expected, actual in zip(expected_deltas, actual_deltas, strict=True)
    )
    if not all(checks):
        failures.append(
            EvalFailure(
                metric="workflow_outcome",
                message="Final response or application state did not match the expected outcome",
                expected={
                    "cart_delta": expected_deltas[0],
                    "order_delta": expected_deltas[1],
                    "confirmation_delta": expected_deltas[2],
                    "clarification": case.expect.requires_clarification,
                    "refusal": case.expect.requires_refusal,
                },
                actual={
                    "cart_delta": actual_deltas[0],
                    "order_delta": actual_deltas[1],
                    "confirmation_delta": actual_deltas[2],
                    "response": response,
                },
            )
        )
    return sum(checks) / len(checks)


def _is_clarification(response: str) -> bool:
    normalized = _normalize(response)
    clarification_terms = (
        "?",
        "oppgi",
        "trenger et konkret valg",
        "trenger mer informasjon",
        "hvilken rett",
        "hvilket måltid",
        "what meal",
        "which meal",
        "need more information",
    )
    return any(term in normalized for term in clarification_terms)


def _score_side_effects(
    case: AssistantEvalCase,
    calls: list[ToolCallRecord],
    before: StateSnapshot,
    after: StateSnapshot,
    failures: list[EvalFailure],
) -> float:
    forbidden_writes = set(case.expect.forbidden_tools) & _WRITE_TOOLS
    actual_forbidden = sorted({call.name for call in calls} & forbidden_writes)
    expected = (
        case.expect.cart_quantity_delta,
        case.expect.order_count_delta,
        case.expect.confirmation_count_delta,
    )
    actual = (
        after.cart_quantity - before.cart_quantity,
        after.order_count - before.order_count,
        after.confirmation_count - before.confirmation_count,
    )
    checks = [not actual_forbidden, expected == actual]
    if not all(checks):
        failures.append(
            EvalFailure(
                metric="unwanted_side_effects",
                message="Unexpected write call or state change detected",
                expected={"deltas": expected, "forbidden_writes": []},
                actual={"deltas": actual, "forbidden_writes": actual_forbidden},
            )
        )
    return sum(checks) / len(checks)


async def run_case(
    case: AssistantEvalCase,
    settings: Settings,
    knowledge_backend: InMemoryKnowledgeBackend,
) -> CaseResult:
    engine = _create_eval_engine()
    started = time.perf_counter()
    try:
        calls: list[ToolCallRecord] = []
        registry = RecordingToolRegistry(calls)
        knowledge_tool = RecordingKnowledgeTool(settings, knowledge_backend, calls)
        with Session(engine) as session:
            user, message = _prepare_case(session, case)
            before = _snapshot(session, user.id)
            reply = await AssistantService(
                settings,
                tool_registry=registry,
                knowledge_tool=knowledge_tool,
            ).respond(
                message=message,
                request_id=f"eval-{case.id}",
                tool_context=AssistantToolContext(
                    session=session,
                    user=user,
                    request_id=f"eval-{case.id}",
                    message=message,
                ),
            )
            after = _snapshot(session, user.id)
        metrics, failures = score_case(case, reply.text, calls, before, after)
        return CaseResult(
            case_id=case.id,
            category=case.category,
            passed=_case_passed(metrics),
            duration_ms=round((time.perf_counter() - started) * 1000),
            response=reply.text,
            response_id=reply.response_id,
            tool_calls=calls,
            before=before,
            after=after,
            metrics=metrics,
            failures=failures,
        )
    finally:
        engine.dispose()


async def run_evaluation(
    cases: list[AssistantEvalCase],
    settings: Settings,
    dataset_path: Path,
    baseline_path: Path | None = None,
) -> EvalRunReport:
    started_at = datetime.now(UTC)
    provider = OpenAIEmbeddingProvider(settings)
    backend = await InMemoryKnowledgeBackend.create(provider)
    results: list[CaseResult] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.id}", flush=True)
        try:
            result = await run_case(case, settings, backend)
        except Exception as error:
            result = _error_case_result(case, error)
        results.append(result)
        print(
            f"  {'PASS' if result.passed else 'FAIL'} overall={result.metrics.overall:.3f}",
            flush=True,
        )
    scores = _aggregate(results)
    report = EvalRunReport(
        run_id=started_at.strftime("%Y%m%dT%H%M%S%fZ"),
        started_at=started_at,
        completed_at=datetime.now(UTC),
        model=settings.openai_model,
        reasoning_effort=settings.openai_reasoning_effort,
        embedding_model=settings.openai_embedding_model,
        prompt_sha256=assistant_prompt_fingerprint(),
        dataset_sha256=hashlib.sha256(await asyncio.to_thread(dataset_path.read_bytes)).hexdigest(),
        dataset_path=str(dataset_path),
        case_count=len(results),
        passed_count=sum(result.passed for result in results),
        scores=scores,
        results=results,
    )
    if baseline_path is not None:
        baseline_json = await asyncio.to_thread(baseline_path.read_text, encoding="utf-8")
        baseline = EvalRunReport.model_validate_json(baseline_json)
        report.baseline = _compare(report, baseline, baseline_path)
    return report


def _create_eval_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_database(engine)
    return engine


def _case_passed(metrics: MetricScores) -> bool:
    return (
        metrics.overall >= _CASE_PASS_THRESHOLD
        and metrics.workflow_outcome == 1.0
        and metrics.unwanted_side_effects == 1.0
    )


def _prepare_case(session: Session, case: AssistantEvalCase) -> tuple[User, str]:
    user = User(external_subject=f"eval-{case.id}", email=f"{case.id}@eval.prepwise.local")
    session.add(user)
    session.commit()
    for item in case.setup.cart:
        meal = session.scalar(select(Meal).where(Meal.name == item.meal_name))
        assert meal is not None
        add_user_cart_item(session, user.id, meal.id, item.quantity)
    for name in case.setup.unavailable_meals:
        meal = session.scalar(select(Meal).where(Meal.name == name))
        assert meal is not None
        meal.available = False
    location = session.scalar(
        select(PickupLocation).where(
            PickupLocation.name == (case.setup.pickup_location_name or "Prepwise Grünerløkka")
        )
    )
    assert location is not None
    meal = session.scalar(select(Meal).order_by(Meal.name))
    assert meal is not None
    now = datetime.now(UTC)
    for index in range(case.setup.existing_order_count):
        session.add(
            Order(
                user_id=user.id,
                pickup_location_id=location.id,
                pickup_start_at=now + timedelta(days=index + 1),
                pickup_end_at=now + timedelta(days=index + 1, hours=2),
                pickup_location_name=location.name,
                pickup_location_address=location.address_line,
                total_nok=meal.price_nok,
            )
        )
    session.commit()
    message = case.message
    message = message.replace("{{pickup_date}}", list_pickup_options().days[0].date.isoformat())
    if case.setup.issue_order_confirmation:
        prepared = prepare_user_order_confirmation(
            session,
            user.id,
            location.id,
            f"eval-prepare-{case.id}",
            pickup_date=list_pickup_options().days[0].date,
            pickup_slot="16-18",
        )
        message = message.replace("{{confirmation_phrase}}", str(prepared["confirmation_phrase"]))
    return user, message


def _snapshot(session: Session, user_id: UUID) -> StateSnapshot:
    return StateSnapshot(
        cart_quantity=int(
            session.scalar(
                select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
                    CartItem.user_id == user_id
                )
            )
            or 0
        ),
        order_count=int(
            session.scalar(select(func.count()).select_from(Order).where(Order.user_id == user_id))
            or 0
        ),
        confirmation_count=int(
            session.scalar(
                select(func.count())
                .select_from(OrderConfirmation)
                .where(
                    OrderConfirmation.user_id == user_id,
                )
            )
            or 0
        ),
    )


def _aggregate(results: list[CaseResult]) -> AggregateScores:
    metric_values: dict[str, list[float]] = defaultdict(list)
    category_values: dict[str, list[float]] = defaultdict(list)
    for result in results:
        for name, score in result.metrics.model_dump(exclude={"overall"}).items():
            if score is not None:
                metric_values[name].append(score)
        category_values[result.category.value].append(result.metrics.overall)
    return AggregateScores(
        pass_rate=sum(result.passed for result in results) / len(results),
        mean_overall=sum(result.metrics.overall for result in results) / len(results),
        by_metric={name: sum(values) / len(values) for name, values in metric_values.items()},
        by_category={name: sum(values) / len(values) for name, values in category_values.items()},
    )


def _error_case_result(case: AssistantEvalCase, error: Exception) -> CaseResult:
    snapshot = StateSnapshot(cart_quantity=0, order_count=0, confirmation_count=0)
    metrics = MetricScores(
        tool_selection=0.0,
        workflow_outcome=0.0,
        unwanted_side_effects=0.0,
        overall=0.0,
    )
    return CaseResult(
        case_id=case.id,
        category=case.category,
        passed=False,
        duration_ms=0,
        response="",
        response_id="",
        tool_calls=[],
        before=snapshot,
        after=snapshot,
        metrics=metrics,
        failures=[
            EvalFailure(
                metric="execution",
                message="Evaluation case raised an exception",
                actual=f"{type(error).__name__}: {error}",
            )
        ],
    )


def _compare(
    current: EvalRunReport,
    baseline: EvalRunReport,
    baseline_path: Path,
) -> BaselineComparison:
    current_cases = [result.case_id for result in current.results]
    baseline_cases = [result.case_id for result in baseline.results]
    if current.dataset_sha256 != baseline.dataset_sha256:
        raise ValueError("Baseline uses a different evaluation dataset")
    if current_cases != baseline_cases:
        raise ValueError("Baseline must contain the same evaluation cases in the same order")
    shared = set(current.scores.by_metric) & set(baseline.scores.by_metric)
    return BaselineComparison(
        baseline_path=str(baseline_path),
        pass_rate_delta=current.scores.pass_rate - baseline.scores.pass_rate,
        mean_overall_delta=current.scores.mean_overall - baseline.scores.mean_overall,
        metric_deltas={
            name: current.scores.by_metric[name] - baseline.scores.by_metric[name]
            for name in sorted(shared)
        },
    )


def _arguments_dict(arguments: str | Mapping[str, object]) -> dict[str, Any]:
    if isinstance(arguments, str):
        decoded = json.loads(arguments)
        return decoded if isinstance(decoded, dict) else {"_invalid": decoded}
    return dict(arguments)


def _json_object(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    return decoded if isinstance(decoded, dict) else {"_invalid": decoded}


def _arguments_match(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    for key, value in expected.items():
        if key not in actual:
            return False
        actual_value = actual[key]
        if key == "query" and isinstance(value, str) and isinstance(actual_value, str):
            expected_tokens = set(_tokens(value))
            actual_tokens = set(_tokens(actual_value))
            if not expected_tokens <= actual_tokens and not actual_tokens <= expected_tokens:
                return False
        elif isinstance(value, (int, float)) and isinstance(actual_value, (int, float)):
            if float(value) != float(actual_value):
                return False
        elif value != actual_value:
            return False
    return True


def _mentioned_meals(response: str) -> set[str]:
    normalized = response.casefold()
    return {meal.name for meal in MEALS if meal.name.casefold() in normalized}


def _meal_satisfies(meal: MealSeed, expected: MealConstraintExpectation) -> bool:
    if (
        expected.min_protein_grams is not None
        and float(meal.protein_grams) < expected.min_protein_grams
    ):
        return False
    if (
        expected.max_calories_exclusive is not None
        and meal.calories >= expected.max_calories_exclusive
    ):
        return False
    if expected.max_price_nok is not None and float(meal.price_nok) > expected.max_price_nok:
        return False
    if set(meal.allergen_codes) & set(expected.excluded_allergens):
        return False
    return True


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _phrase_present(phrase: str, normalized_response: str) -> bool:
    normalized_phrase = _normalize(phrase)
    if normalized_phrase in normalized_response:
        return True
    tokens = _tokens(normalized_phrase)
    return (
        bool(tokens) and sum(token in normalized_response for token in tokens) / len(tokens) >= 0.8
    )


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(value)]


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeatable Prepwise assistant evaluations")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_EVAL_DATASET)
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--category", action="append", choices=[item.value for item in EvalCategory]
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model")
    parser.add_argument(
        "--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh", "max"]
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--fail-under", type=float, default=0.0)
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    return parser.parse_args()


async def _main() -> int:
    arguments = _parse_arguments()
    cases = load_assistant_eval_cases(arguments.dataset)
    if arguments.case_id:
        selected = set(arguments.case_id)
        cases = [case for case in cases if case.id in selected]
    if arguments.category:
        categories = set(arguments.category)
        cases = [case for case in cases if case.category.value in categories]
    if arguments.limit is not None:
        cases = cases[: arguments.limit]
    if not cases:
        raise SystemExit("No evaluation cases matched the filters")
    settings = get_settings()
    overrides: dict[str, object] = {}
    if arguments.model:
        overrides["openai_model"] = arguments.model
    if arguments.reasoning_effort:
        overrides["openai_reasoning_effort"] = arguments.reasoning_effort
    if overrides:
        settings = settings.model_copy(update=overrides)
    report = await run_evaluation(cases, settings, arguments.dataset, arguments.baseline)
    await asyncio.to_thread(arguments.output_dir.mkdir, parents=True, exist_ok=True)
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "-", report.model)
    output_path = arguments.output_dir / f"{report.run_id}_{safe_model}.json"
    await asyncio.to_thread(
        output_path.write_text,
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(
        f"Saved {output_path} | pass_rate={report.scores.pass_rate:.3f} "
        f"mean_overall={report.scores.mean_overall:.3f}"
    )
    failed_threshold = (
        report.scores.mean_overall < arguments.fail_under
        or report.scores.pass_rate < arguments.min_pass_rate
    )
    return 1 if failed_threshold else 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
