"""AegisFlow FastAPI application entry point."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

logger = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown tasks."""
    from app.database import create_tables
    from app.api.deps import get_redis

    logger.info("aegisflow.startup", environment=settings.environment)

    # Create DB tables (safe no-op if tables exist)
    await create_tables()

    # Ensure initial admin user exists
    await _ensure_initial_admin()

    # Warm up Redis connection
    redis = await get_redis()
    await redis.ping()
    logger.info("redis.connected")

    yield

    logger.info("aegisflow.shutdown")


async def _ensure_initial_admin() -> None:
    from sqlalchemy import select

    from app.api.deps import hash_password
    from app.database import AsyncSessionMaker
    from app.models.user import User
    from app.shared_types import UserRole

    async with AsyncSessionMaker() as db:
        result = await db.execute(
            select(User).where(User.email == settings.initial_admin_email)
        )
        if result.scalar_one_or_none() is not None:
            return

        admin = User(
            id=uuid.uuid4(),
            email=settings.initial_admin_email,
            name="Admin",
            hashed_password=hash_password(settings.initial_admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        logger.info("admin.created", email=settings.initial_admin_email)


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="AegisFlow",
    description="Workflow Automation with Built-in Security",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)


# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    import time

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

from app.api import auth, workflows, executions, credentials, websocket, gates, admin  # noqa: E402

API_PREFIX = "/api"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(workflows.router, prefix=API_PREFIX)
app.include_router(executions.router, prefix=API_PREFIX)
app.include_router(credentials.router, prefix=API_PREFIX)
app.include_router(gates.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
# WebSocket uses its own path prefix inside the router
app.include_router(websocket.router)


# ── Health endpoint ───────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}
