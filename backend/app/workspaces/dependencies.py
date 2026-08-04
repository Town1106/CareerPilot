import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.workspaces.models import Workspace


async def owned_workspace(workspace_id: uuid.UUID, user: User, db: AsyncSession) -> Workspace:
    workspace = await db.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user.id)
    )
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return workspace
