import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.documents.models import Document
from app.documents.schemas import DocumentOut
from app.rag.gateway import AIServiceError
from app.rag.schemas import AnswerOut, QuestionRequest
from app.rag.service import answer_question, index_document
from app.rag.store import VectorStoreError
from app.workspaces.dependencies import owned_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["rag"])


@router.post("/documents/{document_id}/index", response_model=DocumentOut)
async def reindex_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    await owned_workspace(workspace_id, user, db)
    document = await db.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return await index_document(db, document)


@router.post("/rag/ask", response_model=AnswerOut)
async def ask(
    workspace_id: uuid.UUID,
    payload: QuestionRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> AnswerOut:
    await owned_workspace(workspace_id, user, db)
    try:
        return await answer_question(db, workspace_id, payload.question.strip())
    except (AIServiceError, VectorStoreError) as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from None
