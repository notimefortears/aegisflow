"""Workflow ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Stores a serialised WorkflowDefinition dict
    definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON array of string tags
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # relationships
    created_by: Mapped["app.models.user.User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="workflows"
    )
    executions: Mapped[list["app.models.execution.Execution"]] = relationship(  # type: ignore[name-defined]
        "Execution", back_populates="workflow", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Workflow id={self.id} name={self.name!r}>"
