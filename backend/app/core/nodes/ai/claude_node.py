"""
ClaudeNode — Anthropic Messages API node with built-in security scanning.

Pipeline:
    1. Render ``user_message`` as a Jinja2 template against ``input_data``.
    2. Look up the API key from ``context.credentials[config["credential"]]``.
    3. Scan the rendered message for prompt injection via SecurityEngine.
       Block (raise SecurityPolicyError) on high-risk content.
    4. Scan the rendered message for PII (warn-only; remains in payload).
    5. Call ``client.messages.create`` with tenacity retry on rate-limit /
       server errors.
    6. Scan the model output for PII; flag in ``security_flags`` if found.
"""

from __future__ import annotations

from typing import Any, ClassVar

import anthropic
import structlog
from jinja2 import Environment, StrictUndefined, TemplateError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.nodes.base import BaseNode, registry
from app.core.security_engine import SecurityPolicyError, security_engine
from app.shared_types import ExecutionContext, NodeOutput, NodeType


logger = structlog.get_logger(__name__)

# A sandboxed Jinja env. ``StrictUndefined`` makes typos in user templates
# surface immediately rather than silently inserting empty strings.
_jinja_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,           # outputs to LLM, not HTML
    keep_trailing_newline=True,
)


# Retry on rate-limit (429) and Anthropic-side 5xx errors.
_RETRYABLE_ERRORS: tuple[type[BaseException], ...] = (
    anthropic.RateLimitError,
    anthropic.APIStatusError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
)


def _is_retryable_status(exc: BaseException) -> bool:
    """Return True only for genuinely transient status codes."""
    if isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        code = getattr(exc, "status_code", None)
        return code in {500, 502, 503, 504, 529}
    return False


class ClaudeNode(BaseNode):
    """Workflow node that calls the Anthropic Messages API."""

    node_type: ClassVar[NodeType] = NodeType.CLAUDE

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("user_message"):
            raise ValueError("ClaudeNode requires 'user_message' in config")
        if not config.get("credential"):
            raise ValueError("ClaudeNode requires 'credential' in config")

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        self.validate_config(config)

        model = config.get("model", "claude-sonnet-4-6")
        system_prompt = config.get("system_prompt") or None
        max_tokens = int(config.get("max_tokens", 2048))
        temperature = float(config.get("temperature", 0.7))
        timeout_seconds = float(config.get("timeout_seconds", 60))
        max_retries = int(config.get("retry", 2))
        credential_name = config["credential"]

        # 1. Render Jinja2 template ─────────────────────────────────────────
        try:
            template = _jinja_env.from_string(config["user_message"])
            rendered = template.render(data=input_data, variables=context.variables)
        except TemplateError as exc:
            return NodeOutput(
                data={"error": f"Template render error: {exc}"},
                branch="error",
                metadata={"error": str(exc), "error_type": "template"},
                security_flags=[],
            )

        if config.get("system_prompt"):
            try:
                system_prompt = _jinja_env.from_string(config["system_prompt"]).render(
                    data=input_data, variables=context.variables
                )
            except TemplateError as exc:
                return NodeOutput(
                    data={"error": f"System template error: {exc}"},
                    branch="error",
                    metadata={"error": str(exc), "error_type": "template"},
                )

        # 2. Resolve API key ───────────────────────────────────────────────
        api_key = context.credentials.get(credential_name)
        if not api_key:
            return NodeOutput(
                data={"error": f"Missing credential: {credential_name}"},
                branch="error",
                metadata={"error_type": "credential"},
            )

        # 3. Injection scan ─────────────────────────────────────────────────
        injection_result = await security_engine.scan_injection(rendered)
        if not injection_result.is_safe:
            context.logger.warning(
                "claude_node.injection_blocked",
                extra={
                    "execution_id": context.execution_id,
                    "risk_score": injection_result.risk_score,
                    "patterns": injection_result.patterns_matched,
                },
            )
            return NodeOutput(
                data={"error": "Prompt injection detected", "risk_score": injection_result.risk_score},
                branch="blocked",
                metadata={"injection_scan": injection_result.model_dump()},
                security_flags=["injection_blocked"],
            )

        # 4. Input PII scan (warn-only) ─────────────────────────────────────
        input_pii = await security_engine.scan_pii(rendered)
        if input_pii.has_pii:
            context.logger.warning(
                "claude_node.input_pii_detected",
                extra={
                    "execution_id": context.execution_id,
                    "risk_score": input_pii.risk_score,
                    "match_count": len(input_pii.matches),
                },
            )

        # 5. Call Anthropic with retry ─────────────────────────────────────
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_seconds)

        messages_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": rendered}],
        }
        if system_prompt:
            messages_kwargs["system"] = system_prompt

        try:
            response = None
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries + 1),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                retry=retry_if_exception_type(_RETRYABLE_ERRORS),
                reraise=True,
            ):
                with attempt:
                    try:
                        response = await client.messages.create(**messages_kwargs)
                    except anthropic.APIStatusError as exc:
                        if not _is_retryable_status(exc):
                            raise  # bubble up as non-retryable
                        raise
        except anthropic.AuthenticationError as exc:
            return NodeOutput(
                data={"error": "Anthropic authentication failed — check your API key"},
                branch="error",
                metadata={"error_type": "auth", "detail": str(exc)},
            )
        except anthropic.BadRequestError as exc:
            return NodeOutput(
                data={"error": f"Anthropic rejected request: {exc}"},
                branch="error",
                metadata={"error_type": "bad_request", "detail": str(exc)},
            )
        except anthropic.APIStatusError as exc:
            return NodeOutput(
                data={"error": f"Anthropic API error: {exc}"},
                branch="error",
                metadata={"error_type": "api_status", "detail": str(exc), "status_code": getattr(exc, "status_code", None)},
            )
        except Exception as exc:  # noqa: BLE001 — final safety net
            return NodeOutput(
                data={"error": f"Unexpected error calling Anthropic: {exc}"},
                branch="error",
                metadata={"error_type": "unknown", "detail": str(exc)},
            )

        # Extract text content from the response.
        text = ""
        if response and response.content:
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text += getattr(block, "text", "")
                elif hasattr(block, "text"):
                    text += block.text

        input_tokens = getattr(getattr(response, "usage", None), "input_tokens", 0) or 0
        output_tokens = getattr(getattr(response, "usage", None), "output_tokens", 0) or 0

        # 6. Output PII scan ───────────────────────────────────────────────
        output_pii = await security_engine.scan_pii(text)

        flags: list[str] = []
        if output_pii.has_pii:
            flags.append("pii_detected")
        if input_pii.has_pii:
            flags.append("input_pii_detected")

        return NodeOutput(
            data={
                "response": text,
                "model": getattr(response, "model", model),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "stop_reason": getattr(response, "stop_reason", None),
            },
            branch="output",
            metadata={
                "injection_scan": injection_result.model_dump(),
                "input_pii_scan": input_pii.model_dump(),
                "pii_scan": output_pii.model_dump(),
            },
            security_flags=flags,
        )


# Register at import time so `from app.core.nodes.ai import *` is enough.
registry.register(ClaudeNode())
