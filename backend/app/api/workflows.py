"""Workflow CRUD and execution endpoints."""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    PaginationParams,
    get_current_active_user,
    get_db,
    require_editor_or_above,
)
from app.models.execution import Execution
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.execution import ExecutionListItem
from app.schemas.user import PaginatedResponse
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowDetail,
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowListItem,
    WorkflowUpdate,
)
from app.shared_types import ExecutionStatus

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _workflow_to_detail(wf: Workflow) -> WorkflowDetail:
    return WorkflowDetail.model_validate(wf)


@router.get("", response_model=PaginatedResponse)
async def list_workflows(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
    is_active: bool | None = Query(default=None),
    tags: list[str] = Query(default=[]),
) -> PaginatedResponse:
    q = select(Workflow)
    if is_active is not None:
        q = q.where(Workflow.is_active == is_active)

    total_q = select(func.count()).select_from(q.subquery())
    total: int = (await db.execute(total_q)).scalar_one()

    rows = (
        await db.execute(
            q.order_by(Workflow.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()

    # Filter by tag in Python (JSON array — avoid DB-specific operators)
    if tags:
        rows = [wf for wf in rows if any(t in (wf.tags or []) for t in tags)]

    return PaginatedResponse(
        items=[WorkflowListItem.model_validate(wf) for wf in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=max(1, math.ceil(total / pagination.page_size)),
    )


@router.post("", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_above)],
) -> WorkflowDetail:
    wf = Workflow(
        id=uuid.uuid4(),
        name=payload.name,
        description=payload.description,
        definition=payload.definition.model_dump(),
        is_active=payload.is_active,
        tags=payload.tags,
        created_by_id=current_user.id,
    )
    db.add(wf)
    await db.flush()
    return _workflow_to_detail(wf)


@router.get("/{workflow_id}", response_model=WorkflowDetail)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> WorkflowDetail:
    wf = await _get_or_404(db, workflow_id)
    return _workflow_to_detail(wf)


@router.put("/{workflow_id}", response_model=WorkflowDetail)
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_editor_or_above)],
) -> WorkflowDetail:
    wf = await _get_or_404(db, workflow_id)
    if payload.name is not None:
        wf.name = payload.name
    if payload.description is not None:
        wf.description = payload.description
    if payload.definition is not None:
        wf.definition = payload.definition.model_dump()
    if payload.tags is not None:
        wf.tags = payload.tags
    await db.flush()
    return _workflow_to_detail(wf)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_editor_or_above)],
) -> None:
    wf = await _get_or_404(db, workflow_id)
    wf.is_active = False  # soft delete


@router.post("/{workflow_id}/activate", response_model=WorkflowDetail)
async def activate_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_editor_or_above)],
) -> WorkflowDetail:
    wf = await _get_or_404(db, workflow_id)
    wf.is_active = True
    await db.flush()
    return _workflow_to_detail(wf)


@router.post("/{workflow_id}/deactivate", response_model=WorkflowDetail)
async def deactivate_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_editor_or_above)],
) -> WorkflowDetail:
    wf = await _get_or_404(db, workflow_id)
    wf.is_active = False
    await db.flush()
    return _workflow_to_detail(wf)


@router.post("/{workflow_id}/execute", response_model=WorkflowExecuteResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowExecuteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> WorkflowExecuteResponse:
    from app.workers.tasks import execute_workflow_task

    wf = await _get_or_404(db, workflow_id)
    if not wf.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not active",
            headers={"code": "WORKFLOW_INACTIVE"},
        )

    execution_id = uuid.uuid4()
    execution = Execution(
        id=execution_id,
        workflow_id=wf.id,
        status=ExecutionStatus.PENDING,
        trigger="manual",
        triggered_by_id=current_user.id,
        node_states={},
    )
    db.add(execution)
    await db.flush()

    execute_workflow_task.delay(
        str(wf.id),
        str(execution_id),
        payload.trigger_data,
        str(current_user.id),
    )

    return WorkflowExecuteResponse(execution_id=execution_id, status=ExecutionStatus.PENDING)


@router.get("/{workflow_id}/executions", response_model=PaginatedResponse)
async def workflow_executions(
    workflow_id: uuid.UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> PaginatedResponse:
    await _get_or_404(db, workflow_id)

    q = select(Execution).where(Execution.workflow_id == workflow_id)
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


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf: Workflow | None = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
            headers={"code": "NOT_FOUND"},
        )
    return wf
