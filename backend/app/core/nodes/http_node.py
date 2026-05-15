"""HTTP integration node — makes outbound HTTP requests."""

from __future__ import annotations

import json
from typing import Any

import aiohttp
import structlog
from jinja2 import Environment, StrictUndefined, TemplateError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)

_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _is_server_error(exc: Exception) -> bool:
    return isinstance(exc, aiohttp.ClientResponseError) and exc.status >= 500


class HTTPNode(BaseNode):
    """Execute an outbound HTTP request with Jinja2-templated URL and body."""

    node_type = NodeType.HTTP

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        method = config.get("method", "GET").upper()
        if method not in ALLOWED_METHODS:
            return NodeOutput(
                data={},
                metadata={"error": f"Unsupported HTTP method: {method}"},
            )

        template_vars = {**context.variables, "data": input_data}

        # Render URL template
        try:
            url = _jinja_env.from_string(config["url"]).render(template_vars)
        except (TemplateError, KeyError) as exc:
            return NodeOutput(data={}, metadata={"error": f"URL template error: {exc}"})

        # Build headers
        raw_headers: dict[str, str] = config.get("headers", {})
        headers: dict[str, str] = {}
        for k, v in raw_headers.items():
            try:
                headers[k] = _jinja_env.from_string(str(v)).render(template_vars)
            except TemplateError as exc:
                return NodeOutput(data={}, metadata={"error": f"Header template error: {exc}"})

        # Build body
        body: str | None = None
        raw_body = config.get("body", "")
        if raw_body:
            try:
                body = _jinja_env.from_string(raw_body).render(template_vars)
            except TemplateError as exc:
                return NodeOutput(data={}, metadata={"error": f"Body template error: {exc}"})

        timeout_seconds: int = int(config.get("timeout_seconds", 30))

        result = await self._do_request(method, url, headers, body, timeout_seconds)
        return NodeOutput(data=result)

    @retry(
        retry=retry_if_exception(_is_server_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _do_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: str | None,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            request_kwargs: dict[str, Any] = {"headers": headers}
            if body:
                request_kwargs["data"] = body

            async with session.request(method, url, **request_kwargs) as resp:
                resp.raise_for_status()
                raw_body_bytes = await resp.read()
                body_text = raw_body_bytes.decode("utf-8", errors="replace")
                result: dict[str, Any] = {
                    "status_code": resp.status,
                    "headers": dict(resp.headers),
                    "body": body_text,
                }
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    try:
                        result["body_json"] = json.loads(body_text)
                    except json.JSONDecodeError:
                        pass
                return result


registry.register(HTTPNode())
