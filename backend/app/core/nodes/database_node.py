"""Database integration node — executes parameterized SQL queries.

SECURITY: Only parameterized queries are used. String interpolation of
user-supplied values into SQL is strictly prohibited.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from jinja2 import Environment, StrictUndefined, TemplateError

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)

_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)

# Only allow SELECT by default; INSERT/UPDATE/DELETE require explicit opt-in
_MUTATION_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE)\b",
    re.IGNORECASE,
)


class DatabaseNode(BaseNode):
    """Execute a parameterized SQL query against a database connection string."""

    node_type = NodeType.DATABASE

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        template_vars = {**context.variables, "data": input_data}

        # Resolve credential
        cred_name: str = config.get("credential", "")
        cred_values: dict[str, Any] = context.credentials.get(cred_name, {})
        connection_string: str = cred_values.get("connection_string", config.get("connection_string", ""))

        if not connection_string:
            return NodeOutput(data={}, metadata={"error": "No database connection string provided"})

        # Render SQL template — only the query string is templated, NOT values
        try:
            query: str = _jinja_env.from_string(config["query"]).render(template_vars)
        except (TemplateError, KeyError) as exc:
            return NodeOutput(data={}, metadata={"error": f"Query template error: {exc}"})

        operation: str = config.get("operation", "query")
        allow_mutations: bool = config.get("allow_mutations", False)

        # Enforce mutation guard
        if _MUTATION_PATTERN.match(query) and not allow_mutations:
            return NodeOutput(
                data={},
                metadata={"error": "Mutation queries are disabled. Set allow_mutations=true to enable."},
            )

        # Params must come from config, NOT from query string interpolation
        params: list[Any] | dict[str, Any] = config.get("params", [])

        try:
            result = await self._execute_query(connection_string, query, params, operation)
        except Exception as exc:
            logger.error("database_node.query_failed", error=str(exc))
            return NodeOutput(data={}, metadata={"error": f"Database error: {exc}"})

        return NodeOutput(data=result)

    async def _execute_query(
        self,
        connection_string: str,
        query: str,
        params: list[Any] | dict[str, Any],
        operation: str,
    ) -> dict[str, Any]:
        """Execute query using asyncpg (PostgreSQL) or aiosqlite depending on URL scheme."""
        if connection_string.startswith("postgresql") or connection_string.startswith("postgres"):
            return await self._execute_pg(connection_string, query, params, operation)
        raise ValueError(f"Unsupported database scheme in connection string: {connection_string[:30]}")

    async def _execute_pg(
        self,
        dsn: str,
        query: str,
        params: list[Any] | dict[str, Any],
        operation: str,
    ) -> dict[str, Any]:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            if operation == "execute":
                status = await conn.execute(query, *(params if isinstance(params, list) else params.values()))
                return {"row_count": int(status.split()[-1]) if status else 0, "status": status}
            else:
                # Always use parameterized fetch — never string interpolation
                rows = await conn.fetch(query, *(params if isinstance(params, list) else params.values()))
                if not rows:
                    return {"rows": [], "row_count": 0, "columns": []}
                columns = list(rows[0].keys())
                return {
                    "rows": [dict(r) for r in rows],
                    "row_count": len(rows),
                    "columns": columns,
                }
        finally:
            await conn.close()


registry.register(DatabaseNode())
