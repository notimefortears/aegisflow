"""FastAPI dependency helpers (auth, DB, Redis, CredentialVault)."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

import redis.asyncio as aioredis
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.shared_types import UserRole

# ── Password hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
security_scheme = HTTPBearer()


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    from datetime import datetime, timedelta, timezone

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": user_id, "type": "access", "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: str) -> str:
    from datetime import datetime, timedelta, timezone

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    return jwt.encode(
        {"sub": user_id, "type": "refresh", "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def _decode_token(token: str, expected_type: str) -> str:
    """Decode a JWT and return the subject (user_id). Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise JWTError("wrong token type")
        sub: str | None = payload.get("sub")
        if sub is None:
            raise JWTError("missing sub")
        return sub
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Redis pool ────────────────────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis_pool


# ── Current user dependency ───────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> User:
    user_id = _decode_token(credentials.credentials, "access")

    # Check token not blacklisted
    blacklisted = await redis.get(f"blacklist:{credentials.credentials}")
    if blacklisted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user: User | None = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return current_user


def require_roles(*roles: UserRole):
    """Return a dependency that enforces role-based access."""

    async def _check(user: Annotated[User, Depends(get_current_active_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check


require_admin = require_roles(UserRole.ADMIN)
require_editor_or_above = require_roles(UserRole.ADMIN, UserRole.EDITOR)


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginationParams:
    def __init__(
        self,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


# ── Credential encryption (Fernet / AES-256) ──────────────────────────────────

class CredentialVault:
    """Encrypts/decrypts credential value blobs using Fernet (AES-256-CBC + HMAC)."""

    def __init__(self) -> None:
        self._fernet = Fernet(settings.credential_encryption_key.encode())

    def encrypt(self, values: dict) -> str:
        plaintext = json.dumps(values).encode()
        return self._fernet.encrypt(plaintext).decode()

    def decrypt(self, token: str) -> dict:
        try:
            plaintext = self._fernet.decrypt(token.encode())
            return json.loads(plaintext)
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt credential — key mismatch or corruption") from exc


vault = CredentialVault()
