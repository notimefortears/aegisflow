"""Workflow request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.shared_types import WorkflowDefinition


# ── Request schemas ───────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    definition: WorkflowDefinition
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    definition: WorkflowDefinition | None = None
    tags: list[str] | None = None


class WorkflowExecuteRequest(BaseModel):
    trigger_data: dict[str, Any] = Field(default_factory=dict)


# ── Response schemas ──────────────────────────────────────────────────────────

class WorkflowListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    last_executed_at: datetime | None
    execution_count: int
    success_count: int
    failure_count: int

    model_config = {"from_attributes": True}


class WorkflowDetail(WorkflowListItem):
    definition: dict[str, Any]
    created_by_id: uuid.UUID | None


class WorkflowExecuteResponse(BaseModel):
    execution_id: uuid.UUID
    status: str
