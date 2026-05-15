"""Celery tasks for async workflow execution."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="execute_workflow", bind=True, max_retries=0)
def execute_workflow_task(
    self,
    workflow_id: str,
    execution_id: str,
    trigger_data: dict,
    user_id: str,
) -> dict:
    """Execute a workflow asynchronously. Returns final execution status."""
    return asyncio.get_event_loop().run_until_complete(
        _run(self, workflow_id, execution_id, trigger_data, user_id)
    )


async def _run(
    task,
    workflow_id: str,
    execution_id: str,
    trigger_data: dict,
    user_id: str,
) -> dict:
    from sqlalchemy import select, update

    from app.core.engine import WorkflowEngine
    from app.core.nodes.base import registry
    from app.database import AsyncSessionMaker
    from app.models.execution import Execution
    from app.models.workflow import Workflow
    from app.shared_types import ExecutionContext, ExecutionStatus
    import redis.asyncio as aioredis
    from app.config import settings

    log = logger.bind(execution_id=execution_id, workflow_id=workflow_id)
    log.info("task.execute_workflow.start")

    redis_client = aioredis.from_url(settings.redis_url)

    try:
        async with AsyncSessionMaker() as db:
            # Load workflow
            result = await db.execute(
                select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
            )
            workflow_row = result.scalar_one_or_none()
            if workflow_row is None:
                log.error("workflow.not_found")
                return {"status": "failed", "error": "Workflow not found"}

            # Load decrypted credentials for this user
            from app.core.auth_core import CredentialVault
            from app.models.credential import Credential
            import json

            creds_result = await db.execute(select(Credential))
            credentials: dict = {}
            vault = CredentialVault(settings.credential_encryption_key)
            for cred in creds_result.scalars():
                try:
                    credentials[cred.name] = json.loads(vault.decrypt(cred.encrypted_values))
                except Exception:
                    pass

            ctx = ExecutionContext(
                execution_id=execution_id,
                workflow_id=workflow_id,
                user_id=user_id,
                variables=workflow_row.definition.get("variables", {}),
                credentials=credentials,
                redis=redis_client,
                db=db,
                logger=log,
            )

            from app.shared_types import WorkflowDefinition
            definition = WorkflowDefinition(**workflow_row.definition)

            engine = WorkflowEngine(redis=redis_client, node_registry=registry)
            status = await engine.execute(
                workflow=definition,
                workflow_id=workflow_id,
                execution_id=execution_id,
                trigger_data=trigger_data,
                context=ctx,
            )

            # Update execution record
            await db.execute(
                update(Execution)
                .where(Execution.id == uuid.UUID(execution_id))
                .values(
                    status=status,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            # Increment workflow counters
            if status == ExecutionStatus.SUCCESS:
                await db.execute(
                    update(Workflow)
                    .where(Workflow.id == uuid.UUID(workflow_id))
                    .values(
                        execution_count=Workflow.execution_count + 1,
                        success_count=Workflow.success_count + 1,
                        last_executed_at=datetime.now(timezone.utc),
                    )
                )
            else:
                await db.execute(
                    update(Workflow)
                    .where(Workflow.id == uuid.UUID(workflow_id))
                    .values(
                        execution_count=Workflow.execution_count + 1,
                        failure_count=Workflow.failure_count + 1,
                    )
                )
            await db.commit()

            log.info("task.execute_workflow.done", status=status)
            return {"status": status, "execution_id": execution_id}

    except Exception as exc:
        log.exception("task.execute_workflow.error", error=str(exc))
        return {"status": "failed", "error": str(exc)}
    finally:
        await redis_client.aclose()
