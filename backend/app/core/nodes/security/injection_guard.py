"""
InjectionGuardNode — block prompt-injection content before it reaches an LLM.

Config schema::

    {
        "scan_field": "data.user_input",
        "threshold": 0.7
    }

Branches:
- ``"safe"``:    risk_score < threshold. Input data is passed through unchanged.
- ``"blocked"``: risk_score >= threshold. ``security_flags`` contains
                 ``"injection_blocked"`` and downstream nodes should not run.

Metadata always carries the full :class:`InjectionScanResult` so audit log
writers can persist patterns_matched, risk_score, etc.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.core.nodes.base import BaseNode, registry
from app.core.nodes.security.pii_scanner import _resolve_path
from app.core.security_engine import security_engine
from app.shared_types import ExecutionContext, NodeOutput, NodeType


class InjectionGuardNode(BaseNode):
    """Workflow node that blocks prompt-injection content above a threshold."""

    node_type: ClassVar[NodeType] = NodeType.INJECTION_GUARD

    def validate_config(self, config: dict[str, Any]) -> None:
        threshold = float(config.get("threshold", 0.7))
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("InjectionGuardNode 'threshold' must be in [0, 1]")

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        self.validate_config(config)

        threshold = float(config.get("threshold", 0.7))
        scan_field: str = config.get("scan_field", "data.user_input")

        found, value = _resolve_path(input_data, scan_field)
        if not found or not isinstance(value, str):
            # Nothing to scan — pass through, no flag.
            empty = await security_engine.scan_injection("")
            return NodeOutput(
                data=input_data,
                branch="safe",
                metadata={
                    "injection_scan": empty.model_dump(),
                    "scan_field": scan_field,
                    "note": "scan_field not present or non-string; pass-through",
                },
            )

        scan = await security_engine.scan_injection(value)
        blocked = scan.risk_score >= threshold or not scan.is_safe

        if blocked:
            context.logger.warning(
                "injection_guard.blocked",
                extra={
                    "execution_id": context.execution_id,
                    "risk_score": scan.risk_score,
                    "patterns": scan.patterns_matched,
                    "field": scan_field,
                },
            )
            return NodeOutput(
                data=input_data,
                branch="blocked",
                metadata={
                    "injection_scan": scan.model_dump(),
                    "scan_field": scan_field,
                    "threshold": threshold,
                },
                security_flags=["injection_blocked"],
            )

        return NodeOutput(
            data=input_data,
            branch="safe",
            metadata={
                "injection_scan": scan.model_dump(),
                "scan_field": scan_field,
                "threshold": threshold,
            },
        )


registry.register(InjectionGuardNode())
