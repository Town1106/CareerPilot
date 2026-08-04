import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pypdf.errors import PyPdfError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import document_files
from app.auth import current_user
from app.database import get_db
from app.models import Document, DocumentChunk, User
from app.schemas import DocumentOut
from app.workspaces import owned_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/documents", tags=["documents"])
CATEGORIES = {"resume", "project", "other"}


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    await owned_workspace(workspace_id, user, db)
    return list(
        (
            await db.scalars(
                select(Document)
                .where(Document.workspace_id == workspace_id)
                .order_by(Document.created_at.desc())
            )
        ).all()
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile = File(),
    category: str = Form("other"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    await owned_workspace(workspace_id, user, db)
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()
    if (
        not original_name
        or len(original_name) > 255
        or extension not in document_files.ALLOWED_EXTENSIONS
    ):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "仅支持 PDF、DOCX、TXT 和 Markdown"
        )
    if category not in CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "无效的文档类型")

    content = await file.read(document_files.MAX_FILE_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "文件不能为空")
    if len(content) > document_files.MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "文件不能超过 10 MB")
    try:
        chunks = document_files.make_chunks(document_files.parse_document(extension, content))
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        zipfile.BadZipFile,
        ElementTree.ParseError,
        PyPdfError,
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "无法解析文档") from None
    if not chunks:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "文档中没有可提取的文本")

    stored_name = document_files.save_file(extension, content)
    document = Document(
        workspace_id=workspace_id,
        original_name=original_name,
        stored_name=stored_name,
        media_type=file.content_type or "application/octet-stream",
        category=category,
        size_bytes=len(content),
        status="ready",
        chunk_count=len(chunks),
    )
    try:
        db.add(document)
        await db.flush()
        db.add_all(
            DocumentChunk(
                document_id=document.id,
                position=index,
                page_number=page,
                content=text,
            )
            for index, (page, text) in enumerate(chunks)
        )
        await db.commit()
    except Exception:
        await db.rollback()
        document_files.delete_file(stored_name)
        raise
    await db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await owned_workspace(workspace_id, user, db)
    document = await db.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    stored_name = document.stored_name
    await db.delete(document)
    await db.commit()
    document_files.delete_file(stored_name)
