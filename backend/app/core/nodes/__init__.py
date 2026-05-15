"""Node implementations + registry for the AegisFlow workflow engine.

Importing this package guarantees every built-in node has registered itself
in :data:`app.core.nodes.base.registry`.
"""

from app.core.nodes.base import BaseNode, NodeRegistry, registry

# Importing each module triggers `registry.register(...)` at import time.
from app.core.nodes import condition as _condition  # noqa: F401
from app.core.nodes import merge as _merge  # noqa: F401
from app.core.nodes import transform as _transform  # noqa: F401

from app.core.nodes.condition import ConditionNode
from app.core.nodes.merge import MergeNode
from app.core.nodes.transform import TransformNode

__all__ = [
    "BaseNode",
    "NodeRegistry",
    "registry",
    "ConditionNode",
    "MergeNode",
    "TransformNode",
]
