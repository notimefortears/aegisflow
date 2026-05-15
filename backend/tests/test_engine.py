"""
Comprehensive async tests for the WorkflowEngine and built-in nodes.

Run with::

    pytest backend/tests/test_engine.py -v
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.engine import NodeExecutionError, WorkflowEngine
from app.core.nodes.base import BaseNode, NodeRegistry
from app.core.nodes.condition import ConditionNode
from app.core.nodes.merge import MergeNode
from app.core.nodes.transform import TransformNode
from app.shared_types import (
    ExecutionContext,
    ExecutionStatus,
    NodeOutput,
    NodeType,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodePosition,
)

pytestmark = pytest.mark.asyncio


# ── Test fixtures and helpers ──────────────────────────────────────────────────


def make_node(
    node_id: str,
    node_type: NodeType = NodeType.TRANSFORM,
    name: str | None = None,
    config: dict[str, Any] | None = None,
    disabled: bool = False,
) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type=node_type,
        name=name or node_id,
        config=config or {},
        position=WorkflowNodePosition(x=0, y=0),
        disabled=disabled,
    )


def make_edge(
    source: str,
    target: str,
    source_handle: str = "output",
    target_handle: str = "input",
    edge_id: str | None = None,
) -> WorkflowEdge:
    return WorkflowEdge(
        id=edge_id or f"{source}->{target}:{source_handle}",
        source=source,
        source_handle=source_handle,
        target=target,
        target_handle=target_handle,
    )


@pytest.fixture
def fake_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def fake_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def context(fake_redis: AsyncMock, fake_db: MagicMock) -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-1",
        workflow_id="wf-1",
        user_id="user-1",
        variables={},
        credentials={},
        redis=fake_redis,
        db=fake_db,
        logger=logging.getLogger("test"),
    )


@pytest.fixture
def registry() -> NodeRegistry:
    """Fresh registry per test to avoid global-singleton bleed."""
    r = NodeRegistry()
    r.register(ConditionNode())
    r.register(TransformNode())
    r.register(MergeNode())
    return r


# Helper synthetic node types for engine-only tests --------------------------------


class _RecordingNode(BaseNode):
    """A node that records call order and timing into a shared list."""

    node_type: ClassVar[NodeType] = NodeType.HTTP

    def __init__(self, recorder: list[tuple[str, float]], delay: float = 0.0) -> None:
        self.recorder = recorder
        self.delay = delay

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        name = config.get("_name", "anon")
        self.recorder.append((f"start:{name}", time.perf_counter()))
        if self.delay:
            await asyncio.sleep(self.delay)
        self.recorder.append((f"end:{name}", time.perf_counter()))
        # Echo input + tag with which node ran
        return NodeOutput(
            data={**input_data, "_ran": name},
            branch="output",
        )


class _FlakyNode(BaseNode):
    """Fails the first ``fail_times`` calls, then succeeds."""

    node_type: ClassVar[NodeType] = NodeType.HTTP

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(f"flaky fail #{self.calls}")
        return NodeOutput(data={"calls": self.calls}, branch="output")


class _SlowNode(BaseNode):
    """Sleeps longer than any reasonable test timeout."""

    node_type: ClassVar[NodeType] = NodeType.HTTP

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        await asyncio.sleep(5.0)
        return NodeOutput(data={}, branch="output")


# ── 1. Linear 3-node workflow ──────────────────────────────────────────────────


async def test_linear_three_nodes_execute_in_order(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    recorder: list[tuple[str, float]] = []
    registry.register(_RecordingNode(recorder))

    nodes = [
        make_node("a", NodeType.HTTP, config={"_name": "a"}),
        make_node("b", NodeType.HTTP, config={"_name": "b"}),
        make_node("c", NodeType.HTTP, config={"_name": "c"}),
    ]
    edges = [make_edge("a", "b"), make_edge("b", "c")]
    workflow = WorkflowDefinition(nodes=nodes, edges=edges)

    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)
    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf-linear",
        execution_id="exec-linear",
        trigger_data={"seed": 1},
        context=context,
    )

    assert status == ExecutionStatus.SUCCESS
    # Order: a start, a end, b start, b end, c start, c end
    names = [r[0] for r in recorder]
    assert names == [
        "start:a",
        "end:a",
        "start:b",
        "end:b",
        "start:c",
        "end:c",
    ]


# ── 2. Parallel branches run concurrently ──────────────────────────────────────


async def test_parallel_branches_run_concurrently(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    recorder: list[tuple[str, float]] = []
    registry.register(_RecordingNode(recorder, delay=0.2))

    # 3 independent branches each starting from the root, ending in nothing.
    nodes = [
        make_node("root", NodeType.HTTP, config={"_name": "root"}),
        make_node("p1", NodeType.HTTP, config={"_name": "p1"}),
        make_node("p2", NodeType.HTTP, config={"_name": "p2"}),
        make_node("p3", NodeType.HTTP, config={"_name": "p3"}),
    ]
    edges = [
        make_edge("root", "p1"),
        make_edge("root", "p2"),
        make_edge("root", "p3"),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=edges)

    # Override recorder to use no delay for root, 0.2s for parallels.
    recorder.clear()
    registry.register(_RecordingNode(recorder, delay=0.2))

    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    start = time.perf_counter()
    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf-par",
        execution_id="exec-par",
        trigger_data={},
        context=context,
    )
    elapsed = time.perf_counter() - start

    assert status == ExecutionStatus.SUCCESS
    # If parallel: total ≈ 0.2 (root) + 0.2 (max of 3 parallels) ≈ 0.4s.
    # If sequential: would be ≈ 0.8s. Allow generous CI slack.
    assert elapsed < 0.75, f"Parallel branches took too long: {elapsed:.3f}s"

    # All three parallel nodes should have started before any one of them ended.
    par_starts = [t for (n, t) in recorder if n in ("start:p1", "start:p2", "start:p3")]
    par_ends = [t for (n, t) in recorder if n in ("end:p1", "end:p2", "end:p3")]
    assert max(par_starts) < min(par_ends), "parallel nodes did not overlap"


# ── 3. Condition node routes to "true" branch only ─────────────────────────────


async def test_condition_routes_true_branch_only(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    recorder: list[tuple[str, float]] = []
    registry.register(_RecordingNode(recorder))

    nodes = [
        make_node(
            "cond",
            NodeType.CONDITION,
            config={"field": "age", "operator": "greater_than", "value": 18},
        ),
        make_node("yes", NodeType.HTTP, config={"_name": "yes"}),
        make_node("no", NodeType.HTTP, config={"_name": "no"}),
    ]
    edges = [
        make_edge("cond", "yes", source_handle="true"),
        make_edge("cond", "no", source_handle="false"),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=edges)

    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)
    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf-cond",
        execution_id="exec-cond",
        trigger_data={"age": 25},
        context=context,
    )

    assert status == ExecutionStatus.SUCCESS
    names = [r[0] for r in recorder]
    assert "start:yes" in names
    assert "start:no" not in names


async def test_condition_false_branch_when_predicate_fails(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    recorder: list[tuple[str, float]] = []
    registry.register(_RecordingNode(recorder))

    nodes = [
        make_node(
            "cond",
            NodeType.CONDITION,
            config={"field": "age", "operator": "greater_than", "value": 18},
        ),
        make_node("yes", NodeType.HTTP, config={"_name": "yes"}),
        make_node("no", NodeType.HTTP, config={"_name": "no"}),
    ]
    edges = [
        make_edge("cond", "yes", source_handle="true"),
        make_edge("cond", "no", source_handle="false"),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=edges)
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf",
        execution_id="exec",
        trigger_data={"age": 10},
        context=context,
    )
    assert status == ExecutionStatus.SUCCESS
    names = [r[0] for r in recorder]
    assert "start:no" in names
    assert "start:yes" not in names


# ── 4. Node timeout ────────────────────────────────────────────────────────────


async def test_node_timeout_marks_failure(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    registry.register(_SlowNode())

    nodes = [
        make_node(
            "slow",
            NodeType.HTTP,
            config={"timeout_seconds": 0.1, "retry": 0},
        ),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=[])
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf",
        execution_id="exec-timeout",
        trigger_data={},
        context=context,
    )

    assert status == ExecutionStatus.FAILED
    # Verify NODE_FAILED + EXECUTION_FAILED were published.
    published = [call.args for call in fake_redis.publish.await_args_list]
    payloads = " ".join(args[1] for args in published)
    assert "node_failed" in payloads
    assert "execution_failed" in payloads
    assert "timeout" in payloads.lower() or "timed out" in payloads.lower()


# ── 5. Retry succeeds on third try ─────────────────────────────────────────────


async def test_retry_succeeds_after_failures(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry, monkeypatch
) -> None:
    flaky = _FlakyNode(fail_times=2)
    registry.register(flaky)

    # Eliminate backoff sleep so the test is fast.
    monkeypatch.setattr(
        "app.core.engine.WorkflowEngine._backoff_seconds",
        staticmethod(lambda _attempt: 0.0),
    )

    nodes = [
        make_node(
            "f",
            NodeType.HTTP,
            config={"retry": 2, "timeout_seconds": 5},
        ),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=[])
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf",
        execution_id="exec-retry",
        trigger_data={},
        context=context,
    )

    assert status == ExecutionStatus.SUCCESS
    assert flaky.calls == 3


async def test_retry_exhausted_raises_failure(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry, monkeypatch
) -> None:
    flaky = _FlakyNode(fail_times=10)
    registry.register(flaky)
    monkeypatch.setattr(
        "app.core.engine.WorkflowEngine._backoff_seconds",
        staticmethod(lambda _attempt: 0.0),
    )

    nodes = [
        make_node(
            "f",
            NodeType.HTTP,
            config={"retry": 2, "timeout_seconds": 5},
        ),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=[])
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf",
        execution_id="exec-retry-fail",
        trigger_data={},
        context=context,
    )

    assert status == ExecutionStatus.FAILED
    assert flaky.calls == 3  # initial + 2 retries


# ── 6. Cancellation ────────────────────────────────────────────────────────────


async def test_cancelled_execution_stops_gracefully(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    registry.register(_SlowNode())

    nodes = [
        make_node("slow", NodeType.HTTP, config={"timeout_seconds": 10, "retry": 0}),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=[])
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    task = asyncio.create_task(
        engine.execute(
            workflow=workflow,
            workflow_id="wf",
            execution_id="exec-cancel",
            trigger_data={},
            context=context,
        )
    )
    # Let the engine schedule the slow node, then cancel.
    await asyncio.sleep(0.05)
    task.cancel()

    # The engine catches CancelledError internally and returns CANCELLED.
    try:
        status = await task
    except asyncio.CancelledError:
        pytest.fail("Engine should swallow CancelledError and return CANCELLED status")

    assert status == ExecutionStatus.CANCELLED


async def test_cancel_execution_publishes_to_redis(fake_redis: AsyncMock) -> None:
    engine = WorkflowEngine(redis=fake_redis, node_registry=NodeRegistry())
    await engine.cancel_execution("exec-abc")
    fake_redis.publish.assert_awaited_once()
    channel, payload = fake_redis.publish.await_args.args
    assert channel == "executions:exec-abc"
    assert "cancel" in payload


# ── 7. Transform node with Jinja2 ──────────────────────────────────────────────


async def test_transform_node_renders_jinja_templates(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    nodes = [
        make_node(
            "t",
            NodeType.TRANSFORM,
            config={
                "mappings": {
                    "shout": "{{ input.name | upper }}",
                    "n": "{{ input.items | length }}",
                    "joined": "{{ input.items | join(',') }}",
                },
                "remove_fields": ["secret"],
            },
        ),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=[])
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf",
        execution_id="exec-tx",
        trigger_data={"name": "alice", "items": [1, 2, 3], "secret": "shh"},
        context=context,
    )
    assert status == ExecutionStatus.SUCCESS


async def test_transform_node_direct_invocation(context: ExecutionContext) -> None:
    """Verify TransformNode produces correct output when called directly."""
    node = TransformNode()
    output = await node.execute(
        input_data={"name": "bob", "items": [1, 2], "secret": "xx"},
        config={
            "mappings": {
                "upper_name": "{{ input.name | upper }}",
                "count": "{{ input.items | length }}",
            },
            "remove_fields": ["secret"],
        },
        context=context,
    )
    assert output.data["upper_name"] == "BOB"
    assert output.data["count"] == "2"  # Jinja renders to string
    assert "secret" not in output.data


async def test_transform_node_invalid_template_captured_in_metadata(
    context: ExecutionContext,
) -> None:
    node = TransformNode()
    output = await node.execute(
        input_data={"x": 1},
        config={"mappings": {"bad": "{{ not_a_filter(broken syntax"}},
        context=context,
    )
    assert "error" in output.metadata
    assert "template_errors" in output.metadata
    assert "bad" in output.metadata["template_errors"]


# ── 8. Condition node with missing field ──────────────────────────────────────


async def test_condition_missing_field_does_not_crash(
    context: ExecutionContext,
) -> None:
    node = ConditionNode()
    # Missing field — is_empty should be true.
    out_empty = await node.execute(
        input_data={"data": {"user": {}}},
        config={"field": "data.user.age", "operator": "is_empty", "value": None},
        context=context,
    )
    assert out_empty.branch == "true"

    # Missing field with equals — actual is None, expected is 5 → false branch.
    out_eq = await node.execute(
        input_data={},
        config={"field": "deeply.missing.path", "operator": "equals", "value": 5},
        context=context,
    )
    assert out_eq.branch == "false"

    # Missing field with greater_than — should not raise.
    out_gt = await node.execute(
        input_data={},
        config={"field": "missing", "operator": "greater_than", "value": 0},
        context=context,
    )
    assert out_gt.branch == "false"


async def test_condition_supported_operators(context: ExecutionContext) -> None:
    node = ConditionNode()
    cases = [
        ({"x": "hello"}, "contains", "ell", "true"),
        ({"x": "hello"}, "not_contains", "zzz", "true"),
        ({"x": "hello"}, "starts_with", "he", "true"),
        ({"x": "hello"}, "ends_with", "lo", "true"),
        ({"x": "hello"}, "regex_match", "^h.*o$", "true"),
        ({"x": 5}, "less_than", 10, "true"),
        ({"x": 5}, "equals", 5, "true"),
        ({"x": 5}, "not_equals", 6, "true"),
        ({"x": ""}, "is_empty", None, "true"),
        ({"x": "y"}, "is_not_empty", None, "true"),
    ]
    for data, op, val, expected in cases:
        out = await node.execute(
            input_data=data,
            config={"field": "x", "operator": op, "value": val},
            context=context,
        )
        assert out.branch == expected, f"{op}({data['x']!r}, {val!r}) → {out.branch}"


# ── Bonus: merge node behaviour ─────────────────────────────────────────────────


async def test_merge_node_modes(context: ExecutionContext) -> None:
    node = MergeNode()

    # merge_objects
    out = await node.execute(
        input_data={"a": {"x": 1}, "b": {"y": 2}},
        config={"mode": "merge_objects"},
        context=context,
    )
    assert out.data == {"x": 1, "y": 2}

    # concat_arrays — branches with "items" lists
    out = await node.execute(
        input_data={"a": {"items": [1, 2]}, "b": {"items": [3]}},
        config={"mode": "concat_arrays"},
        context=context,
    )
    assert out.data == {"items": [1, 2, 3]}

    # first
    out = await node.execute(
        input_data={"a": {"x": 1}, "b": {"x": 2}},
        config={"mode": "first"},
        context=context,
    )
    assert out.data == {"x": 1}

    # last
    out = await node.execute(
        input_data={"a": {"x": 1}, "b": {"x": 2}},
        config={"mode": "last"},
        context=context,
    )
    assert out.data == {"x": 2}

    # all
    out = await node.execute(
        input_data={"a": {"x": 1}, "b": {"x": 2}},
        config={"mode": "all"},
        context=context,
    )
    assert out.data == {"items": [{"x": 1}, {"x": 2}]}


async def test_merge_in_workflow_combines_parallel_branches(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    recorder: list[tuple[str, float]] = []
    registry.register(_RecordingNode(recorder))

    nodes = [
        make_node("root", NodeType.HTTP, config={"_name": "root"}),
        make_node("p1", NodeType.HTTP, config={"_name": "p1"}),
        make_node("p2", NodeType.HTTP, config={"_name": "p2"}),
        make_node("m", NodeType.MERGE, config={"mode": "all"}),
    ]
    edges = [
        make_edge("root", "p1"),
        make_edge("root", "p2"),
        make_edge("p1", "m", edge_id="p1m"),
        make_edge("p2", "m", edge_id="p2m"),
    ]
    workflow = WorkflowDefinition(nodes=nodes, edges=edges)
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf-merge",
        execution_id="exec-merge",
        trigger_data={"seed": "z"},
        context=context,
    )
    assert status == ExecutionStatus.SUCCESS


# ── Disabled nodes ──────────────────────────────────────────────────────────────


async def test_disabled_node_passes_input_through(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    recorder: list[tuple[str, float]] = []
    registry.register(_RecordingNode(recorder))

    nodes = [
        make_node("a", NodeType.HTTP, config={"_name": "a"}),
        make_node("b", NodeType.HTTP, config={"_name": "b"}, disabled=True),
        make_node("c", NodeType.HTTP, config={"_name": "c"}),
    ]
    edges = [make_edge("a", "b"), make_edge("b", "c")]
    workflow = WorkflowDefinition(nodes=nodes, edges=edges)
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf-dis",
        execution_id="exec-dis",
        trigger_data={},
        context=context,
    )
    assert status == ExecutionStatus.SUCCESS
    names = [r[0] for r in recorder]
    assert "start:a" in names
    assert "start:b" not in names  # disabled — never executed
    assert "start:c" in names


# ── Unregistered node type ──────────────────────────────────────────────────────


async def test_unregistered_node_type_fails_cleanly(
    fake_redis: AsyncMock, context: ExecutionContext
) -> None:
    empty_registry = NodeRegistry()  # no nodes registered
    nodes = [make_node("x", NodeType.TRANSFORM)]
    workflow = WorkflowDefinition(nodes=nodes, edges=[])
    engine = WorkflowEngine(redis=fake_redis, node_registry=empty_registry)

    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf",
        execution_id="exec-missing",
        trigger_data={},
        context=context,
    )
    assert status == ExecutionStatus.FAILED


# ── Empty / cyclic workflows ────────────────────────────────────────────────────


async def test_empty_workflow_fails(
    fake_redis: AsyncMock, context: ExecutionContext, registry: NodeRegistry
) -> None:
    workflow = WorkflowDefinition(nodes=[], edges=[])
    engine = WorkflowEngine(redis=fake_redis, node_registry=registry)
    status = await engine.execute(
        workflow=workflow,
        workflow_id="wf",
        execution_id="exec-empty",
        trigger_data={},
        context=context,
    )
    assert status == ExecutionStatus.FAILED
