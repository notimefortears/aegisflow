"""Webhook trigger node.

Generates a unique webhook URL per workflow, validates HMAC signatures
if configured, and passes the inbound request payload as trigger_data.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any

import structlog

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)


class WebhookTriggerNode(BaseNode):
    """Webhook trigger: validates inbound HTTP payloads and starts the workflow."""

    node_type = NodeType.WEBHOOK

    # Webhook URL slug stored in the workflow definition config
    SLUG_KEY = "webhook_id"

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        """Validate the incoming webhook and return its payload.

        ``input_data`` is expected to contain:
          - ``body``: raw request body (str or dict)
          - ``headers``: dict of request headers
          - ``query_params``: dict of query string params
        """
        auth_type: str = config.get("auth_type", "none")
        webhook_id: str = config.get(self.SLUG_KEY, "")

        if auth_type == "hmac":
            secret: str = config.get("hmac_secret", "")
            if not self._validate_hmac(input_data, secret):
                return NodeOutput(
                    data={},
                    metadata={"error": "HMAC signature validation failed"},
                    security_flags=["invalid_hmac"],
                )
        elif auth_type == "bearer":
            expected_token: str = config.get("bearer_token", "")
            auth_header = (input_data.get("headers") or {}).get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != expected_token:
                return NodeOutput(
                    data={},
                    metadata={"error": "Bearer token mismatch"},
                    security_flags=["invalid_bearer"],
                )

        logger.info("webhook.trigger", webhook_id=webhook_id, execution_id=context.execution_id)

        return NodeOutput(
            data={
                "webhook_id": webhook_id,
                "body": input_data.get("body", {}),
                "headers": input_data.get("headers", {}),
                "query_params": input_data.get("query_params", {}),
            }
        )

    @staticmethod
    def _validate_hmac(input_data: dict[str, Any], secret: str) -> bool:
        if not secret:
            return False
        raw_body: str = input_data.get("raw_body", "")
        if isinstance(raw_body, dict):
            import json
            raw_body = json.dumps(raw_body, separators=(",", ":"))
        signature_header = (input_data.get("headers") or {}).get("X-Webhook-Signature", "")
        expected = hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature_header)

    @staticmethod
    def generate_webhook_id() -> str:
        """Generate a new unique webhook identifier for a workflow config."""
        return uuid.uuid4().hex


registry.register(WebhookTriggerNode())
