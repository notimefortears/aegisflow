"""Credential ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # CredentialType value string (e.g. "anthropic_api_key", "smtp", "http_bearer")
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    # AES-256 encrypted JSON blob (Fernet)
    encrypted_values: Mapped[str] = mapped_column(Text, nullable=False)

    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # relationships
    created_by: Mapped["app.models.user.User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="credentials"
    )

    def __repr__(self) -> str:
        return f"<Credential id={self.id} name={self.name!r} type={self.type!r}>"
