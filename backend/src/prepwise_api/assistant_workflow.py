import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from prepwise_api.assistant_tools import AssistantToolOperation
from prepwise_api.schemas.assistant_tools import AssistantToolError, AssistantToolResult

_CART_WRITE_TOOLS = frozenset({"add_to_cart", "remove_from_cart"})
_CART_VERIFICATION_TOOL = "get_cart"


@dataclass(slots=True)
class AssistantWorkflowState:
    """Track bounded workflow invariants without persisting customer content."""

    cart_verification_required: bool = False
    expected_failure_count: int = 0
    repeated_failure_count: int = 0
    forced_verification_count: int = 0
    write_call_count: int = 0
    _failed_calls: set[str] = field(default_factory=set)

    @property
    def required_verification_tool(self) -> str | None:
        if self.cart_verification_required:
            return _CART_VERIFICATION_TOOL
        return None

    def repeated_failure_output(
        self,
        name: str,
        arguments: str | Mapping[str, object],
    ) -> str | None:
        if _call_fingerprint(name, arguments) not in self._failed_calls:
            return None
        self.repeated_failure_count += 1
        return AssistantToolResult(
            ok=False,
            error=AssistantToolError(
                code="repeated_tool_failure",
                message=(
                    "This exact tool call already failed; change the plan or report the failure"
                ),
            ),
        ).model_dump_json(exclude_none=True)

    def record_tool_result(
        self,
        name: str,
        arguments: str | Mapping[str, object],
        output: str,
        *,
        operation: AssistantToolOperation = AssistantToolOperation.READ,
    ) -> None:
        if operation is AssistantToolOperation.WRITE:
            self.write_call_count += 1
        succeeded = _tool_result_succeeded(output)
        if not succeeded:
            self.expected_failure_count += 1
            self._failed_calls.add(_call_fingerprint(name, arguments))

        if name in _CART_WRITE_TOOLS:
            self.cart_verification_required = True
        elif name == _CART_VERIFICATION_TOOL and succeeded:
            self.cart_verification_required = False

    def record_forced_verification(self) -> None:
        self.forced_verification_count += 1


def _call_fingerprint(name: str, arguments: str | Mapping[str, object]) -> str:
    if isinstance(arguments, str):
        try:
            payload: object = json.loads(arguments)
        except json.JSONDecodeError:
            normalized = arguments
        else:
            normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    else:
        normalized = json.dumps(dict(arguments), sort_keys=True, separators=(",", ":"))
    return f"{name}:{normalized}"


def _tool_result_succeeded(output: str) -> bool:
    try:
        payload: object = json.loads(output)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("ok") is True
