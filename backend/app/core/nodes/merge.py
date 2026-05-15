"""
Merge node — combines outputs from multiple upstream branches.

The engine resolves merge-node input as a dict keyed by the upstream node id::

    {
        "<upstream_node_id_1>": <NodeOutput.data dict>,
        "<upstream_node_id_2>": <NodeOutput.data dict>,
        ...
    }

Supported ``mode`` values:

- ``"merge_objects"`` (default): dict.update in arrival order — later upstream
  ids win on key conflicts.
- ``"concat_arrays"``: For each upstream value, if it's a list, extend the
  result list; if it's a dict with an ``items`` list, extend by those; else
  append the value.
- ``"first"``: Return the first upstream's data unchanged.
- ``"last"``: Return the last upstream's data unchanged.
- ``"all"``: Return ``{"items": [<each upstream's data>]}``.
"""

from __future__ import annotations

from typing import Any, ClassVar

import structlog

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)

_SUPPORTED_MODES: frozenset[str] = frozenset(
    {"merge_objects", "concat_arrays", "first", "last", "all"}
)


def _is_branch_payload(input_data: dict[str, Any]) -> bool:
    """Heuristic: treat input as a per-branch payload only when every value is a dict."""
    if not input_data:
        return False
    return all(isinstance(v, dict) for v in input_data.values())


class MergeNode(BaseNode):
    """Merge multiple upstream node outputs into a single payload."""

    node_type: ClassVar[NodeType] = NodeType.MERGE

    def validate_config(self, config: dict[str, Any]) -> None:
        mode = config.get("mode", "merge_objects")
        if mode not in _SUPPORTED_MODES:
            raise ValueError(
                f"MergeNode unsupported mode: {mode!r}. Supported: {sorted(_SUPPORTED_MODES)}"
            )

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        """Merge the per-branch input dict into a single output dict."""
        self.validate_config(config)
        mode: str = config.get("mode", "merge_objects")

        # If the engine handed us a per-branch payload, iterate values in order.
        if _is_branch_payload(input_data):
            branches: list[dict[str, Any]] = list(input_data.values())
        else:
            # Single-branch fall-through: treat the entire input as one upstream.
            branches = [input_data] if input_data else []

        merged: dict[str, Any]

        if not branches:
            merged = {}
        elif mode == "merge_objects":
            merged = {}
            for branch in branches:
                merged.update(branch)
        elif mode == "concat_arrays":
            collected: list[Any] = []
            for branch in branches:
                if isinstance(branch, list):
                    collected.extend(branch)
                elif isinstance(branch, dict) and isinstance(branch.get("items"), list):
                    collected.extend(branch["items"])
                else:
                    collected.append(branch)
            merged = {"items": collected}
        elif mode == "first":
            merged = dict(branches[0])
        elif mode == "last":
            merged = dict(branches[-1])
        elif mode == "all":
            merged = {"items": list(branches)}
        else:  # pragma: no cover - validate_config blocks this
            raise ValueError(f"MergeNode unsupported mode: {mode!r}")

        context.logger.debug(
            "merge.executed",
            extra={
                "execution_id": context.execution_id,
                "mode": mode,
                "branch_count": len(branches),
            },
        )

        return NodeOutput(
            data=merged,
            branch="output",
            metadata={"mode": mode, "branch_count": len(branches)},
        )


# Auto-register on import.
registry.register(MergeNode())
