"""
Workflow execution engine.

Executes a workflow DAG with real async parallelism:

1. Build an adjacency list and in-degree map from the workflow edges.
2. Schedule all in-degree-zero nodes (start nodes) for execution.
3. Run all currently-ready nodes concurrently via ``asyncio.gather``.
4. After a node completes:
   - For condition nodes, only follow downstream edges whose
     ``source_handle`` matches ``output.branch`` ("true" / "false").
   - Decrement the in-degree of each followed downstream node.
   - For non-followed branches, mark all transitively unreachable downstream
     nodes as SKIPPED so the DAG can drain.
5. Repeat until the queue empties or a failure aborts the run.

The engine never silently swallows errors — every exception is logged with
``execution_id`` bound to the log line and either propagated, converted into
a ``NODE_FAILED`` event, or surfaced via the returned ``ExecutionStatus``.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from app.core.nodes.base import NodeRegistry
from app.shared_types import (
    ExecutionContext,
    ExecutionStatus,
    NodeOutput,
    NodeStatus,
    NodeType,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WSEventType,
)

logger = structlog.get_logger(__name__)

_TRIGGER_TYPES: frozenset[NodeType] = frozenset(
    {NodeType.WEBHOOK, NodeType.SCHEDULE, NodeType.MANUAL}
)


class NodeExecutionError(Exception):
    """Raised when a node fails after exhausting retries."""

    def __init__(
        self,
        node_id: str,
        node_name: str,
        message: str,
        *,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(f"Node {node_id} ({node_name}) failed: {message}")
        self.node_id = node_id
        self.node_name = node_name
        self.message = message
        self.__cause__ = cause


class WorkflowEngine:
    """Production-grade async workflow DAG executor."""

    def __init__(self, redis: Any, node_registry: NodeRegistry) -> None:
        self.redis = redis
        self.registry = node_registry
        self._log = logger.bind(component="WorkflowEngine")

    # ── Public API ─────────────────────────────────────────────────────────

    async def execute(
        self,
        workflow: WorkflowDefinition,
        workflow_id: str,
        execution_id: str,
        trigger_data: dict[str, Any],
        context: ExecutionContext,
    ) -> ExecutionStatus:
        """Execute a workflow DAG. Returns the final :class:`ExecutionStatus`."""
        log = self._log.bind(execution_id=execution_id, workflow_id=workflow_id)
        log.info("engine.execution.start", node_count=len(workflow.nodes))

        nodes_by_id: dict[str, WorkflowNode] = {n.id: n for n in workflow.nodes}
        adjacency = self._build_dag(workflow)
        in_degree = self._build_in_degree(workflow)
        outgoing_edges: dict[str, list[WorkflowEdge]] = defaultdict(list)
        for edge in workflow.edges:
            outgoing_edges[edge.source].append(edge)

        outputs: dict[str, NodeOutput] = {}
        statuses: dict[str, NodeStatus] = {nid: NodeStatus.PENDING for nid in nodes_by_id}
        skipped_edges: set[str] = set()  # edge ids that should NOT be traversed

        ready: deque[str] = deque(self._get_start_nodes(workflow))
        if not ready:
            log.warning("engine.execution.no_start_nodes")
            await self._publish(
                context,
                WSEventType.EXECUTION_FAILED,
                {"error": "Workflow has no start nodes (cycle or empty graph)"},
            )
            return ExecutionStatus.FAILED

        failure: Optional[BaseException] = None

        try:
            while ready:
                # Snapshot all currently-ready nodes for this parallel wave.
                wave_ids = list(ready)
                ready.clear()
                wave_nodes = [nodes_by_id[nid] for nid in wave_ids]

                log.debug("engine.wave.start", wave_size=len(wave_nodes))

                # Mark all wave members RUNNING (or SKIPPED for disabled) before launching.
                coros = []
                for node in wave_nodes:
                    coros.append(
                        self._run_node_safely(
                            node=node,
                            workflow=workflow,
                            outputs=outputs,
                            skipped_edges=skipped_edges,
                            trigger_data=trigger_data,
                            context=context,
                            log=log,
                        )
                    )

                results = await asyncio.gather(*coros, return_exceptions=True)

                # Process results sequentially to update DAG bookkeeping
                # deterministically.
                for node, result in zip(wave_nodes, results):
                    if isinstance(result, BaseException):
                        failure = result
                        statuses[node.id] = NodeStatus.FAILED
                        log.error(
                            "engine.node.failed",
                            node_id=node.id,
                            error=str(result),
                        )
                        # Bubble up; the finally block publishes the failure event.
                        raise result

                    node_output, node_status = result  # type: ignore[misc]
                    outputs[node.id] = node_output
                    statuses[node.id] = node_status

                    self._propagate(
                        node=node,
                        output=node_output,
                        outgoing_edges=outgoing_edges,
                        in_degree=in_degree,
                        skipped_edges=skipped_edges,
                        nodes_by_id=nodes_by_id,
                        statuses=statuses,
                        ready=ready,
                    )

            # Reached drain — every node is either SUCCESS, SKIPPED, or unreachable.
            await self._publish(
                context,
                WSEventType.EXECUTION_COMPLETED,
                {
                    "status": ExecutionStatus.SUCCESS.value,
                    "node_count": len(outputs),
                },
            )
            log.info("engine.execution.success", completed=len(outputs))
            return ExecutionStatus.SUCCESS

        except asyncio.CancelledError:
            log.warning("engine.execution.cancelled")
            await self._publish(
                context,
                WSEventType.EXECUTION_FAILED,
                {"status": ExecutionStatus.CANCELLED.value, "reason": "cancelled"},
            )
            return ExecutionStatus.CANCELLED

        except NodeExecutionError as exc:
            log.error(
                "engine.execution.failed",
                node_id=exc.node_id,
                error=exc.message,
            )
            await self._publish(
                context,
                WSEventType.EXECUTION_FAILED,
                {
                    "status": ExecutionStatus.FAILED.value,
                    "failed_node_id": exc.node_id,
                    "failed_node_name": exc.node_name,
                    "error": exc.message,
                },
            )
            return ExecutionStatus.FAILED

        except Exception as exc:
            log.exception("engine.execution.unexpected_error", error=str(exc))
            await self._publish(
                context,
                WSEventType.EXECUTION_FAILED,
                {"status": ExecutionStatus.FAILED.value, "error": repr(exc)},
            )
            return ExecutionStatus.FAILED

    async def cancel_execution(self, execution_id: str) -> None:
        """Publish a cancel signal to the execution's Redis channel.

        Subscribers (worker tasks running ``execute``) should observe this and
        translate it into ``asyncio.CancelledError`` for the running coroutine.
        """
        import json

        channel = f"executions:{execution_id}"
        payload = json.dumps({"type": "cancel", "execution_id": execution_id})
        self._log.info("engine.cancel.publish", execution_id=execution_id)
        await self.redis.publish(channel, payload)

    # ── DAG construction helpers ───────────────────────────────────────────

    def _build_dag(self, definition: WorkflowDefinition) -> dict[str, list[str]]:
        """Return an adjacency list mapping ``node_id`` to downstream ids."""
        adjacency: dict[str, list[str]] = {n.id: [] for n in definition.nodes}
        for edge in definition.edges:
            if edge.source in adjacency:
                adjacency[edge.source].append(edge.target)
        return adjacency

    def _build_in_degree(self, definition: WorkflowDefinition) -> dict[str, int]:
        """Return a mapping of ``node_id`` to its incoming-edge count."""
        in_degree: dict[str, int] = {n.id: 0 for n in definition.nodes}
        for edge in definition.edges:
            if edge.target in in_degree:
                in_degree[edge.target] += 1
        return in_degree

    def _get_start_nodes(self, definition: WorkflowDefinition) -> list[str]:
        """Return node ids that have no incoming edges."""
        targets = {edge.target for edge in definition.edges}
        return [n.id for n in definition.nodes if n.id not in targets]

    # ── Input resolution ───────────────────────────────────────────────────

    def _resolve_input(
        self,
        node: WorkflowNode,
        edges: list[WorkflowEdge],
        outputs: dict[str, NodeOutput],
        trigger_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Collect outputs from upstream nodes into a single input dict.

        - Trigger nodes (no upstreams) receive ``trigger_data`` verbatim.
        - Merge nodes get a dict keyed by upstream node id so they can decide
          how to combine branches.
        - All other nodes:
            * One upstream → upstream output passed through.
            * Multiple upstreams → outputs merged via ``dict.update`` in edge
              declaration order; ties broken by later edges.
        """
        upstream_edges = [e for e in edges if e.target == node.id]
        if not upstream_edges:
            return dict(trigger_data) if isinstance(trigger_data, dict) else {"value": trigger_data}

        if node.type == NodeType.MERGE:
            return {
                e.source: outputs[e.source].data
                for e in upstream_edges
                if e.source in outputs
            }

        if len(upstream_edges) == 1:
            src = upstream_edges[0].source
            if src in outputs:
                # Shallow copy so the node cannot mutate upstream state.
                return dict(outputs[src].data)
            return {}

        merged: dict[str, Any] = {}
        for edge in upstream_edges:
            if edge.source in outputs:
                merged.update(outputs[edge.source].data)
        return merged

    # ── Single node execution ──────────────────────────────────────────────

    async def _run_node_safely(
        self,
        *,
        node: WorkflowNode,
        workflow: WorkflowDefinition,
        outputs: dict[str, NodeOutput],
        skipped_edges: set[str],
        trigger_data: dict[str, Any],
        context: ExecutionContext,
        log: Any,
    ) -> tuple[NodeOutput, NodeStatus]:
        """Resolve input, run the node, and return ``(output, status)``."""
        # Skip propagation may have already marked this node SKIPPED; we still
        # need an output to feed downstream merges. Disabled and skipped nodes
        # pass through input.
        input_data = self._resolve_input(node, workflow.edges, outputs, trigger_data)

        if node.disabled:
            log.info("engine.node.disabled", node_id=node.id, name=node.name)
            await self._publish_node_event(
                context,
                WSEventType.NODE_STARTED,
                node,
                {"status": NodeStatus.SKIPPED.value, "reason": "disabled"},
            )
            output = NodeOutput(
                data=input_data,
                branch="output",
                metadata={"skipped": True, "reason": "disabled"},
            )
            await self._publish_node_event(
                context,
                WSEventType.NODE_COMPLETED,
                node,
                {"status": NodeStatus.SKIPPED.value},
            )
            return output, NodeStatus.SKIPPED

        output = await self._execute_single_node(node, input_data, context)
        return output, NodeStatus.SUCCESS

    async def _execute_single_node(
        self,
        node: WorkflowNode,
        input_data: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        """Execute a single node with timeout + retry + event publishing.

        Raises:
            NodeExecutionError: After all retries are exhausted.
        """
        log = self._log.bind(
            execution_id=context.execution_id,
            node_id=node.id,
            node_name=node.name,
            node_type=node.type.value,
        )

        timeout_seconds: float = float(node.config.get("timeout_seconds", 60))
        max_retries: int = int(node.config.get("retry", 0))
        attempts = max_retries + 1

        try:
            node_impl = self.registry.get(node.type)
        except KeyError as exc:
            msg = f"No implementation registered for node type {node.type.value!r}"
            log.error("engine.node.unregistered", error=msg)
            await self._publish_node_event(
                context,
                WSEventType.NODE_FAILED,
                node,
                {"error": msg, "attempts": 0},
            )
            raise NodeExecutionError(node.id, node.name, msg, cause=exc) from exc

        last_exc: Optional[BaseException] = None

        for attempt in range(1, attempts + 1):
            started_at = datetime.now(timezone.utc)
            start_perf = time.perf_counter()

            await self._publish_node_event(
                context,
                WSEventType.NODE_STARTED,
                node,
                {
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "started_at": started_at.isoformat(),
                },
            )

            try:
                await node_impl.on_before_execute(input_data, node.config, context)
                output: NodeOutput = await asyncio.wait_for(
                    node_impl.execute(input_data, node.config, context),
                    timeout=timeout_seconds,
                )
                await node_impl.on_after_execute(output, context)

                duration_ms = int((time.perf_counter() - start_perf) * 1000)
                completed_at = datetime.now(timezone.utc)

                log.info(
                    "engine.node.completed",
                    attempt=attempt,
                    duration_ms=duration_ms,
                    branch=output.branch,
                )
                await self._publish_node_event(
                    context,
                    WSEventType.NODE_COMPLETED,
                    node,
                    {
                        "attempt": attempt,
                        "started_at": started_at.isoformat(),
                        "completed_at": completed_at.isoformat(),
                        "duration_ms": duration_ms,
                        "branch": output.branch,
                        "security_flags": output.security_flags,
                    },
                )
                return output

            except asyncio.CancelledError:
                log.warning("engine.node.cancelled", attempt=attempt)
                raise

            except asyncio.TimeoutError as exc:
                duration_ms = int((time.perf_counter() - start_perf) * 1000)
                last_exc = exc
                msg = f"Timed out after {timeout_seconds}s"
                log.warning(
                    "engine.node.timeout",
                    attempt=attempt,
                    duration_ms=duration_ms,
                    timeout_seconds=timeout_seconds,
                )
                await self._publish_node_event(
                    context,
                    WSEventType.NODE_FAILED,
                    node,
                    {
                        "attempt": attempt,
                        "max_attempts": attempts,
                        "error": msg,
                        "error_type": "timeout",
                        "duration_ms": duration_ms,
                    },
                )

            except Exception as exc:
                duration_ms = int((time.perf_counter() - start_perf) * 1000)
                last_exc = exc
                log.warning(
                    "engine.node.error",
                    attempt=attempt,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                    duration_ms=duration_ms,
                )
                await self._publish_node_event(
                    context,
                    WSEventType.NODE_FAILED,
                    node,
                    {
                        "attempt": attempt,
                        "max_attempts": attempts,
                        "error": str(exc),
                        "error_type": exc.__class__.__name__,
                        "duration_ms": duration_ms,
                    },
                )

            # Backoff before retrying (skip after the last attempt).
            if attempt < attempts:
                backoff = self._backoff_seconds(attempt)
                log.debug(
                    "engine.node.retry_backoff",
                    attempt=attempt,
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)

        # Exhausted all attempts.
        final_msg = (
            f"Failed after {attempts} attempt(s): "
            f"{last_exc.__class__.__name__ if last_exc else 'UnknownError'}: {last_exc}"
        )
        raise NodeExecutionError(node.id, node.name, final_msg, cause=last_exc)

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        """Exponential backoff with jitter: ``min(2^(attempt-1), 30) + jitter``."""
        base = min(2 ** (attempt - 1), 30)
        jitter = random.uniform(0, 0.25)
        return float(base) + jitter

    # ── DAG propagation ────────────────────────────────────────────────────

    def _propagate(
        self,
        *,
        node: WorkflowNode,
        output: NodeOutput,
        outgoing_edges: dict[str, list[WorkflowEdge]],
        in_degree: dict[str, int],
        skipped_edges: set[str],
        nodes_by_id: dict[str, WorkflowNode],
        statuses: dict[str, NodeStatus],
        ready: deque[str],
    ) -> None:
        """Decrement downstream in-degrees and enqueue newly ready nodes.

        For condition nodes, only edges whose ``source_handle`` matches
        ``output.branch`` are followed; the other branch's edges are recorded
        in ``skipped_edges`` and their downstream subtrees are recursively
        drained so we don't deadlock.
        """
        edges = outgoing_edges.get(node.id, [])
        if not edges:
            return

        follow_branch: Optional[str] = None
        if node.type == NodeType.CONDITION:
            follow_branch = output.branch  # "true" or "false"

        for edge in edges:
            if follow_branch is not None and edge.source_handle != follow_branch:
                # Don't follow this branch; drain it.
                self._drain_subtree(
                    edge=edge,
                    outgoing_edges=outgoing_edges,
                    in_degree=in_degree,
                    skipped_edges=skipped_edges,
                    nodes_by_id=nodes_by_id,
                    statuses=statuses,
                    ready=ready,
                )
                continue

            target = edge.target
            if target not in in_degree:
                continue
            in_degree[target] -= 1
            if in_degree[target] <= 0 and statuses.get(target) == NodeStatus.PENDING:
                statuses[target] = NodeStatus.WAITING
                ready.append(target)

    def _drain_subtree(
        self,
        *,
        edge: WorkflowEdge,
        outgoing_edges: dict[str, list[WorkflowEdge]],
        in_degree: dict[str, int],
        skipped_edges: set[str],
        nodes_by_id: dict[str, WorkflowNode],
        statuses: dict[str, NodeStatus],
        ready: deque[str],
    ) -> None:
        """Drain the subtree reachable through ``edge`` without executing it.

        Nodes whose ALL inbound edges have been drained get marked SKIPPED so
        any downstream merge node can still become ready (its in-degree drops
        to zero via the drained counts).
        """
        stack: list[WorkflowEdge] = [edge]
        while stack:
            e = stack.pop()
            if e.id in skipped_edges:
                continue
            skipped_edges.add(e.id)

            target = e.target
            if target not in in_degree:
                continue
            in_degree[target] -= 1

            # If all inbound edges to this node are now satisfied (drained or
            # produced), and the node hasn't run, mark it skipped and recurse.
            if in_degree[target] <= 0 and statuses.get(target) == NodeStatus.PENDING:
                statuses[target] = NodeStatus.SKIPPED
                # Recursively drain its downstream too.
                for child_edge in outgoing_edges.get(target, []):
                    stack.append(child_edge)

    # ── Event publishing ───────────────────────────────────────────────────

    async def _publish(
        self,
        context: ExecutionContext,
        event_type: WSEventType,
        data: dict[str, Any],
    ) -> None:
        """Publish a top-level execution event."""
        try:
            await context.publish_event(event_type.value, data)
        except Exception as exc:  # pragma: no cover - never let pub/sub take down a run
            self._log.warning(
                "engine.publish.error",
                event_type=event_type.value,
                error=str(exc),
                execution_id=context.execution_id,
            )

    async def _publish_node_event(
        self,
        context: ExecutionContext,
        event_type: WSEventType,
        node: WorkflowNode,
        extra: dict[str, Any],
    ) -> None:
        """Publish a per-node event with a consistent payload shape."""
        payload: dict[str, Any] = {
            "node_id": node.id,
            "node_name": node.name,
            "node_type": node.type.value,
            **extra,
        }
        await self._publish(context, event_type, payload)
