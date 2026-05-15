"""Admin-only endpoints."""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaginationParams, get_db, require_admin
from app.models.audit_log import AuditLog
from app.models.execution import Execution
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.user import PaginatedResponse, UserProfile, UserUpdateRole
from app.shared_types import ExecutionStatus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> PaginatedResponse:
    total: int = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    rows = (
        await db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()

    return PaginatedResponse(
        items=[UserProfile.model_validate(u) for u in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=max(1, math.ceil(total / pagination.page_size)),
    )


@router.put("/users/{user_id}/role", response_model=UserProfile)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UserUpdateRole,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserProfile:
    from fastapi import HTTPException, status

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = payload.role
    await db.flush()
    return UserProfile.model_validate(user)


class AuditLogItem(UserProfile.__class__):
    pass


from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    audit_id: str
    execution_id: str | None
    node_id: str | None
    event_type: str
    risk_score: float | None
    data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/audit", response_model=PaginatedResponse)
async def audit_log(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    event_type: str | None = Query(default=None),
    execution_id: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
) -> PaginatedResponse:
    q = select(AuditLog)
    if event_type:
        q = q.where(AuditLog.event_type == event_type)
    if execution_id:
        q = q.where(AuditLog.execution_id == execution_id)
    if from_date:
        q = q.where(AuditLog.created_at >= from_date)
    if to_date:
        q = q.where(AuditLog.created_at <= to_date)

    total: int = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (
        await db.execute(
            q.order_by(AuditLog.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()

    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=max(1, math.ceil(total / pagination.page_size)),
    )


class DashboardStats(BaseModel):
    total_workflows: int
    active_workflows: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    pii_detections: int
    injection_blocks: int


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> DashboardStats:
    total_workflows: int = (await db.execute(select(func.count()).select_from(Workflow))).scalar_one()
    active_workflows: int = (
        await db.execute(select(func.count()).select_from(Workflow).where(Workflow.is_active == True))  # noqa: E712
    ).scalar_one()
    total_executions: int = (await db.execute(select(func.count()).select_from(Execution))).scalar_one()
    successful: int = (
        await db.execute(
            select(func.count()).select_from(Execution).where(Execution.status == ExecutionStatus.SUCCESS)
        )
    ).scalar_one()
    failed: int = (
        await db.execute(
            select(func.count()).select_from(Execution).where(Execution.status == ExecutionStatus.FAILED)
        )
    ).scalar_one()
    pii_detections: int = (
        await db.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.event_type == "pii_detected")
        )
    ).scalar_one()
    injection_blocks: int = (
        await db.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.event_type == "injection_blocked")
        )
    ).scalar_one()

    success_rate = (successful / total_executions) if total_executions > 0 else 0.0

    return DashboardStats(
        total_workflows=total_workflows,
        active_workflows=active_workflows,
        total_executions=total_executions,
        successful_executions=successful,
        failed_executions=failed,
        success_rate=round(success_rate, 4),
        pii_detections=pii_detections,
        injection_blocks=injection_blocks,
    )
