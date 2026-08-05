import hashlib
import math
import re
import uuid
from collections import Counter
from functools import lru_cache
from itertools import pairwise
from pathlib import Path

from qdrant_client import QdrantClient, models

from app.core.config import DASHSCOPE_EMBEDDING_DIMENSIONS

COLLECTION_NAME = "careerpilot_chunks_v2"
LEGACY_COLLECTION_NAME = "careerpilot_chunks"
SPARSE_VECTOR_NAME = "sparse"
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
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )


def sparse_vector(text: str) -> models.SparseVector:
    normalized = text.casefold()
    tokens = re.findall(r"[a-z0-9][a-z0-9.+#_-]*", normalized)
    for sequence in re.findall(r"[\u3400-\u9fff]+", normalized):
        tokens.extend(sequence if len(sequence) == 1 else pairwise(sequence))
    counts = Counter("".join(token) if isinstance(token, tuple) else token for token in tokens)
    weights: dict[int, float] = {}
    for token, count in counts.items():
        index = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "big")
        weights[index] = weights.get(index, 0) + 1 + math.log(count)
    indices = sorted(weights)
    return models.SparseVector(indices=indices, values=[weights[index] for index in indices])


def upsert_chunks(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_ids: list[uuid.UUID],
    texts: list[str],
    vectors: list[list[float]],
) -> None:
    try:
        ensure_collection()
        get_client().upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=chunk_id,
                    vector={"": vector, SPARSE_VECTOR_NAME: sparse_vector(text)},
                    payload={
                        "workspace_id": str(workspace_id),
                        "document_id": str(document_id),
                    },
                )
                for chunk_id, text, vector in zip(chunk_ids, texts, vectors, strict=True)
            ],
            wait=True,
        )
    except Exception as error:
        raise VectorStoreError(f"Qdrant 写入失败：{error}") from error


def search(
    workspace_id: uuid.UUID,
    vector: list[float],
    query: str,
    limit: int,
    mode: str,
) -> list[tuple[uuid.UUID, float]]:
    try:
        client = get_client()
        if not client.collection_exists(COLLECTION_NAME):
            return []
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="workspace_id", match=models.MatchValue(value=str(workspace_id))
                )
            ]
        )
        if mode == "dense":
            points = client.query_points(
                collection_name=COLLECTION_NAME,
                query=vector,
                query_filter=query_filter,
                with_payload=False,
                limit=limit,
            ).points
        elif mode == "hybrid":
            candidate_limit = max(20, limit * 4)
            points = client.query_points(
                collection_name=COLLECTION_NAME,
                prefetch=[
                    models.Prefetch(
                        query=vector, filter=query_filter, limit=candidate_limit
                    ),
                    models.Prefetch(
                        query=sparse_vector(query),
                        using=SPARSE_VECTOR_NAME,
                        filter=query_filter,
                        limit=candidate_limit,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                with_payload=False,
                limit=limit,
            ).points
        else:
            raise ValueError(f"不支持的检索模式：{mode}")
        return [(uuid.UUID(str(point.id)), point.score) for point in points]
    except Exception as error:
        raise VectorStoreError(f"Qdrant 检索失败：{error}") from error


def _delete_by(key: str, value: uuid.UUID) -> None:
    try:
        client = get_client()
        for collection_name in (COLLECTION_NAME, LEGACY_COLLECTION_NAME):
            if client.collection_exists(collection_name):
                client.delete(
                    collection_name=collection_name,
                    points_selector=models.Filter(
                        must=[
                            models.FieldCondition(key=key, match=models.MatchValue(value=str(value)))
                        ]
                    ),
                    wait=True,
                )
    except Exception as error:
        raise VectorStoreError(f"Qdrant 删除失败：{error}") from error


def delete_document(document_id: uuid.UUID) -> None:
    _delete_by("document_id", document_id)


def delete_workspace(workspace_id: uuid.UUID) -> None:
    _delete_by("workspace_id", workspace_id)
