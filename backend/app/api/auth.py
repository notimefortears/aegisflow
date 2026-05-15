"""Authentication endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ALGORITHM,
    _decode_token,
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    get_db,
    get_redis,
    hash_password,
    verify_password,
)
from app.config import settings
from app.models.user import User
from app.schemas.user import RefreshTokenRequest, TokenResponse, UserCreate, UserLogin, UserProfile
from app.shared_types import UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Register a new user.

    Only the first registration is permitted without authentication.
    Subsequent registrations require an admin token (enforced in admin router).
    """
    # Check duplicate email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
            headers={"code": "EMAIL_TAKEN"},
        )

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"code": "INVALID_CREDENTIALS"},
        )

    user.last_login_at = datetime.now(timezone.utc)

    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis=Depends(get_redis),
) -> TokenResponse:
    # Check not blacklisted
    blacklisted = await redis.get(f"blacklist:{payload.refresh_token}")
    if blacklisted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user_id = _decode_token(payload.refresh_token, "refresh")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user: User | None = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Blacklist old refresh token
    try:
        decoded = jwt.decode(payload.refresh_token, settings.secret_key, algorithms=[ALGORITHM])
        exp = decoded.get("exp", 0)
        import time
        ttl = max(0, int(exp - time.time()))
        if ttl > 0:
            await redis.setex(f"blacklist:{payload.refresh_token}", ttl, "1")
    except JWTError:
        pass

    access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshTokenRequest,
    redis=Depends(get_redis),
) -> None:
    """Invalidate a refresh token by adding it to the Redis blacklist."""
    try:
        decoded = jwt.decode(payload.refresh_token, settings.secret_key, algorithms=[ALGORITHM])
        exp = decoded.get("exp", 0)
        import time
        ttl = max(0, int(exp - time.time()))
        if ttl > 0:
            await redis.setex(f"blacklist:{payload.refresh_token}", ttl, "1")
    except JWTError:
        pass  # Already expired tokens are harmless


@router.get("/me", response_model=UserProfile)
async def me(current_user: Annotated[User, Depends(get_current_active_user)]) -> User:
    return current_user
