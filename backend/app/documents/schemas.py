import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    original_name: str
    media_type: str
    category: str
    size_bytes: int
    status: str
    index_error: str | None
    indexed_at: datetime | None
    chunk_count: int
    created_at: datetime
