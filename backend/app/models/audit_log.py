"""AuditLog ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    audit_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # e.g. "pii_detected", "injection_blocked", "human_gate_approved"
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} event_type={self.event_type!r}>"
