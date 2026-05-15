"""
Abstract base class and singleton registry for all workflow nodes.

Every node implementation in `app.core.nodes.*` must subclass `BaseNode` and
register itself in the module-level `registry` singleton so the engine can
look it up by `NodeType`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import structlog

from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)


class BaseNode(ABC):
    """Abstract base class for every executable workflow node.

    Subclasses must:
    - Set the class-level attribute ``node_type`` to a value of `NodeType`.
    - Implement the async :py:meth:`execute` method.

    Lifecycle hooks (``on_before_execute`` and ``on_after_execute``) may be
    overridden for setup/teardown. The engine guarantees ``on_before_execute``
    runs before each attempt and ``on_after_execute`` runs only after a
    successful attempt (no exception).
    """

    node_type: ClassVar[NodeType]

    @abstractmethod
    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        """Execute the node and return its output.

        Implementations should not raise for user-level errors; instead
        return a ``NodeOutput`` whose ``metadata`` contains an ``error`` key.
        The engine will catch any uncaught exceptions and convert them into
        failed node records.
        """
        raise NotImplementedError

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate node-specific configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        return None

    async def on_before_execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> None:
        """Hook called immediately before :py:meth:`execute`."""
        return None

    async def on_after_execute(
        self,
        output: NodeOutput,
        context: ExecutionContext,
    ) -> None:
        """Hook called after a successful :py:meth:`execute` call."""
        return None


class NodeRegistry:
    """Registry mapping ``NodeType`` to a ``BaseNode`` instance.

    Designed to be used as a module-level singleton. Node modules call
    ``registry.register(MyNode())`` at import time, and the engine calls
    ``registry.get(node.type)`` for each node it executes.
    """

    def __init__(self) -> None:
        self._nodes: dict[NodeType, BaseNode] = {}

    def register(self, node: BaseNode) -> None:
        """Register a node instance under its declared ``node_type``."""
        node_type = getattr(node, "node_type", None)
        if node_type is None:
            raise ValueError(
                f"Cannot register {node.__class__.__name__}: missing class attribute 'node_type'"
            )
        if node_type in self._nodes:
            logger.warning(
                "node_registry.override",
                node_type=node_type.value,
                previous=self._nodes[node_type].__class__.__name__,
                new=node.__class__.__name__,
            )
        self._nodes[node_type] = node
        logger.debug(
            "node_registry.registered",
            node_type=node_type.value,
            cls=node.__class__.__name__,
        )

    def get(self, node_type: NodeType) -> BaseNode:
        """Look up a node by ``NodeType``.

        Raises:
            KeyError: If no node is registered for the given type.
        """
        if node_type not in self._nodes:
            raise KeyError(f"No node registered for type: {node_type.value}")
        return self._nodes[node_type]

    def get_all(self) -> dict[NodeType, BaseNode]:
        """Return a shallow copy of the registry mapping."""
        return dict(self._nodes)

    def clear(self) -> None:
        """Remove all registered nodes (primarily for tests)."""
        self._nodes.clear()


# Module-level singleton — import this directly.
registry = NodeRegistry()
