import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.documents import files
from app.documents.models import Document, DocumentVersion
from app.rag import store
from app.rag.store import VectorStoreError
from app.workspaces.dependencies import owned_workspace
from app.workspaces.models import Workspace
from app.workspaces.schemas import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[Workspace]:
    return list(
        (
            await db.scalars(
                select(Workspace).where(Workspace.user_id == user.id).order_by(Workspace.created_at)
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
    stored_names = list(
        (
            await db.scalars(
                select(DocumentVersion.stored_name)
                .join(Document, Document.id == DocumentVersion.document_id)
                .where(Document.workspace_id == workspace.id)
            )
        ).all()
    )
    await db.delete(workspace)
    await db.commit()
    for stored_name in stored_names:
        files.delete_file(stored_name)
    try:
        await asyncio.to_thread(store.delete_workspace, workspace_id)
    except VectorStoreError as error:
        logger.warning("Vector cleanup failed for workspace %s: %s", workspace_id, error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
