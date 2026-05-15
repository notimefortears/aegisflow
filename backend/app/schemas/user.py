"""User-related request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.shared_types import UserRole


# ── Request schemas ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdateRole(BaseModel):
    role: UserRole


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ── Response schemas ──────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ── Paginated helpers (generic) ───────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
