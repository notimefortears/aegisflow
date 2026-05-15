"""Human gate approval/rejection endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db, get_redis
from app.models.audit_log import AuditLog
from app.models.execution import Execution
from app.models.user import User
from app.shared_types import ExecutionStatus, NodeStatus

router = APIRouter(prefix="/gates", tags=["gates"])

_GATE_KEY_PREFIX = "gate:"


class GateDecisionRequest(BaseModel):
    comment: str = ""


class GateRejectRequest(BaseModel):
    reason: str


class GateItem(BaseModel):
    gate_id: str
    execution_id: str
    node_id: str
    node_name: str
    message: str
    approver_emails: list[str]


@router.get("", response_model=list[GateItem])
async def list_pending_gates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    redis=Depends(get_redis),
) -> list[GateItem]:
    """Return all pending human gates for the current user."""
    keys = await redis.keys(f"{_GATE_KEY_PREFIX}*")
    gates: list[GateItem] = []
    for key in keys:
        raw = await redis.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        approvers: list[str] = data.get("approver_emails", [])
        if current_user.email in approvers or current_user.role.value == "admin":
            gates.append(
                GateItem(
                    gate_id=key.removeprefix(_GATE_KEY_PREFIX),
                    execution_id=data.get("execution_id", ""),
                    node_id=data.get("node_id", ""),
                    node_name=data.get("node_name", ""),
                    message=data.get("message", ""),
                    approver_emails=approvers,
                )
            )
    return gates


@router.post("/{gate_id}/approve", status_code=status.HTTP_200_OK)
async def approve_gate(
    gate_id: str,
    payload: GateDecisionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis=Depends(get_redis),
) -> dict:
    gate_data = await _get_gate_or_404(gate_id, redis)
    _check_permission(current_user, gate_data)

    execution_id = gate_data["execution_id"]
    node_id = gate_data["node_id"]

    # Signal approval
    await redis.set(f"gate_decision:{gate_id}", json.dumps({"approved": True, "comment": payload.comment}), ex=3600)

    # Remove pending gate entry
    await redis.delete(f"{_GATE_KEY_PREFIX}{gate_id}")

    # Audit log
    log = AuditLog(
        id=uuid.uuid4(),
        audit_id=f"gate-approve-{gate_id}",
        execution_id=execution_id,
        node_id=node_id,
        event_type="human_gate_approved",
        data={
            "gate_id": gate_id,
            "approved_by": current_user.email,
            "comment": payload.comment,
        },
    )
    db.add(log)

    # Publish event so workflow engine can resume
    channel = f"executions:{execution_id}"
    await redis.publish(
        channel,
        json.dumps({"type": "human_gate_approved", "execution_id": execution_id, "node_id": node_id, "gate_id": gate_id}),
    )

    return {"detail": "Gate approved", "gate_id": gate_id}


@router.post("/{gate_id}/reject", status_code=status.HTTP_200_OK)
async def reject_gate(
    gate_id: str,
    payload: GateRejectRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis=Depends(get_redis),
) -> dict:
    gate_data = await _get_gate_or_404(gate_id, redis)
    _check_permission(current_user, gate_data)

    execution_id = gate_data["execution_id"]
    node_id = gate_data["node_id"]

    await redis.set(
        f"gate_decision:{gate_id}",
        json.dumps({"approved": False, "reason": payload.reason}),
        ex=3600,
    )
    await redis.delete(f"{_GATE_KEY_PREFIX}{gate_id}")

    log = AuditLog(
        id=uuid.uuid4(),
        audit_id=f"gate-reject-{gate_id}",
        execution_id=execution_id,
        node_id=node_id,
        event_type="human_gate_rejected",
        data={
            "gate_id": gate_id,
            "rejected_by": current_user.email,
            "reason": payload.reason,
        },
    )
    db.add(log)

    await redis.publish(
        f"executions:{execution_id}",
        json.dumps({"type": "human_gate_rejected", "execution_id": execution_id, "node_id": node_id, "gate_id": gate_id, "reason": payload.reason}),
    )

    return {"detail": "Gate rejected", "gate_id": gate_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_gate_or_404(gate_id: str, redis) -> dict:
    raw = await redis.get(f"{_GATE_KEY_PREFIX}{gate_id}")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate not found or already decided",
            headers={"code": "NOT_FOUND"},
        )
    return json.loads(raw)


def _check_permission(user: User, gate_data: dict) -> None:
    approvers: list[str] = gate_data.get("approver_emails", [])
    if user.email not in approvers and user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not in the list of approvers for this gate",
            headers={"code": "FORBIDDEN"},
        )
