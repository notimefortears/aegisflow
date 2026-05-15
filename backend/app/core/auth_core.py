"""
Authentication & authorization primitives for AegisFlow.

This module provides:
- JWT access / refresh token issuance and verification.
- Bcrypt password hashing via passlib.
- A role → permission matrix and a FastAPI dependency factory for
  permission gating.
- A Fernet-based CredentialVault for at-rest credential encryption with
  key rotation support.

All functions are pure / stateless except for the CredentialVault, which
holds a Fernet key. Configuration is read from environment variables at
import time so the module can be used outside FastAPI (e.g. in workers).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.shared_types import UserRole


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("AEGIS_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("AEGIS_JWT_ALG", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AEGIS_ACCESS_TOKEN_EXP_MIN", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("AEGIS_REFRESH_TOKEN_EXP_DAYS", "14"))

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 password flow — the tokenUrl is informational only; the auth router
# implements the actual endpoint.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token for ``user_id`` with ``role`` claim.

    ``expires_delta`` defaults to ``ACCESS_TOKEN_EXPIRE_MINUTES`` from env.
    The payload contains ``sub``, ``role``, ``iat``, ``exp``, and ``type``.
    """
    expires = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value if isinstance(role, UserRole) else str(role),
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": expires,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a signed JWT refresh token for ``user_id``.

    Refresh tokens carry only a subject and a long expiry; they cannot be
    used to authenticate API requests directly (the ``type`` claim is checked
    by :func:`verify_token` callers).
    """
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": expires,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """Verify a JWT and return the decoded payload.

    Raises:
        JWTError: If the token is invalid, expired, or has a bad signature.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise
    if "sub" not in payload:
        raise JWTError("Token missing 'sub' claim")
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# Passwords
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash ``password`` with bcrypt (cost from passlib defaults)."""
    if not password:
        raise ValueError("password must be non-empty")
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash.

    Returns False instead of raising on any error so callers can treat this
    as a boolean check.
    """
    if not plain or not hashed:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# RBAC
# ─────────────────────────────────────────────────────────────────────────────

# Static role → permission matrix. Keep this in sync with the API surface.
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN: {
        "workflow:read", "workflow:write", "workflow:delete", "workflow:execute",
        "credential:read", "credential:write", "credential:delete",
        "user:read", "user:write",
        "execution:read", "audit:read",
    },
    UserRole.EDITOR: {
        "workflow:read", "workflow:write", "workflow:execute",
        "credential:read", "credential:write",
        "execution:read",
    },
    UserRole.VIEWER: {
        "workflow:read", "execution:read",
    },
    UserRole.RUNNER: {
        "workflow:read", "workflow:execute", "execution:read",
    },
}


def has_permission(role: UserRole | str, permission: str) -> bool:
    """Return True if ``role`` is granted ``permission`` by the matrix."""
    try:
        role_enum = role if isinstance(role, UserRole) else UserRole(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(role_enum, set())


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    """FastAPI dependency that resolves the current user from the bearer token.

    Returns the decoded JWT payload. Raises 401 if the token is missing,
    invalid, or not an access token.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh tokens cannot be used for API auth",
        )
    return payload


def require_permission(permission: str) -> Callable[..., dict[str, Any]]:
    """Return a FastAPI dependency that enforces ``permission``.

    Usage::

        @router.post("/workflows", dependencies=[Depends(require_permission("workflow:write"))])
        async def create_workflow(...): ...
    """

    def _dep(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        role = user.get("role")
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return user

    return _dep


# ─────────────────────────────────────────────────────────────────────────────
# Credential vault (Fernet / AES-256)
# ─────────────────────────────────────────────────────────────────────────────

class CredentialVault:
    """Encrypt / decrypt user credentials (API keys, SMTP passwords, …).

    Uses :class:`cryptography.fernet.Fernet` which provides AES-128 in CBC
    mode with HMAC-SHA256 for authentication (Fernet's "AES-256" naming
    refers to its 32-byte key — Fernet itself is AES-128-CBC + HMAC, which
    is the de-facto safe symmetric primitive for this kind of at-rest
    encryption).

    Key rotation: call :py:meth:`rotate_key` with the old and new keys to
    re-encrypt a token in place. For zero-downtime rotation you can also
    construct a vault with multiple keys (``MultiFernet``) by passing a
    comma-separated key list.
    """

    def __init__(self, encryption_key: str) -> None:
        if not encryption_key:
            raise ValueError("encryption_key must be non-empty")
        keys = [k.strip().encode() for k in encryption_key.split(",") if k.strip()]
        fernets = [Fernet(k) for k in keys]
        if not fernets:
            raise ValueError("encryption_key parse produced zero keys")
        self._fernet: Fernet | MultiFernet = (
            fernets[0] if len(fernets) == 1 else MultiFernet(fernets)
        )

    def encrypt(self, value: str) -> str:
        """Encrypt ``value`` (UTF-8) and return a URL-safe base64 token."""
        if value is None:
            raise ValueError("value must not be None")
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a Fernet token and return the original plaintext.

        Raises :class:`cryptography.fernet.InvalidToken` on tampering /
        wrong key.
        """
        if not encrypted:
            raise InvalidToken("encrypted token is empty")
        return self._fernet.decrypt(encrypted.encode("ascii")).decode("utf-8")

    def rotate_key(self, old_key: str, new_key: str, encrypted: str) -> str:
        """Re-encrypt ``encrypted`` from ``old_key`` to ``new_key``.

        This is the simple per-record rotation form — callers iterate every
        stored credential and write back the result. For high-volume
        rotation, construct a :class:`MultiFernet` and let it transparently
        decrypt with any old key, then re-encrypt with the primary.
        """
        old_vault = CredentialVault(old_key)
        new_vault = CredentialVault(new_key)
        plaintext = old_vault.decrypt(encrypted)
        return new_vault.encrypt(plaintext)


@lru_cache(maxsize=1)
def get_credential_vault() -> CredentialVault:
    """Process-wide singleton vault keyed off ``AEGIS_CREDENTIAL_KEY``."""
    key = os.getenv("AEGIS_CREDENTIAL_KEY")
    if not key:
        # Generate a fresh in-memory key for dev / tests. WARNING: data
        # encrypted with this key is unrecoverable after process restart.
        key = Fernet.generate_key().decode("ascii")
    return CredentialVault(key)


__all__ = [
    "ROLE_PERMISSIONS",
    "CredentialVault",
    "create_access_token",
    "create_refresh_token",
    "get_credential_vault",
    "get_current_user",
    "has_permission",
    "hash_password",
    "oauth2_scheme",
    "require_permission",
    "verify_password",
    "verify_token",
]
