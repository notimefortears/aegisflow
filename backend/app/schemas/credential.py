"""Credential request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class CredentialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=64)
    # Raw values to be encrypted; never stored or returned in plain text
    values: dict[str, Any]


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    values: dict[str, Any] | None = None


# ── Response schemas ──────────────────────────────────────────────────────────

class CredentialResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CredentialTestResponse(BaseModel):
    success: bool
    message: str
