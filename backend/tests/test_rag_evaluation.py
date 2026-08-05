import uuid

from qdrant_client import QdrantClient

from app.rag import store
from app.rag.evaluate import percentile, recall_at, reciprocal_rank
from app.rag.store import sparse_vector


def test_retrieval_metrics() -> None:
    ranked_ids = ["exact", "partial", "other"]
    assert recall_at(ranked_ids, {"exact", "other"}, 2) == 0.5
    assert reciprocal_rank(ranked_ids, {"partial"}) == 0.5
    assert percentile([10, 30, 20, 40], 0.5) == 20
    assert percentile([10, 30, 20, 40], 0.95) == 40


def test_sparse_vector_matches_english_terms_and_chinese_bigrams() -> None:
    left = sparse_vector("FastAPI 使用向量数据库")
    right = sparse_vector("fastapi 与向量检索")

    assert set(left.indices) & set(right.indices)
    assert left == sparse_vector("FastAPI 使用向量数据库")


def test_hybrid_search_keeps_workspace_isolation(monkeypatch) -> None:
    qdrant = QdrantClient(":memory:", force_disable_check_same_thread=True)
    monkeypatch.setattr(store, "get_client", lambda: qdrant)
    workspace_id = uuid.uuid4()
    expected_chunk_id = uuid.uuid4()
    vector = [1.0] + [0.0] * 1023
    store.upsert_chunks(
        workspace_id,
        uuid.uuid4(),
        [expected_chunk_id],
        ["FastAPI 使用 Qdrant 向量数据库"],
        [vector],
    )
    store.upsert_chunks(
        uuid.uuid4(),
        uuid.uuid4(),
        [uuid.uuid4()],
        ["FastAPI 使用 Qdrant 向量数据库"],
        [vector],
    )

    hits = store.search(workspace_id, vector, "FastAPI 向量检索", 5, "hybrid")

    assert [chunk_id for chunk_id, _ in hits] == [expected_chunk_id]
    qdrant.close()
