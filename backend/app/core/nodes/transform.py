"""
Transform node — applies Jinja2 templates to build a new output dict.

Config schema::

    {
        "mappings": {
            "new_key": "{{ input.old_key | upper }}",
            "count":   "{{ input.items | length }}"
        },
        "remove_fields": ["secret", "internal.token"]
    }

The template context exposes:
- ``input``: the entire input_data dict (the upstream payload)
- ``variables``: ``context.variables`` (workflow-scoped variables)

Templates are rendered in a sandboxed Jinja2 environment — no Python attribute
access, no I/O, no imports — so user-defined workflows cannot break out.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import structlog
from jinja2.exceptions import TemplateError, UndefinedError
from jinja2.sandbox import SandboxedEnvironment

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)


def _build_environment() -> SandboxedEnvironment:
    env = SandboxedEnvironment(autoescape=False)
    # The built-in filters listed in the spec: upper, lower, strip, int, float,
    # length, join, default, tojson. All but `tojson` and `strip` are present
    # in Jinja2 by default.
    env.filters.setdefault("tojson", lambda v: json.dumps(v, default=str))
    env.filters.setdefault("strip", lambda v: str(v).strip() if v is not None else v)
    return env


_ENV: SandboxedEnvironment = _build_environment()


def _remove_field(data: dict[str, Any], dotted_path: str) -> None:
    """Mutate ``data`` in-place, removing the value at the dotted path if present."""
    if not dotted_path:
        return
    segments = dotted_path.split(".")
    current: Any = data
    for seg in segments[:-1]:
        if not isinstance(current, dict) or seg not in current:
            return
        current = current[seg]
    if isinstance(current, dict):
        current.pop(segments[-1], None)


class TransformNode(BaseNode):
    """Project / rename / compute fields with Jinja2 templates."""

    node_type: ClassVar[NodeType] = NodeType.TRANSFORM

    def validate_config(self, config: dict[str, Any]) -> None:
        mappings = config.get("mappings", {})
        if mappings and not isinstance(mappings, dict):
            raise ValueError("TransformNode 'mappings' must be a dict")
        remove_fields = config.get("remove_fields", [])
        if remove_fields and not isinstance(remove_fields, list):
            raise ValueError("TransformNode 'remove_fields' must be a list")

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        """Render mappings, drop ``remove_fields``, and return the result."""
        self.validate_config(config)
        mappings: dict[str, Any] = config.get("mappings", {}) or {}
        remove_fields: list[str] = config.get("remove_fields", []) or []

        # Start from a shallow copy of the input so callers' data is not mutated.
        output: dict[str, Any] = dict(input_data)
        errors: dict[str, str] = {}

        template_ctx = {
            "input": input_data,
            "variables": getattr(context, "variables", {}) or {},
        }

        for key, template_src in mappings.items():
            if not isinstance(template_src, str):
                # Non-string mappings are passed through verbatim.
                output[key] = template_src
                continue
            try:
                template = _ENV.from_string(template_src)
                output[key] = template.render(**template_ctx)
            except UndefinedError as exc:
                errors[key] = f"undefined: {exc.message}"
                output[key] = None
                context.logger.warning(
                    "transform.template_undefined",
                    extra={
                        "execution_id": context.execution_id,
                        "key": key,
                        "error": str(exc),
                    },
                )
            except TemplateError as exc:
                errors[key] = f"template_error: {exc.message}"
                output[key] = None
                context.logger.warning(
                    "transform.template_error",
                    extra={
                        "execution_id": context.execution_id,
                        "key": key,
                        "error": str(exc),
                    },
                )
            except Exception as exc:  # pragma: no cover - defensive
                errors[key] = f"unexpected: {exc!r}"
                output[key] = None
                context.logger.error(
                    "transform.unexpected_error",
                    extra={
                        "execution_id": context.execution_id,
                        "key": key,
                        "error": str(exc),
                    },
                )

        for path in remove_fields:
            if not isinstance(path, str):
                continue
            _remove_field(output, path)

        metadata: dict[str, Any] = {"mapped_keys": list(mappings.keys())}
        if errors:
            metadata["error"] = "One or more templates failed to render"
            metadata["template_errors"] = errors

        return NodeOutput(data=output, branch="output", metadata=metadata)


# Auto-register on import.
registry.register(TransformNode())
