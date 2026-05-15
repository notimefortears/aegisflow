"""Execution ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.shared_types import ExecutionStatus


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status"),
        nullable=False,
        default=ExecutionStatus.PENDING,
    )
    # "manual" | "webhook:{id}" | "schedule"
    trigger: Mapped[str] = mapped_column(String(128), nullable=False)

    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Stores dict[node_id, NodeExecutionRecord] serialised to JSON
    node_states: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    workflow: Mapped["app.models.workflow.Workflow"] = relationship(  # type: ignore[name-defined]
        "Workflow", back_populates="executions"
    )
    triggered_by: Mapped["app.models.user.User | None"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="executions"
    )

    def __repr__(self) -> str:
        return f"<Execution id={self.id} status={self.status}>"
