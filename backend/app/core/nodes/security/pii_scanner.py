"""
PIIScannerNode — workflow node wrapping SecurityEngine.scan_pii.

Config schema::

    {
        "scan_fields": ["data.message", "data.email"],
        "action": "redact" | "block" | "alert",
        "fail_on_detection": false
    }

Behaviour:
- Resolves each configured field via dot-notation into ``input_data``.
- Scans every resolved string with the security engine.
- If ``action == "redact"``: writes redacted text back into the output.
- If ``action == "block"`` and any PII is found: emits ``blocked_pii`` flag
  on a "blocked" branch and stops the data from propagating.
- ``fail_on_detection``: when True, sets ``branch="error"`` (the engine
  treats this as a failure) instead of a normal block.

Always returns scan results under ``output.metadata["pii_results"]``.
"""

from __future__ import annotations

import copy
from typing import Any, ClassVar

from app.core.nodes.base import BaseNode, registry
from app.core.security_engine import security_engine
from app.shared_types import ExecutionContext, NodeOutput, NodeType


def _resolve_path(data: dict[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve ``"a.b.c"`` style paths against ``data``.

    A leading ``"data."`` segment is stripped because callers conventionally
    write paths relative to the workflow's ``data`` key.
    """
    if not path:
        return False, None
    segments = path.split(".")
    if segments and segments[0] == "data":
        segments = segments[1:]
    cur: Any = data
    for seg in segments:
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        elif isinstance(cur, list):
            try:
                cur = cur[int(seg)]
            except (ValueError, IndexError):
                return False, None
        else:
            return False, None
    return True, cur


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    """Set ``"a.b.c"`` style path inside ``data`` (in place)."""
    segments = path.split(".")
    if segments and segments[0] == "data":
        segments = segments[1:]
    if not segments:
        return
    cur: Any = data
    for seg in segments[:-1]:
        if isinstance(cur, dict):
            cur = cur.setdefault(seg, {})
        else:
            return
    if isinstance(cur, dict):
        cur[segments[-1]] = value


class PIIScannerNode(BaseNode):
    """Standalone PII-scanning node for workflows."""

    node_type: ClassVar[NodeType] = NodeType.PII_SCANNER

    def validate_config(self, config: dict[str, Any]) -> None:
        action = config.get("action", "alert")
        if action not in ("redact", "block", "alert"):
            raise ValueError(
                f"PIIScannerNode action must be one of redact/block/alert (got {action!r})"
            )

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        self.validate_config(config)

        scan_fields: list[str] = list(config.get("scan_fields") or [])
        action: str = config.get("action", "alert")
        fail_on_detection: bool = bool(config.get("fail_on_detection", False))

        # Default: if no fields specified, scan every top-level string in input_data.
        if not scan_fields:
            scan_fields = [
                f"data.{k}" for k, v in input_data.items() if isinstance(v, str)
            ]

        output_data: dict[str, Any] = copy.deepcopy(input_data)
        results_by_field: dict[str, dict[str, Any]] = {}
        any_pii = False
        flags: list[str] = []

        for field in scan_fields:
            found, value = _resolve_path(input_data, field)
            if not found or not isinstance(value, str) or not value:
                continue
            scan = await security_engine.scan_pii(value)
            results_by_field[field] = scan.model_dump()
            if scan.has_pii:
                any_pii = True
                if action == "redact":
                    _set_path(output_data, field, scan.redacted_text)

        if any_pii:
            flags.append("pii_detected")

        if any_pii and action == "block":
            return NodeOutput(
                data=output_data,
                branch="blocked",
                metadata={"pii_results": results_by_field, "action": action},
                security_flags=flags + ["blocked_pii"],
            )

        if any_pii and fail_on_detection:
            return NodeOutput(
                data=output_data,
                branch="error",
                metadata={
                    "pii_results": results_by_field,
                    "action": action,
                    "error": "PII detected and fail_on_detection=True",
                },
                security_flags=flags,
            )

        return NodeOutput(
            data=output_data,
            branch="output",
            metadata={"pii_results": results_by_field, "action": action},
            security_flags=flags,
        )


registry.register(PIIScannerNode())
