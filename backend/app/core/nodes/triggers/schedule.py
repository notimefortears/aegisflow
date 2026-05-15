"""Schedule trigger node.

Uses APScheduler to register cron-based jobs that enqueue workflow executions
via Celery.  The node's ``execute`` method is called by the engine when a
scheduled run fires — at that point the trigger_data contains scheduling metadata.
"""

from __future__ import annotations

from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.nodes.base import BaseNode, registry
from app.shared_types import ExecutionContext, NodeOutput, NodeType

logger = structlog.get_logger(__name__)

# Module-level scheduler singleton — started/stopped by the lifespan or worker
scheduler = AsyncIOScheduler()


class ScheduleTriggerNode(BaseNode):
    """Cron-based schedule trigger node.

    When the workflow engine calls ``execute`` for a SCHEDULE node, it simply
    passes through the scheduled trigger metadata as output.  Actual scheduling
    is managed separately via ``register_schedule`` / ``remove_schedule``.
    """

    node_type = NodeType.SCHEDULE

    async def execute(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> NodeOutput:
        cron_expr: str = config.get("cron", "")
        timezone: str = config.get("timezone", "UTC")

        logger.info(
            "schedule.trigger",
            cron=cron_expr,
            timezone=timezone,
            execution_id=context.execution_id,
        )

        return NodeOutput(
            data={
                "scheduled_cron": cron_expr,
                "timezone": timezone,
                "trigger_metadata": input_data,
            }
        )

    @staticmethod
    def register_schedule(
        workflow_id: str,
        cron_expr: str,
        timezone: str = "UTC",
    ) -> str:
        """Register a cron job that enqueues a workflow execution."""
        from app.workers.tasks import execute_workflow_task

        job_id = f"schedule:{workflow_id}"

        # Remove existing job for this workflow if present
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(
            func=_enqueue_scheduled_execution,
            trigger=CronTrigger.from_crontab(cron_expr, timezone=timezone),
            id=job_id,
            args=[workflow_id],
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info("schedule.registered", workflow_id=workflow_id, cron=cron_expr)
        return job_id

    @staticmethod
    def remove_schedule(workflow_id: str) -> None:
        job_id = f"schedule:{workflow_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info("schedule.removed", workflow_id=workflow_id)


async def _enqueue_scheduled_execution(workflow_id: str) -> None:
    """Callback fired by APScheduler — enqueues a Celery task."""
    import uuid

    from app.database import AsyncSessionMaker
    from app.models.execution import Execution
    from app.shared_types import ExecutionStatus
    from app.workers.tasks import execute_workflow_task

    execution_id = uuid.uuid4()
    async with AsyncSessionMaker() as db:
        execution = Execution(
            id=execution_id,
            workflow_id=uuid.UUID(workflow_id),
            status=ExecutionStatus.PENDING,
            trigger="schedule",
            triggered_by_id=None,
            node_states={},
        )
        db.add(execution)
        await db.commit()

    execute_workflow_task.delay(workflow_id, str(execution_id), {}, "system")
    logger.info("schedule.execution_enqueued", workflow_id=workflow_id, execution_id=str(execution_id))


registry.register(ScheduleTriggerNode())
