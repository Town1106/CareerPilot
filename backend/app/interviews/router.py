import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.interviews.models import CompetencyMemory, InterviewSession
from app.interviews.schemas import (
    AnswerCreate,
    InterviewCreate,
    InterviewOut,
    MemoryOut,
    MemoryPatch,
)
from app.interviews.service import (
    InterviewStateError,
    finalize_interview,
    get_interview,
    start_interview,
    submit_answer,
)
from app.jobs.models import JobDescription
from app.rag.gateway import AIServiceError
from app.workspaces.dependencies import owned_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["interviews"])


async def owned_session(
    db: AsyncSession, workspace_id: uuid.UUID, session_id: uuid.UUID
) -> InterviewSession:
    session = await db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.workspace_id == workspace_id,
        )
    )
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return session


async def owned_memory(
    db: AsyncSession, workspace_id: uuid.UUID, memory_id: uuid.UUID
) -> CompetencyMemory:
    memory = await db.scalar(
        select(CompetencyMemory).where(
            CompetencyMemory.id == memory_id,
            CompetencyMemory.workspace_id == workspace_id,
        )
    )
    if not memory:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    return memory


def interview_error(error: Exception) -> HTTPException:
    code = status.HTTP_409_CONFLICT if isinstance(error, InterviewStateError) else 502
    return HTTPException(code, str(error))


@router.post("/interviews", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
async def create_interview(
    workspace_id: uuid.UUID,
    payload: InterviewCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    await owned_workspace(workspace_id, user, db)
    job = await db.scalar(
        select(JobDescription).where(
            JobDescription.id == payload.job_description_id,
            JobDescription.workspace_id == workspace_id,
        )
    )
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job description not found")
    if job.status != "analyzed":
        raise HTTPException(status.HTTP_409_CONFLICT, "请先完成目标岗位分析")
    session = InterviewSession(workspace_id=workspace_id, **payload.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return await get_interview(db, session)


@router.get("/interviews", response_model=list[InterviewOut])
async def list_interviews(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewOut]:
    await owned_workspace(workspace_id, user, db)
    sessions = list(
        (
            await db.scalars(
                select(InterviewSession)
                .where(InterviewSession.workspace_id == workspace_id)
                .order_by(InterviewSession.created_at.desc())
            )
        ).all()
    )
    return [await get_interview(db, session) for session in sessions]


@router.get("/interviews/{session_id}", response_model=InterviewOut)
async def interview_detail(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    await owned_workspace(workspace_id, user, db)
    return await get_interview(db, await owned_session(db, workspace_id, session_id))


@router.post("/interviews/{session_id}/start", response_model=InterviewOut)
async def start(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    await owned_workspace(workspace_id, user, db)
    session = await owned_session(db, workspace_id, session_id)
    try:
        return await start_interview(db, session)
    except (InterviewStateError, AIServiceError) as error:
        raise interview_error(error) from None


@router.post("/interviews/{session_id}/answers", response_model=InterviewOut)
async def answer(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: AnswerCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    await owned_workspace(workspace_id, user, db)
    session = await owned_session(db, workspace_id, session_id)
    try:
        return await submit_answer(db, session, payload.answer)
    except (InterviewStateError, AIServiceError) as error:
        await db.rollback()
        raise interview_error(error) from None


@router.post("/interviews/{session_id}/finish", response_model=InterviewOut)
async def finish(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    await owned_workspace(workspace_id, user, db)
    session = await owned_session(db, workspace_id, session_id)
    if session.status == "completed":
        return await get_interview(db, session)
    if session.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "该面试当前不能结束")
    try:
        return await finalize_interview(db, session)
    except (InterviewStateError, AIServiceError) as error:
        await db.rollback()
        raise interview_error(error) from None


@router.get("/interviews/{session_id}/report", response_model=InterviewOut)
async def report(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    await owned_workspace(workspace_id, user, db)
    session = await owned_session(db, workspace_id, session_id)
    if session.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "面试尚未完成")
    return await get_interview(db, session)


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CompetencyMemory]:
    await owned_workspace(workspace_id, user, db)
    return list(
        (
            await db.scalars(
                select(CompetencyMemory)
                .where(CompetencyMemory.workspace_id == workspace_id)
                .order_by(CompetencyMemory.mastery_score, CompetencyMemory.competency_name)
            )
        ).all()
    )


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
async def update_memory(
    workspace_id: uuid.UUID,
    memory_id: uuid.UUID,
    payload: MemoryPatch,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> CompetencyMemory:
    await owned_workspace(workspace_id, user, db)
    memory = await owned_memory(db, workspace_id, memory_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(memory, field, value)
    await db.commit()
    await db.refresh(memory)
    return memory


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    workspace_id: uuid.UUID,
    memory_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await owned_workspace(workspace_id, user, db)
    await db.delete(await owned_memory(db, workspace_id, memory_id))
    await db.commit()
