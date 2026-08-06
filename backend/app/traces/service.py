import json
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utc_now
from app.traces.models import AgentRun, AgentRunStep
from app.traces.schemas import RunDetailOut, RunListOut, RunOut, StepOut


async def create_run(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    run_type: str,
    model_id: str | None,
) -> AgentRun:
    run = AgentRun(
        workspace_id=workspace_id,
        run_type=run_type,
        model_id=model_id,
    )
    db.add(run)
    await db.flush()
    return run


async def add_step(
    db: AsyncSession,
    run: AgentRun,
    step_name: str,
    status: str = "running",
    input_summary: str | None = None,
    output_summary: str | None = None,
    retrieved_chunks: list[dict] | None = None,
    latency_ms: int | None = None,
    error_code: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> AgentRunStep:
    step = AgentRunStep(
        run_id=run.id,
        step_name=step_name,
        status=status,
        input_summary=input_summary[:500] if input_summary else None,
        output_summary=output_summary[:500] if output_summary else None,
        retrieved_chunks=json.dumps(retrieved_chunks, ensure_ascii=False) if retrieved_chunks else None,
        latency_ms=latency_ms or 0,
        error_code=error_code[:500] if error_code else None,
        started_at=started_at or utc_now(),
        completed_at=completed_at,
    )
    db.add(step)
    await db.flush()
    return step


async def finalize_run(
    db: AsyncSession,
    run: AgentRun,
    status: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
    error_code: str | None = None,
) -> None:
    run.status = status
    run.prompt_tokens = prompt_tokens
    run.completion_tokens = completion_tokens
    run.total_tokens = prompt_tokens + completion_tokens
    run.latency_ms = latency_ms
    run.error_code = error_code[:500] if error_code else None
    run.completed_at = utc_now()
    await db.flush()


async def list_runs(
    db: AsyncSession, workspace_id: uuid.UUID, limit: int = 20, offset: int = 0,
) -> RunListOut:
    total = (
        await db.scalar(
            select(func.count()).select_from(AgentRun).where(
                AgentRun.workspace_id == workspace_id
            )
        )
    ) or 0
    runs = list(
        (
            await db.scalars(
                select(AgentRun)
                .where(AgentRun.workspace_id == workspace_id)
                .order_by(AgentRun.started_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    return RunListOut(
        runs=[RunOut.model_validate(r) for r in runs],
        total=total,
    )


async def get_run_detail(db: AsyncSession, run: AgentRun) -> RunDetailOut:
    steps = list(
        (
            await db.scalars(
                select(AgentRunStep)
                .where(AgentRunStep.run_id == run.id)
                .order_by(AgentRunStep.started_at)
            )
        ).all()
    )
    return RunDetailOut(
        id=run.id,
        workspace_id=run.workspace_id,
        run_type=run.run_type,
        status=run.status,
        model_id=run.model_id,
        total_tokens=run.total_tokens,
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
        latency_ms=run.latency_ms,
        error_code=run.error_code,
        started_at=run.started_at,
        completed_at=run.completed_at,
        steps=[StepOut.model_validate(s) for s in steps],
    )