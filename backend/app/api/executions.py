"""Execution list, detail, and cancel endpoints."""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaginationParams, get_current_active_user, get_db, get_redis
from app.models.execution import Execution
from app.models.user import User
from app.schemas.execution import ExecutionDetail, ExecutionListItem
from app.schemas.user import PaginatedResponse
from app.shared_types import ExecutionStatus

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=PaginatedResponse)
async def list_executions(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
    workflow_id: uuid.UUID | None = Query(default=None),
    execution_status: ExecutionStatus | None = Query(default=None, alias="status"),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
) -> PaginatedResponse:
    q = select(Execution)
    if workflow_id is not None:
        q = q.where(Execution.workflow_id == workflow_id)
    if execution_status is not None:
        q = q.where(Execution.status == execution_status)
    if from_date is not None:
        q = q.where(Execution.started_at >= from_date)
    if to_date is not None:
        q = q.where(Execution.started_at <= to_date)

    total: int = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (
        await db.execute(
            q.order_by(Execution.started_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()

    return PaginatedResponse(
        items=[ExecutionListItem.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=max(1, math.ceil(total / pagination.page_size)),
    )


@router.get("/{execution_id}", response_model=ExecutionDetail)
async def get_execution(
    execution_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> ExecutionDetail:
    execution = await _get_or_404(db, execution_id)
    return ExecutionDetail.model_validate(execution)


@router.post("/{execution_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_execution(
    execution_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
    redis=Depends(get_redis),
) -> dict:
    execution = await _get_or_404(db, execution_id)
    if execution.status not in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execution is not in a cancellable state",
            headers={"code": "NOT_CANCELLABLE"},
        )

    # Signal the worker to stop via Redis
    await redis.set(f"cancel:{execution_id}", "1", ex=3600)

    return {"detail": "Cancellation signal sent", "execution_id": str(execution_id)}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, execution_id: uuid.UUID) -> Execution:
    result = await db.execute(select(Execution).where(Execution.id == execution_id))
    execution: Execution | None = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
            headers={"code": "NOT_FOUND"},
        )
    return execution
