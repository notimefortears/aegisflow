"""Execution request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.shared_types import ExecutionStatus


# ── Response schemas ──────────────────────────────────────────────────────────

class ExecutionListItem(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: ExecutionStatus
    trigger: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    error: str | None

    model_config = {"from_attributes": True}


class ExecutionDetail(ExecutionListItem):
    triggered_by_id: uuid.UUID | None
    node_states: dict[str, Any]
