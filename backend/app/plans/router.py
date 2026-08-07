import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.plans.models import StudyPlan
from app.plans.schemas import PlanGenerate, PlanOut, TaskOut, TaskPatch
from app.plans.service import PlanError, generate_plan, get_plan, update_task
from app.workspaces.dependencies import owned_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["plans"])


async def owned_plan(
    db: AsyncSession, workspace_id: uuid.UUID, plan_id: uuid.UUID
) -> StudyPlan:
    plan = await db.scalar(
        select(StudyPlan).where(
            StudyPlan.id == plan_id,
            StudyPlan.workspace_id == workspace_id,
        )
    )
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "学习计划不存在")
    return plan


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    workspace_id: uuid.UUID,
    payload: PlanGenerate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanOut:
    workspace = await owned_workspace(workspace_id, user, db)
    try:
        return await generate_plan(
            db, workspace, payload.start_date, payload.end_date, payload.daily_minutes
        )
    except PlanError as error:
        raise HTTPException(502, str(error)) from None


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlanOut]:
    await owned_workspace(workspace_id, user, db)
    plans = list(
        (
            await db.scalars(
                select(StudyPlan)
                .where(StudyPlan.workspace_id == workspace_id)
                .order_by(StudyPlan.created_at.desc())
            )
        ).all()
    )
    return [await get_plan(db, plan) for plan in plans]


@router.get("/plans/{plan_id}", response_model=PlanOut)
async def plan_detail(
    workspace_id: uuid.UUID,
    plan_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanOut:
    await owned_workspace(workspace_id, user, db)
    return await get_plan(db, await owned_plan(db, workspace_id, plan_id))


@router.patch("/plans/{plan_id}/tasks/{task_id}", response_model=TaskOut)
async def patch_task(
    workspace_id: uuid.UUID,
    plan_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TaskPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    await owned_workspace(workspace_id, user, db)
    plan = await owned_plan(db, workspace_id, plan_id)
    try:
        return await update_task(
            db, plan, task_id, payload.status, payload.scheduled_date, payload.duration_minutes
        )
    except PlanError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from None


@router.post("/plans/{plan_id}/archive", response_model=PlanOut)
async def archive_plan(
    workspace_id: uuid.UUID,
    plan_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanOut:
    await owned_workspace(workspace_id, user, db)
    plan = await owned_plan(db, workspace_id, plan_id)
    if plan.status == "archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "计划已归档")
    plan.status = "archived"
    await db.commit()
    return await get_plan(db, plan)
