import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.database import get_db
from app.models import User, Workspace
from app.schemas import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


async def owned_workspace(workspace_id: uuid.UUID, user: User, db: AsyncSession) -> Workspace:
    workspace = await db.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user.id)
    )
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return workspace


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[Workspace]:
    return list(
        (
            await db.scalars(
                select(Workspace)
                .where(Workspace.user_id == user.id)
                .order_by(Workspace.created_at)
            )
        ).all()
    )


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    workspace = Workspace(user_id=user.id, **payload.model_dump())
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    workspace = await owned_workspace(workspace_id, user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    workspace = await owned_workspace(workspace_id, user, db)
    await db.delete(workspace)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

