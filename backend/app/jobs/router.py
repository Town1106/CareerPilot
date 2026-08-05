import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.jobs.models import JobDescription
from app.jobs.schemas import (
    AnalysisOut,
    CompareOut,
    CompareRequest,
    GapOut,
    JobCreate,
    JobOut,
)
from app.jobs.service import analyze_job, compare_jobs, competency_gap, get_analysis
from app.rag.gateway import AIServiceError
from app.rag.store import VectorStoreError
from app.workspaces.dependencies import owned_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["jobs"])


async def owned_job(db: AsyncSession, workspace_id: uuid.UUID, job_id: uuid.UUID) -> JobDescription:
    job = await db.scalar(
        select(JobDescription).where(
            JobDescription.id == job_id, JobDescription.workspace_id == workspace_id
        )
    )
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job description not found")
    return job


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    workspace_id: uuid.UUID,
    payload: JobCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> JobDescription:
    await owned_workspace(workspace_id, user, db)
    job = JobDescription(workspace_id=workspace_id, **payload.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobDescription]:
    await owned_workspace(workspace_id, user, db)
    return list(
        (
            await db.scalars(
                select(JobDescription)
                .where(JobDescription.workspace_id == workspace_id)
                .order_by(JobDescription.created_at.desc())
            )
        ).all()
    )


@router.post("/jobs/compare", response_model=CompareOut)
async def compare(
    workspace_id: uuid.UUID,
    payload: CompareRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> CompareOut:
    await owned_workspace(workspace_id, user, db)
    if len(payload.job_ids) != len(set(payload.job_ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "岗位不能重复")
    jobs = list(
        (
            await db.scalars(
                select(JobDescription).where(
                    JobDescription.workspace_id == workspace_id,
                    JobDescription.id.in_(payload.job_ids),
                )
            )
        ).all()
    )
    if len(jobs) != len(payload.job_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job description not found")
    if any(job.status != "analyzed" for job in jobs):
        raise HTTPException(status.HTTP_409_CONFLICT, "只能比较已完成分析的岗位")
    jobs_by_id = {job.id: job for job in jobs}
    return await compare_jobs(db, [jobs_by_id[job_id] for job_id in payload.job_ids])


@router.get("/competency-gap", response_model=list[GapOut])
async def get_competency_gap(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GapOut]:
    await owned_workspace(workspace_id, user, db)
    return await competency_gap(db, workspace_id)


@router.post("/jobs/{job_id}/analyze", response_model=AnalysisOut)
async def analyze(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    await owned_workspace(workspace_id, user, db)
    job = await owned_job(db, workspace_id, job_id)
    try:
        return await analyze_job(db, job)
    except (AIServiceError, VectorStoreError) as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from None


@router.get("/jobs/{job_id}/requirements", response_model=AnalysisOut)
async def requirements(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    await owned_workspace(workspace_id, user, db)
    job = await owned_job(db, workspace_id, job_id)
    return await get_analysis(db, job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await owned_workspace(workspace_id, user, db)
    job = await owned_job(db, workspace_id, job_id)
    await db.delete(job)
    await db.commit()
