"""WebSocket endpoint for real-time execution events."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import select

from app.api.deps import ALGORITHM, get_redis
from app.config import settings
from app.database import AsyncSessionMaker
from app.models.user import User

router = APIRouter(tags=["websocket"])
logger = structlog.get_logger(__name__)


@router.websocket("/ws/executions/{execution_id}")
async def execution_ws(
    websocket: WebSocket,
    execution_id: str,
    token: str = "",
) -> None:
    """Stream real-time execution events to the client.

    Authentication: pass ?token=<access_token> as a query parameter.
    The endpoint subscribes to the Redis pub/sub channel
    ``executions:{execution_id}`` and forwards every JSON message to the
    connected WebSocket until the execution completes or the client disconnects.
    """
    # Authenticate before accepting
    if not token:
        token = websocket.query_params.get("token", "")

    if not await _authenticate_ws(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    redis = await get_redis()
    pubsub = redis.pubsub()
    channel = f"executions:{execution_id}"
    await pubsub.subscribe(channel)

    logger.info("ws.connected", execution_id=execution_id)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data: str = message["data"]
            await websocket.send_text(data)

            # Close once the terminal event arrives
            if '"execution_completed"' in data or '"execution_failed"' in data:
                break

    except WebSocketDisconnect:
        logger.info("ws.disconnected", execution_id=execution_id)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("ws.error", execution_id=execution_id, error=str(exc))
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        logger.info("ws.closed", execution_id=execution_id)


async def _authenticate_ws(token: str) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return False
        user_id = payload.get("sub")
        if user_id is None:
            return False

        async with AsyncSessionMaker() as db:
            result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user: User | None = result.scalar_one_or_none()
            return user is not None and user.is_active

    except (JWTError, ValueError):
        return False
