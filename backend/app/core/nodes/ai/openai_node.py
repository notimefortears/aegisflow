"""
OpenAINode — OpenAI Chat Completions API node with built-in security scanning.

Mirrors :class:`ClaudeNode` so workflows can swap providers without changing
downstream contracts. See ``claude_node.py`` for an explanation of the
security pipeline; the only differences here are SDK shapes and retry
predicates.
"""

from __future__ import annotations

from typing import Any, ClassVar

import openai
import structlog
from jinja2 import Environment, StrictUndefined, TemplateError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.nodes.base import BaseNode, registry
from app.core.security_engine import security_engine
from app.shared_types import ExecutionContext, NodeOutput, NodeType


logger = structlog.get_logger(__name__)

_jinja_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)


_RETRYABLE_ERRORS: tuple[type[BaseException], ...] = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


_SUPPORTED_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo"}


class OpenAINode(BaseNode):
    """Workflow node that calls the OpenAI Chat Completions API."""

    node_type: ClassVar[NodeType] = NodeType.OPENAI

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("user_message"):
            raise ValueError("OpenAINode requires 'user_message' in config")
        if not config.get("credential"):
            raise ValueError("OpenAINode requires 'credential' in config")
        model = config.get("model", "gpt-4o")
        # Soft check: warn rather than reject — OpenAI rolls out new models often.
        if model not in _SUPPORTED_MODELS:
            logger.debug("openai_node.unknown_model", model=model)

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        self.validate_config(config)

        model = config.get("model", "gpt-4o")
        system_prompt = config.get("system_prompt") or None
        max_tokens = int(config.get("max_tokens", 2048))
        temperature = float(config.get("temperature", 0.7))
        timeout_seconds = float(config.get("timeout_seconds", 60))
        max_retries = int(config.get("retry", 2))
        credential_name = config["credential"]

        # 1. Render templates.
        try:
            rendered = _jinja_env.from_string(config["user_message"]).render(
                data=input_data, variables=context.variables
            )
            if system_prompt:
                system_prompt = _jinja_env.from_string(system_prompt).render(
                    data=input_data, variables=context.variables
                )
        except TemplateError as exc:
            return NodeOutput(
                data={"error": f"Template render error: {exc}"},
                branch="error",
                metadata={"error_type": "template", "detail": str(exc)},
            )

        # 2. Resolve credential.
        api_key = context.credentials.get(credential_name)
        if not api_key:
            return NodeOutput(
                data={"error": f"Missing credential: {credential_name}"},
                branch="error",
                metadata={"error_type": "credential"},
            )

        # 3. Injection scan.
        injection_result = await security_engine.scan_injection(rendered)
        if not injection_result.is_safe:
            context.logger.warning(
                "openai_node.injection_blocked",
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

        # 4. Input PII scan (warn-only).
        input_pii = await security_engine.scan_pii(rendered)
        if input_pii.has_pii:
            context.logger.warning(
                "openai_node.input_pii_detected",
                extra={
                    "execution_id": context.execution_id,
                    "risk_score": input_pii.risk_score,
                    "match_count": len(input_pii.matches),
                },
            )

        # 5. Call OpenAI with retry.
        client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": rendered})

        try:
            response = None
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries + 1),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                retry=retry_if_exception_type(_RETRYABLE_ERRORS),
                reraise=True,
            ):
                with attempt:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
        except openai.AuthenticationError as exc:
            return NodeOutput(
                data={"error": "OpenAI authentication failed — check your API key"},
                branch="error",
                metadata={"error_type": "auth", "detail": str(exc)},
            )
        except openai.BadRequestError as exc:
            return NodeOutput(
                data={"error": f"OpenAI rejected request: {exc}"},
                branch="error",
                metadata={"error_type": "bad_request", "detail": str(exc)},
            )
        except openai.APIStatusError as exc:
            return NodeOutput(
                data={"error": f"OpenAI API error: {exc}"},
                branch="error",
                metadata={"error_type": "api_status", "detail": str(exc), "status_code": getattr(exc, "status_code", None)},
            )
        except Exception as exc:  # noqa: BLE001
            return NodeOutput(
                data={"error": f"Unexpected error calling OpenAI: {exc}"},
                branch="error",
                metadata={"error_type": "unknown", "detail": str(exc)},
            )

        # Extract assistant text.
        text = ""
        if response and response.choices:
            text = response.choices[0].message.content or ""

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0

        # 6. Output PII scan.
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
                "finish_reason": response.choices[0].finish_reason if response and response.choices else None,
            },
            branch="output",
            metadata={
                "injection_scan": injection_result.model_dump(),
                "input_pii_scan": input_pii.model_dump(),
                "pii_scan": output_pii.model_dump(),
            },
            security_flags=flags,
        )


registry.register(OpenAINode())
