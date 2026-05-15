"""
HumanGateNode — pause execution until a human approves via the API.

State machine:
1. On execute, generate a ``gate_id`` and persist gate state in Redis under
   ``human_gate:{gate_id}`` (TTL = ``timeout_hours``).
2. Publish a ``HUMAN_GATE_WAITING`` WebSocket event so the UI can show a
   pending approval card.
3. Poll Redis at ``human_gate:{gate_id}:decision`` every 5 seconds. The
   API endpoint ``POST /api/gates/{gate_id}/approve`` writes the decision.
4. On approval / rejection, route via the appropriate branch
   (``approved`` / ``rejected``). On timeout, branch ``timeout`` with
   ``gate_timeout`` flag.

The polling loop uses ``asyncio.sleep`` so the worker can yield to other
coroutines; the engine is async throughout.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, ClassVar
from uuid import uuid4

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType, WSEventType


_POLL_INTERVAL_SECONDS = 5.0


class HumanGateNode(BaseNode):
    """Workflow node that blocks until an external human decision is made."""

    node_type: ClassVar[NodeType] = NodeType.HUMAN_GATE

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("approvers"):
            raise ValueError("HumanGateNode requires 'approvers' in config")

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        self.validate_config(config)

        gate_id = str(uuid4())
        approvers_raw = config["approvers"]
        approvers: list[str] = [
            a.strip() for a in str(approvers_raw).split(",") if a.strip()
        ]
        timeout_hours = float(config.get("timeout_hours", 24))
        timeout_seconds = max(int(timeout_hours * 3600), 1)
        message = config.get("message", "")

        gate_data: dict[str, Any] = {
            "gate_id": gate_id,
            "execution_id": context.execution_id,
            "workflow_id": context.workflow_id,
            "node_id": config.get("_node_id"),  # engine may inject this
            "input_data": input_data,
            "approvers": approvers,
            "message": message,
            "status": "waiting",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Persist gate state in Redis.
        await context.redis.setex(
            f"human_gate:{gate_id}",
            timeout_seconds,
            json.dumps(gate_data),
        )

        # 2. Notify the UI.
        await context.publish_event(
            WSEventType.HUMAN_GATE_WAITING.value,
            {
                "gate_id": gate_id,
                "approvers": approvers,
                "message": message,
                "timeout_seconds": timeout_seconds,
            },
        )
        context.logger.info(
            "human_gate.waiting",
            extra={
                "execution_id": context.execution_id,
                "gate_id": gate_id,
                "approvers": approvers,
            },
        )

        # 3. Poll for a decision.
        decision_key = f"human_gate:{gate_id}:decision"
        start = time.monotonic()
        while (time.monotonic() - start) < timeout_seconds:
            raw = await context.redis.get(decision_key)
            if raw:
                try:
                    decision = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
                except (ValueError, AttributeError):
                    decision = {"approved": False, "reason": "Malformed decision payload"}

                # Mark the gate as resolved so it disappears from any pending lists.
                try:
                    await context.redis.delete(f"human_gate:{gate_id}")
                    await context.redis.delete(decision_key)
                except Exception:  # noqa: BLE001
                    pass

                if decision.get("approved"):
                    return NodeOutput(
                        data=input_data,
                        branch="approved",
                        metadata={
                            "gate_id": gate_id,
                            "approved_by": decision.get("approved_by"),
                            "approved_at": decision.get("approved_at", datetime.now(timezone.utc).isoformat()),
                            "comment": decision.get("comment", ""),
                        },
                    )
                return NodeOutput(
                    data=input_data,
                    branch="rejected",
                    metadata={
                        "gate_id": gate_id,
                        "rejected_by": decision.get("approved_by") or decision.get("rejected_by"),
                        "reason": decision.get("reason", ""),
                        "rejected_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

        # 4. Timeout.
        try:
            await context.redis.delete(f"human_gate:{gate_id}")
        except Exception:  # noqa: BLE001
            pass
        context.logger.warning(
            "human_gate.timeout",
            extra={"execution_id": context.execution_id, "gate_id": gate_id},
        )
        return NodeOutput(
            data=input_data,
            branch="timeout",
            metadata={"gate_id": gate_id, "timeout_seconds": timeout_seconds},
            security_flags=["gate_timeout"],
        )


registry.register(HumanGateNode())
