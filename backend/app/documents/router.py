import asyncio
import hashlib
import logging
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pypdf.errors import PyPdfError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.config import DASHSCOPE_API_KEY
from app.core.database import get_db
from app.documents import files
from app.documents.models import Document, DocumentChunk, DocumentVersion
from app.documents.schemas import DocumentOut, DocumentVersionOut, document_out
from app.rag import store
from app.rag.service import index_document
from app.rag.store import VectorStoreError
from app.workspaces.dependencies import owned_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/documents", tags=["documents"])
CATEGORIES = {"resume", "project", "other"}
logger = logging.getLogger(__name__)


async def read_upload(
    file: UploadFile,
) -> tuple[str, str, str, bytes, str, list[tuple[int | None, str]]]:
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()
    if not original_name or len(original_name) > 255 or extension not in files.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "仅支持 PDF、DOCX、TXT 和 Markdown"
        )
    content = await file.read(files.MAX_FILE_BYTES + 1)
    media_type = file.content_type or "application/octet-stream"
    await file.close()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "文件不能为空")
    if len(content) > files.MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "文件不能超过 10 MB")
    try:
        chunks = files.make_chunks(files.parse_document(extension, content))
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
    return original_name, extension, media_type, content, hashlib.sha256(content).hexdigest(), chunks


async def reject_duplicate(
    db: AsyncSession, workspace_id: uuid.UUID, digest: str
) -> None:
    # ponytail: application check fits local single-process uploads; add a DB unique key if concurrent uploads arrive.
    duplicate = (
        await db.execute(
            select(Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .where(Document.workspace_id == workspace_id, DocumentVersion.sha256 == digest)
            .limit(1)
        )
    ).first()
    if duplicate:
        document, version = duplicate
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"相同文件已存在：{version.original_name}（版本 {version.version}，文档 {document.id}）",
        )


async def persist_version(
    db: AsyncSession,
    document: Document,
    version_number: int,
    original_name: str,
    extension: str,
    media_type: str,
    content: bytes,
    digest: str,
    chunks: list[tuple[int | None, str]],
) -> DocumentVersion:
    stored_name = files.save_file(extension, content)
    version = DocumentVersion(
        document_id=document.id,
        version=version_number,
        original_name=original_name,
        stored_name=stored_name,
        media_type=media_type,
        size_bytes=len(content),
        sha256=digest,
        status="parsed",
        chunk_count=len(chunks),
    )
    try:
        db.add(version)
        await db.flush()
        db.add_all(
            DocumentChunk(
                version_id=version.id,
                position=index,
                page_number=page,
                content=text,
            )
            for index, (page, text) in enumerate(chunks)
        )
        document.original_name = original_name
        document.active_version_id = version.id
        await db.commit()
    except Exception:
        await db.rollback()
        files.delete_file(stored_name)
        raise
    await db.refresh(document)
    await db.refresh(version)
    return version


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentOut]:
    await owned_workspace(workspace_id, user, db)
    rows = (
        await db.execute(
            select(Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.id == Document.active_version_id)
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at.desc())
        )
    ).all()
    return [document_out(document, version) for document, version in rows]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile = File(),
    category: str = Form("other"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    await owned_workspace(workspace_id, user, db)
    if category not in CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "无效的文档类型")
    original_name, extension, media_type, content, digest, chunks = await read_upload(file)
    await reject_duplicate(db, workspace_id, digest)
    document = Document(
        workspace_id=workspace_id,
        original_name=original_name,
        category=category,
    )
    db.add(document)
    await db.flush()
    version = await persist_version(
        db, document, 1, original_name, extension, media_type, content, digest, chunks
    )
    if DASHSCOPE_API_KEY:
        version = await index_document(db, document, version)
    return document_out(document, version)


@router.post("/{document_id}/versions", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_version(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    file: UploadFile = File(),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    await owned_workspace(workspace_id, user, db)
    document = await db.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    original_name, extension, media_type, content, digest, chunks = await read_upload(file)
    await reject_duplicate(db, workspace_id, digest)
    version_number = 1 + (
        await db.scalar(
            select(func.max(DocumentVersion.version)).where(
                DocumentVersion.document_id == document.id
            )
        )
        or 0
    )
    version = await persist_version(
        db,
        document,
        version_number,
        original_name,
        extension,
        media_type,
        content,
        digest,
        chunks,
    )
    if DASHSCOPE_API_KEY:
        version = await index_document(db, document, version)
    else:
        try:
            await asyncio.to_thread(store.delete_document, document.id)
        except VectorStoreError as error:
            logger.warning("Vector cleanup failed for document %s: %s", document.id, error)
    return document_out(document, version)


@router.get("/{document_id}/versions", response_model=list[DocumentVersionOut])
async def list_versions(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentVersion]:
    await owned_workspace(workspace_id, user, db)
    if not await db.scalar(
        select(Document.id).where(Document.id == document_id, Document.workspace_id == workspace_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return list(
        (
            await db.scalars(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version.desc())
            )
        ).all()
    )


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
    stored_names = list(
        await db.scalars(
            select(DocumentVersion.stored_name).where(DocumentVersion.document_id == document.id)
        )
    )
    document.active_version_id = None
    await db.flush()
    await db.delete(document)
    await db.commit()
    for stored_name in stored_names:
        files.delete_file(stored_name)
    try:
        await asyncio.to_thread(store.delete_document, document_id)
    except VectorStoreError as error:
        logger.warning("Vector cleanup failed for document %s: %s", document_id, error)
