"""
Condition node — routes execution down "true" or "false" branches based on
a configurable comparison.

Config schema::

    {
        "field": "data.user.age",        # dot-notation into input_data
        "operator": "greater_than",       # one of the supported operators
        "value": 18                       # value to compare against
    }
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

import structlog

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)

_SUPPORTED_OPERATORS: frozenset[str] = frozenset(
    {
        "equals",
        "not_equals",
        "contains",
        "not_contains",
        "greater_than",
        "less_than",
        "regex_match",
        "is_empty",
        "is_not_empty",
        "starts_with",
        "ends_with",
    }
)

_SENTINEL = object()


def _resolve_path(data: Any, dotted_path: str) -> Any:
    """Resolve a dot-notation path against arbitrarily nested data.

    Returns ``None`` if any segment is missing. Supports numeric indices for
    lists (e.g. ``"items.0.name"``).
    """
    if not dotted_path:
        return data
    current: Any = data
    for segment in dotted_path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(segment, _SENTINEL)
            if current is _SENTINEL:
                return None
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(segment)
            except ValueError:
                return None
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
        else:
            return None
    return current


def _is_empty(value: Any) -> bool:
    """Treat None, empty string, empty list/dict/tuple/set as empty."""
    if value is None:
        return True
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) == 0
    return False


def _coerce_numeric(a: Any, b: Any) -> tuple[Any, Any]:
    """Best-effort numeric coercion for ordered comparisons."""
    try:
        return float(a), float(b)
    except (TypeError, ValueError):
        return a, b


def _evaluate(operator: str, actual: Any, expected: Any) -> bool:
    """Evaluate a single comparison; never raises for type mismatches."""
    if operator == "is_empty":
        return _is_empty(actual)
    if operator == "is_not_empty":
        return not _is_empty(actual)

    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected

    if operator == "contains":
        try:
            return expected in actual  # type: ignore[operator]
        except TypeError:
            return False
    if operator == "not_contains":
        try:
            return expected not in actual  # type: ignore[operator]
        except TypeError:
            return True

    if operator in ("greater_than", "less_than"):
        a, b = _coerce_numeric(actual, expected)
        try:
            if operator == "greater_than":
                return a > b  # type: ignore[operator]
            return a < b  # type: ignore[operator]
        except TypeError:
            return False

    if operator == "regex_match":
        if actual is None or expected is None:
            return False
        try:
            return re.search(str(expected), str(actual)) is not None
        except re.error:
            return False

    if operator == "starts_with":
        if actual is None or expected is None:
            return False
        try:
            return str(actual).startswith(str(expected))
        except (TypeError, ValueError):
            return False
    if operator == "ends_with":
        if actual is None or expected is None:
            return False
        try:
            return str(actual).endswith(str(expected))
        except (TypeError, ValueError):
            return False

    # Should be unreachable thanks to validate_config.
    raise ValueError(f"Unsupported operator: {operator}")


class ConditionNode(BaseNode):
    """A logic node that routes execution down the ``"true"`` or ``"false"`` branch."""

    node_type: ClassVar[NodeType] = NodeType.CONDITION

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate the condition configuration.

        Raises:
            ValueError: If operator is missing or unsupported, or if field is missing
                for operators that require it.
        """
        operator = config.get("operator")
        if not operator:
            raise ValueError("ConditionNode config requires 'operator'")
        if operator not in _SUPPORTED_OPERATORS:
            raise ValueError(
                f"ConditionNode unsupported operator: {operator!r}. "
                f"Supported: {sorted(_SUPPORTED_OPERATORS)}"
            )
        if "field" not in config:
            raise ValueError("ConditionNode config requires 'field'")

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        """Evaluate the condition and pass input through on the matching branch."""
        self.validate_config(config)
        field: str = config["field"]
        operator: str = config["operator"]
        expected: Any = config.get("value")

        actual = _resolve_path(input_data, field)
        result = _evaluate(operator, actual, expected)
        branch = "true" if result else "false"

        context.logger.debug(
            "condition.evaluated",
            extra={
                "execution_id": context.execution_id,
                "field": field,
                "operator": operator,
                "actual": actual,
                "expected": expected,
                "branch": branch,
            },
        )

        return NodeOutput(
            data=input_data,
            branch=branch,
            metadata={
                "field": field,
                "operator": operator,
                "evaluated": result,
            },
        )


# Auto-register on import.
registry.register(ConditionNode())
