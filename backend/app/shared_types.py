"""
Shared types used across the entire AegisFlow backend.
All agents must import from this file — do not redefine these types.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Enums ────────────────────────────────────────────────────────────────────

class NodeType(str, Enum):
    # Triggers
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    # Providers
    CLAUDE = "claude"
    OPENAI = "openai"
    # Security
    PII_SCANNER = "pii_scanner"
    INJECTION_GUARD = "injection_guard"
    HUMAN_GATE = "human_gate"
    # Integrations
    HTTP = "http"
    EMAIL = "email"
    DATABASE = "database"
    # Logic
    CONDITION = "condition"
    TRANSFORM = "transform"
    MERGE = "merge"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"   # human gate paused


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    RUNNER = "runner"    # can only trigger executions


class PIICategory(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    PASSPORT = "passport"
    MEDICAL = "medical"


class PolicyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REDACT = "redact"
    ALERT = "alert"
    REQUIRE_APPROVAL = "require_approval"


# ── Workflow Definition ───────────────────────────────────────────────────────

class WorkflowNodePosition(BaseModel):
    x: float
    y: float


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    position: WorkflowNodePosition
    disabled: bool = False


class WorkflowEdge(BaseModel):
    id: str
    source: str        # source node id
    source_handle: str  # "output" | "true" | "false"
    target: str        # target node id
    target_handle: str  # "input"


class WorkflowDefinition(BaseModel):
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    variables: dict[str, Any] = Field(default_factory=dict)


# ── Execution Types ───────────────────────────────────────────────────────────

class NodeOutput(BaseModel):
    """What every node must return from execute()."""
    data: dict[str, Any]
    branch: str = "output"          # "output" | "true" | "false" (condition)
    metadata: dict[str, Any] = Field(default_factory=dict)
    security_flags: list[str] = Field(default_factory=list)   # e.g. ["pii_detected", "injection_risk"]


class NodeExecutionRecord(BaseModel):
    node_id: str
    node_name: str
    node_type: NodeType
    status: NodeStatus
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    logs: list[str] = Field(default_factory=list)
    retry_count: int = 0


# ── Security Types ────────────────────────────────────────────────────────────

class PIIMatch(BaseModel):
    category: PIICategory
    value: str        # the raw matched value
    redacted: str     # e.g. "[REDACTED_EMAIL]"
    start: int        # char offset
    end: int
    confidence: float  # 0.0–1.0


class PIIScanResult(BaseModel):
    has_pii: bool
    matches: list[PIIMatch]
    redacted_text: str   # text with all PII replaced
    risk_score: float    # 0.0–1.0


class InjectionScanResult(BaseModel):
    is_safe: bool
    risk_score: float     # 0.0–1.0 (>0.7 = high risk)
    patterns_matched: list[str]
    explanation: str


class SecurityScanResult(BaseModel):
    pii: PIIScanResult
    injection: InjectionScanResult
    policy_actions: list[PolicyAction]
    blocked: bool
    audit_id: str


# ── Execution Context ─────────────────────────────────────────────────────────

class ExecutionContext:
    """Passed to every node.execute() call."""

    def __init__(
        self,
        execution_id: str,
        workflow_id: str,
        user_id: str,
        variables: dict[str, Any],
        credentials: dict[str, Any],   # decrypted credential values by name
        redis: "Redis",
        db: "AsyncSession",
        logger: logging.Logger,
    ) -> None:
        self.execution_id = execution_id
        self.workflow_id = workflow_id
        self.user_id = user_id
        self.variables = variables
        self.credentials = credentials
        self.redis = redis
        self.db = db
        self.logger = logger

    async def publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish a real-time event to the WebSocket channel."""
        import json
        payload = json.dumps({
            "type": event_type,
            "execution_id": self.execution_id,
            **data,
        })
        await self.redis.publish(f"executions:{self.execution_id}", payload)


# ── WebSocket Messages ────────────────────────────────────────────────────────

class WSEventType(str, Enum):
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    HUMAN_GATE_WAITING = "human_gate_waiting"
    LOG_LINE = "log_line"


# ── Node Config Schemas (used by frontend for rendering config panels) ────────

NODE_CONFIG_SCHEMAS: dict[NodeType, dict[str, Any]] = {
    NodeType.CLAUDE: {
        "model": {"type": "select", "options": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"], "default": "claude-sonnet-4-6"},
        "system_prompt": {"type": "textarea", "label": "System Prompt"},
        "user_message": {"type": "textarea", "label": "User Message (supports {{ variables }})"},
        "max_tokens": {"type": "number", "default": 2048, "min": 1, "max": 8192},
        "temperature": {"type": "number", "default": 0.7, "min": 0, "max": 1, "step": 0.1},
        "credential": {"type": "credential", "credentialType": "anthropic_api_key"},
        "timeout_seconds": {"type": "number", "default": 60},
        "retry": {"type": "number", "default": 2, "label": "Max Retries"},
    },
    NodeType.OPENAI: {
        "model": {"type": "select", "options": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"], "default": "gpt-4o"},
        "system_prompt": {"type": "textarea"},
        "user_message": {"type": "textarea"},
        "max_tokens": {"type": "number", "default": 2048},
        "temperature": {"type": "number", "default": 0.7},
        "credential": {"type": "credential", "credentialType": "openai_api_key"},
        "timeout_seconds": {"type": "number", "default": 60},
        "retry": {"type": "number", "default": 2},
    },
    NodeType.HTTP: {
        "url": {"type": "text", "label": "URL (supports {{ variables }})"},
        "method": {"type": "select", "options": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
        "headers": {"type": "keyvalue", "label": "Headers"},
        "body": {"type": "textarea", "label": "Body (JSON)"},
        "timeout_seconds": {"type": "number", "default": 30},
    },
    NodeType.CONDITION: {
        "field": {"type": "text", "label": "Field path (e.g. data.user.email)"},
        "operator": {"type": "select", "options": ["equals", "not_equals", "contains", "not_contains", "greater_than", "less_than", "regex_match", "is_empty", "is_not_empty"]},
        "value": {"type": "text", "label": "Compare value"},
    },
    NodeType.PII_SCANNER: {
        "scan_fields": {"type": "multiselect", "options": [c.value for c in PIICategory], "label": "PII categories to detect"},
        "action": {"type": "select", "options": [a.value for a in PolicyAction], "default": "alert"},
        "fail_on_detection": {"type": "boolean", "default": False},
    },
    NodeType.INJECTION_GUARD: {
        "threshold": {"type": "number", "default": 0.7, "min": 0, "max": 1, "step": 0.05, "label": "Risk score threshold (block above this)"},
        "scan_field": {"type": "text", "label": "Field to scan (e.g. data.user_input)"},
    },
    NodeType.HUMAN_GATE: {
        "approvers": {"type": "text", "label": "Approver emails (comma-separated)"},
        "timeout_hours": {"type": "number", "default": 24},
        "message": {"type": "textarea", "label": "Approval request message"},
    },
    NodeType.TRANSFORM: {
        "mappings": {"type": "keyvalue", "label": "Output field → Jinja2 template"},
        "remove_fields": {"type": "tags", "label": "Fields to remove"},
    },
    NodeType.EMAIL: {
        "to": {"type": "text", "label": "To (supports {{ variables }})"},
        "subject": {"type": "text"},
        "body": {"type": "textarea", "label": "Body (HTML supported)"},
        "credential": {"type": "credential", "credentialType": "smtp"},
    },
    NodeType.WEBHOOK: {
        "method": {"type": "select", "options": ["GET", "POST", "PUT"], "default": "POST"},
        "auth_type": {"type": "select", "options": ["none", "bearer", "basic", "hmac"], "default": "none"},
    },
    NodeType.SCHEDULE: {
        "cron": {"type": "text", "label": "Cron expression (e.g. 0 9 * * MON-FRI)"},
        "timezone": {"type": "text", "default": "UTC"},
    },
}
