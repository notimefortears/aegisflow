"""Credential CRUD and test endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_db,
    require_editor_or_above,
    vault,
)
from app.models.credential import Credential
from app.models.user import User
from app.schemas.credential import (
    CredentialCreate,
    CredentialResponse,
    CredentialTestResponse,
    CredentialUpdate,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.get("", response_model=list[CredentialResponse])
async def list_credentials(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> list[CredentialResponse]:
    rows = (await db.execute(select(Credential).order_by(Credential.name))).scalars().all()
    return [CredentialResponse.model_validate(r) for r in rows]


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CredentialCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_above)],
) -> CredentialResponse:
    encrypted = vault.encrypt(payload.values)
    cred = Credential(
        id=uuid.uuid4(),
        name=payload.name,
        type=payload.type,
        encrypted_values=encrypted,
        created_by_id=current_user.id,
    )
    db.add(cred)
    await db.flush()
    return CredentialResponse.model_validate(cred)


@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    payload: CredentialUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_editor_or_above)],
) -> CredentialResponse:
    cred = await _get_or_404(db, credential_id)
    if payload.name is not None:
        cred.name = payload.name
    if payload.values is not None:
        cred.encrypted_values = vault.encrypt(payload.values)
    await db.flush()
    return CredentialResponse.model_validate(cred)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_editor_or_above)],
) -> None:
    cred = await _get_or_404(db, credential_id)
    await db.delete(cred)


@router.post("/{credential_id}/test", response_model=CredentialTestResponse)
async def test_credential(
    credential_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> CredentialTestResponse:
    cred = await _get_or_404(db, credential_id)
    try:
        values = vault.decrypt(cred.encrypted_values)
    except ValueError:
        return CredentialTestResponse(success=False, message="Decryption failed — key mismatch")

    success, message = await _test_connectivity(cred.type, values)
    return CredentialTestResponse(success=success, message=message)


async def _test_connectivity(cred_type: str, values: dict) -> tuple[bool, str]:
    """Basic connectivity test per credential type."""
    import aiohttp

    try:
        if cred_type == "anthropic_api_key":
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": values.get("api_key", ""), "anthropic-version": "2023-06-01"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status < 500, f"HTTP {resp.status}"

        elif cred_type == "openai_api_key":
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {values.get('api_key', '')}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status < 500, f"HTTP {resp.status}"

        elif cred_type == "smtp":
            import aiosmtplib
            smtp = aiosmtplib.SMTP(
                hostname=values.get("host", ""),
                port=int(values.get("port", 587)),
                timeout=10,
            )
            await smtp.connect()
            await smtp.quit()
            return True, "SMTP connection successful"

        else:
            return True, f"No test available for credential type '{cred_type}'"

    except Exception as exc:
        return False, str(exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, credential_id: uuid.UUID) -> Credential:
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    cred: Credential | None = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
            headers={"code": "NOT_FOUND"},
        )
    return cred
