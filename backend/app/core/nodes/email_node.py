"""Email integration node — sends HTML email via SMTP."""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Any

import aiosmtplib
import structlog
from jinja2 import Environment, StrictUndefined, TemplateError

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)

_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)


class EmailNode(BaseNode):
    """Send an HTML email using SMTP credentials from the execution context."""

    node_type = NodeType.EMAIL

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        template_vars = {**context.variables, "data": input_data}

        # Render fields
        try:
            to_addr = _jinja_env.from_string(config["to"]).render(template_vars)
            subject = _jinja_env.from_string(config.get("subject", "(no subject)")).render(template_vars)
            body_html = _jinja_env.from_string(config.get("body", "")).render(template_vars)
        except (TemplateError, KeyError) as exc:
            return NodeOutput(data={}, metadata={"error": f"Template error: {exc}"})

        # Resolve SMTP credential
        cred_name: str = config.get("credential", "")
        cred_values: dict[str, Any] = context.credentials.get(cred_name, {})

        smtp_host: str = cred_values.get("host", "")
        smtp_port: int = int(cred_values.get("port", 587))
        smtp_user: str = cred_values.get("username", "")
        smtp_password: str = cred_values.get("password", "")
        smtp_from: str = cred_values.get("from_address", smtp_user)

        if not smtp_host:
            return NodeOutput(data={}, metadata={"error": "No SMTP host configured in credential"})

        # Build MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to_addr
        msg["Date"] = formatdate(localtime=True)
        message_id = make_msgid()
        msg["Message-ID"] = message_id
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user or None,
                password=smtp_password or None,
                start_tls=smtp_port in (587, 465),
            )
        except aiosmtplib.SMTPException as exc:
            return NodeOutput(data={}, metadata={"error": f"SMTP error: {exc}"})

        return NodeOutput(
            data={"sent": True, "message_id": message_id, "to": to_addr, "subject": subject}
        )


registry.register(EmailNode())
