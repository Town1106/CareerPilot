import uuid
from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient, models

from app.core.config import DASHSCOPE_EMBEDDING_DIMENSIONS

COLLECTION_NAME = "careerpilot_chunks"
QDRANT_PATH = Path(__file__).resolve().parents[2] / "data" / "qdrant"


class VectorStoreError(RuntimeError):
    pass


@lru_cache
def get_client() -> QdrantClient:
    # ponytail: local mode is single-process; switch to Qdrant Server before multiple API workers.
    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(QDRANT_PATH), force_disable_check_same_thread=True)


def close_client() -> None:
    if hasattr(get_client, "cache_info") and get_client.cache_info().currsize:
        get_client().close()
        get_client.cache_clear()


def ensure_collection() -> None:
    client = get_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=DASHSCOPE_EMBEDDING_DIMENSIONS,
                distance=models.Distance.COSINE,
            ),
        )


def upsert_chunks(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_ids: list[uuid.UUID],
    vectors: list[list[float]],
) -> None:
    try:
        ensure_collection()
        get_client().upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload={
                        "workspace_id": str(workspace_id),
                        "document_id": str(document_id),
                    },
                )
                for chunk_id, vector in zip(chunk_ids, vectors, strict=True)
            ],
            wait=True,
        )
    except Exception as error:
        raise VectorStoreError(f"Qdrant 写入失败：{error}") from error


def search(
    workspace_id: uuid.UUID, vector: list[float], limit: int
) -> list[tuple[uuid.UUID, float]]:
    try:
        client = get_client()
        if not client.collection_exists(COLLECTION_NAME):
            return []
        points = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="workspace_id", match=models.MatchValue(value=str(workspace_id))
                    )
                ]
            ),
            with_payload=False,
            limit=limit,
        ).points
        return [(uuid.UUID(str(point.id)), point.score) for point in points]
    except Exception as error:
        raise VectorStoreError(f"Qdrant 检索失败：{error}") from error


def _delete_by(key: str, value: uuid.UUID) -> None:
    try:
        client = get_client()
        if not client.collection_exists(COLLECTION_NAME):
            return
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.Filter(
                must=[models.FieldCondition(key=key, match=models.MatchValue(value=str(value)))]
            ),
            wait=True,
        )
    except Exception as error:
        raise VectorStoreError(f"Qdrant 删除失败：{error}") from error


def delete_document(document_id: uuid.UUID) -> None:
    _delete_by("document_id", document_id)


def delete_workspace(workspace_id: uuid.UUID) -> None:
    _delete_by("workspace_id", workspace_id)
