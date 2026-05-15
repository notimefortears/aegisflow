"""Shared pytest fixtures for AegisFlow backend tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncClient:
    from app.api.deps import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    return db
