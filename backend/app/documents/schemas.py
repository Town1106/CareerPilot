import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.documents.models import Document, DocumentVersion


class DocumentOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    original_name: str
    category: str
    current_version: int
    media_type: str
    size_bytes: int
    sha256: str
    status: str
    index_error: str | None
    indexed_at: datetime | None
    chunk_count: int
    created_at: datetime


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: str
    index_error: str | None
    indexed_at: datetime | None
    chunk_count: int
    created_at: datetime


def document_out(document: Document, version: DocumentVersion) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        workspace_id=document.workspace_id,
        original_name=version.original_name,
        category=document.category,
        current_version=version.version,
        media_type=version.media_type,
        size_bytes=version.size_bytes,
        sha256=version.sha256,
        status=version.status,
        index_error=version.index_error,
        indexed_at=version.indexed_at,
        chunk_count=version.chunk_count,
        created_at=document.created_at,
    )
