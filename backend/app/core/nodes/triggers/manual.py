"""Manual trigger node — passthrough for user-initiated executions."""

from __future__ import annotations

from typing import Any

import structlog

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)


class ManualTriggerNode(BaseNode):
    """Manual trigger: passes the caller-supplied trigger_data straight through."""

    node_type = NodeType.MANUAL

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        logger.info(
            "manual.trigger",
            execution_id=context.execution_id,
            user_id=context.user_id,
        )
        return NodeOutput(
            data={
                "trigger": "manual",
                "triggered_by": context.user_id,
                "trigger_data": input_data,
            }
        )


registry.register(ManualTriggerNode())
