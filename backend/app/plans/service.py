import json
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DASHSCOPE_CHAT_MODEL
from app.core.database import utc_now
from app.interviews.models import CompetencyMemory
from app.jobs.models import Competency
from app.jobs.service import competency_gap, normalize_competency
from app.plans.models import StudyPlan, StudyTask
from app.plans.schemas import PlanOut, TaskOut
from app.rag import gateway
from app.rag.gateway import AIServiceError
from app.traces.service import add_step, create_run, finalize_run
from app.workspaces.models import Workspace


class PlanError(RuntimeError):
    pass


async def _plan_tasks(db: AsyncSession, plan: StudyPlan) -> list[StudyTask]:
    return list(
        (
            await db.scalars(
                select(StudyTask)
                .where(StudyTask.plan_id == plan.id)
                .order_by(StudyTask.scheduled_date, StudyTask.priority.desc())
            )
        ).all()
    )


async def get_plan(db: AsyncSession, plan: StudyPlan) -> PlanOut:
    tasks = await _plan_tasks(db, plan)
    competency_ids = {t.competency_id for t in tasks if t.competency_id}
    competency_map = {}
    if competency_ids:
        rows = (
            await db.execute(
                select(Competency).where(Competency.id.in_(competency_ids))
            )
        ).scalars().all()
        competency_map = {c.id: c.canonical_name for c in rows}
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    return PlanOut(
        id=plan.id,
        workspace_id=plan.workspace_id,
        goal=plan.goal,
        start_date=plan.start_date,
        end_date=plan.end_date,
        version=plan.version,
        status=plan.status,
        created_at=plan.created_at,
        tasks=[
            TaskOut(
                id=t.id,
                competency_name=competency_map.get(t.competency_id),
                title=t.title,
                description=t.description,
                scheduled_date=t.scheduled_date,
                duration_minutes=t.duration_minutes,
                priority=t.priority,
                status=t.status,
                created_at=t.created_at,
            )
            for t in tasks
        ],
        total_tasks=total,
        completed_tasks=completed,
        coverage=round(completed / total * 100, 1) if total else 0.0,
    )


async def generate_plan(
    db: AsyncSession, workspace: Workspace, start_date: date, end_date: date, daily_minutes: int
) -> PlanOut:
    if await db.scalar(
        select(StudyPlan.id).where(
            StudyPlan.workspace_id == workspace.id,
            StudyPlan.status == "active",
        )
    ):
        raise PlanError("当前已有进行中的学习计划，请先归档再创建")
    plan = StudyPlan(
        workspace_id=workspace.id,
        goal=f"从 {start_date} 到 {end_date} 备战 {workspace.target_role or '目标岗位'}",
        start_date=start_date,
        end_date=end_date,
        status="active",
    )
    db.add(plan)
    await db.flush()

    gaps = await competency_gap(db, workspace.id)
    gap_items = [
        {
            "competency": g.competency,
            "category": g.category,
            "coverage": g.worst_coverage,
            "priority": g.priority,
        }
        for g in gaps[:15]
    ]
    memories = list(
        (
            await db.execute(
                select(CompetencyMemory).where(
                    CompetencyMemory.workspace_id == workspace.id,
                    CompetencyMemory.confirmed == True,
                )
            )
        ).scalars().all()
    )
    memory_items = [
        {
            "competency": m.competency_name,
            "mastery_score": m.mastery_score,
            "error_count": m.error_count,
        }
        for m in memories
    ]

    total_days = (end_date - start_date).days + 1
    run = await create_run(db, workspace.id, "plan_generate", DASHSCOPE_CHAT_MODEL)
    usage = {}
    generation_started = utc_now()
    try:
        payload = await gateway.structured_chat(
            (
                "你是学习计划生成器。根据用户的能力差距、面试表现和可用时间，生成每日学习任务。"
                "返回 JSON 对象 tasks，每项包含 competency_name（必须取自 gaps 中的 competency）、"
                "title（任务标题）、description（具体学习内容）、"
                "scheduled_date（ISO 日期）、duration_minutes（分钟）、priority（0-10 整数，越大越优先）。"
                "每天的任务总时长不超过 daily_minutes。优先安排未覆盖和部分覆盖的能力。"
                "每个能力只安排 1-2 个任务，不要重复。确保覆盖所有差距项。"
            ),
            json.dumps(
                {
                    "daily_minutes": daily_minutes,
                    "total_days": total_days,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "gaps": gap_items,
                    "memories": memory_items,
                    "target_role": workspace.target_role or "未设置",
                },
                ensure_ascii=False,
            ),
            usage=usage,
        )
    except AIServiceError:
        await finalize_run(db, run, "failed", error_code="学习计划生成失败")
        raise PlanError("学习计划生成失败，请稍后重试")

    raw_tasks = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(raw_tasks, list) or not raw_tasks:
        await finalize_run(db, run, "failed", error_code="学习计划生成结果为空")
        raise PlanError("学习计划生成结果为空")

    task_date_base = start_date
    used_minutes: dict[date, int] = {}
    valid_task_count = 0
    for index, item in enumerate(raw_tasks):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        description = item.get("description")
        if not isinstance(title, str) or not isinstance(description, str):
            continue
        scheduled_str = item.get("scheduled_date")
        try:
            scheduled_date = (
                date.fromisoformat(scheduled_str) if isinstance(scheduled_str, str)
                else task_date_base + timedelta(days=index % total_days)
            )
        except ValueError:
            scheduled_date = task_date_base + timedelta(days=index % total_days)
        scheduled_date = max(start_date, min(end_date, scheduled_date))
        duration = item.get("duration_minutes", 60)
        if not isinstance(duration, (int, float)) or duration <= 0:
            duration = 60
        priority = item.get("priority", 0)
        if not isinstance(priority, (int, float)):
            priority = 0

        competency_value = item.get("competency_name")
        competency_name = (
            normalize_competency(competency_value)
            if isinstance(competency_value, str)
            else ""
        )
        competency = await db.scalar(
            select(Competency).where(
                Competency.workspace_id == workspace.id,
                Competency.canonical_name == competency_name,
            )
        )
        duration = min(480, max(15, int(duration)))
        remaining = daily_minutes - used_minutes.get(scheduled_date, 0)
        if remaining < 15:
            continue
        duration = min(duration, remaining)
        used_minutes[scheduled_date] = used_minutes.get(scheduled_date, 0) + duration
        db.add(
            StudyTask(
                plan_id=plan.id,
                competency_id=competency.id if competency else None,
                title=str(title)[:200],
                description=str(description)[:2000],
                scheduled_date=scheduled_date,
                duration_minutes=duration,
                priority=min(10, max(0, int(priority))),
            )
        )
        valid_task_count += 1
    if not valid_task_count:
        await finalize_run(db, run, "failed", error_code="学习计划没有可用任务")
        raise PlanError("学习计划没有可用任务")
    await add_step(
        db, run, "generate", status="completed",
        input_summary=f"为 {len(gap_items)} 项能力差距生成任务",
        output_summary=f"生成 {valid_task_count} 个任务",
        started_at=generation_started,
    )
    await finalize_run(
        db, run, "completed",
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )
    await db.commit()
    await db.refresh(plan)
    return await get_plan(db, plan)


async def update_task(
    db: AsyncSession, plan: StudyPlan, task_id: uuid.UUID, status: str | None,
    scheduled_date: date | None, duration_minutes: int | None,
) -> TaskOut:
    task = await db.scalar(
        select(StudyTask).where(StudyTask.id == task_id, StudyTask.plan_id == plan.id)
    )
    if not task:
        raise PlanError("任务不存在")
    if status:
        task.status = status
    if scheduled_date:
        task.scheduled_date = scheduled_date
    if duration_minutes is not None:
        task.duration_minutes = duration_minutes
    await db.commit()
    await db.refresh(task)
    competency_name = None
    if task.competency_id:
        c = await db.scalar(select(Competency).where(Competency.id == task.competency_id))
        competency_name = c.canonical_name if c else None
    return TaskOut(
        id=task.id,
        competency_name=competency_name,
        title=task.title,
        description=task.description,
        scheduled_date=task.scheduled_date,
        duration_minutes=task.duration_minutes,
        priority=task.priority,
        status=task.status,
        created_at=task.created_at,
    )


async def adjust_priorities_after_interview(
    db: AsyncSession, workspace_id: uuid.UUID,
) -> None:
    """Called after interview finalization to bump priority for weak areas."""
    plan = await db.scalar(
        select(StudyPlan).where(
            StudyPlan.workspace_id == workspace_id,
            StudyPlan.status == "active",
        ).order_by(StudyPlan.created_at.desc()).limit(1)
    )
    if not plan:
        return
    memories = list(
        (
            await db.execute(
                select(CompetencyMemory).where(
                    CompetencyMemory.workspace_id == workspace_id,
                )
            )
        ).scalars().all()
    )
    memory_scores = {normalize_competency(m.competency_name): m.mastery_score for m in memories}
    tasks = await _plan_tasks(db, plan)
    for task in tasks:
        if task.status == "completed":
            continue
        if task.competency_id:
            c = await db.scalar(select(Competency).where(Competency.id == task.competency_id))
            if c:
                score = memory_scores.get(c.canonical_name, 50)
                if score < 60:
                    task.priority = min(10, task.priority + 2)
                elif score < 80:
                    task.priority = min(10, task.priority + 1)
    await db.commit()
