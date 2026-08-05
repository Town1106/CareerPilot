import argparse
import asyncio
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient, models

from app.core.config import DASHSCOPE_EMBEDDING_DIMENSIONS, DASHSCOPE_EMBEDDING_MODEL
from app.rag.gateway import embed_texts
from app.rag.store import SPARSE_VECTOR_NAME, sparse_vector

COLLECTION_NAME = "rag_evaluation"


def recall_at(ranked_ids: list[str], relevant_ids: set[str], limit: int) -> float:
    return len(set(ranked_ids[:limit]) & relevant_ids) / len(relevant_ids)


def reciprocal_rank(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    return next(
        (1 / position for position, chunk_id in enumerate(ranked_ids, 1) if chunk_id in relevant_ids),
        0,
    )


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percent) - 1)]


def create_collection(
    chunks: list[dict], vectors: list[list[float]]
) -> tuple[QdrantClient, dict[int, str]]:
    client = QdrantClient(":memory:", force_disable_check_same_thread=True)
    client.create_collection(
        COLLECTION_NAME,
        vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE),
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
    id_by_point = {point_id: chunk["id"] for point_id, chunk in enumerate(chunks, 1)}
    client.upsert(
        COLLECTION_NAME,
        [
            models.PointStruct(
                id=point_id,
                vector={"": vector, SPARSE_VECTOR_NAME: sparse_vector(chunk["text"])},
            )
            for point_id, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True), 1)
        ],
    )
    return client, id_by_point


def search(
    client: QdrantClient, id_by_point: dict[int, str], query: str, vector: list[float], mode: str
) -> list[tuple[str, float]]:
    if mode == "dense":
        points = client.query_points(COLLECTION_NAME, query=vector, limit=10).points
    else:
        points = client.query_points(
            COLLECTION_NAME,
            prefetch=[
                models.Prefetch(query=vector, limit=20),
                models.Prefetch(
                    query=sparse_vector(query), using=SPARSE_VECTOR_NAME, limit=20
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=10,
        ).points
    return [(id_by_point[int(point.id)], point.score) for point in points]


def summarize(details: list[dict]) -> dict:
    count = len(details)
    latencies = [item["latency_ms"] for item in details]
    return {
        "recall_at_5": round(sum(item["recall_at_5"] for item in details) / count, 4),
        "recall_at_10": round(sum(item["recall_at_10"] for item in details) / count, 4),
        "mrr": round(sum(item["reciprocal_rank"] for item in details) / count, 4),
        "retrieval_p50_ms": round(percentile(latencies, 0.5), 2),
        "retrieval_p95_ms": round(percentile(latencies, 0.95), 2),
    }


async def evaluate(dataset_path: Path) -> dict:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    chunks = dataset["chunks"]
    cases = dataset["cases"]
    chunk_ids = [chunk["id"] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("评测集包含重复的 chunk id")
    known_ids = set(chunk_ids)
    for case in cases:
        relevant_ids = set(case["relevant_chunk_ids"])
        if not relevant_ids or not relevant_ids <= known_ids:
            raise ValueError(f"用例 {case['id']} 的相关 chunk 标注无效")

    vectors = await embed_texts([chunk["text"] for chunk in chunks])
    client, id_by_point = create_collection(chunks, vectors)
    embedding_latencies = []
    strategy_details = {"dense": [], "hybrid": []}
    try:
        for case in cases:
            started = time.perf_counter()
            query_vector = (await embed_texts([case["question"]]))[0]
            embedding_latencies.append((time.perf_counter() - started) * 1000)
            relevant_ids = set(case["relevant_chunk_ids"])
            for mode, details in strategy_details.items():
                started = time.perf_counter()
                ranking = search(client, id_by_point, case["question"], query_vector, mode)
                latency_ms = (time.perf_counter() - started) * 1000
                ranked_ids = [chunk_id for chunk_id, _ in ranking]
                details.append(
                    {
                        "id": case["id"],
                        "recall_at_5": recall_at(ranked_ids, relevant_ids, 5),
                        "recall_at_10": recall_at(ranked_ids, relevant_ids, 10),
                        "reciprocal_rank": reciprocal_rank(ranked_ids, relevant_ids),
                        "latency_ms": round(latency_ms, 2),
                        "top_10": [
                            {"chunk_id": chunk_id, "score": round(score, 6)}
                            for chunk_id, score in ranking
                        ],
                    }
                )
    finally:
        client.close()

    strategies = {
        mode: {"metrics": summarize(details), "cases": details}
        for mode, details in strategy_details.items()
    }
    dense_metrics = strategies["dense"]["metrics"]
    hybrid_metrics = strategies["hybrid"]["metrics"]
    return {
        "dataset": dataset["name"],
        "created_at": datetime.now(UTC).isoformat(),
        "config": {
            "embedding_model": DASHSCOPE_EMBEDDING_MODEL,
            "embedding_dimensions": DASHSCOPE_EMBEDDING_DIMENSIONS,
            "sparse": "lexical terms and Chinese bigrams with Qdrant IDF",
            "fusion": "RRF",
            "case_count": len(cases),
            "chunk_count": len(chunks),
        },
        "embedding_latency_ms": {
            "p50": round(percentile(embedding_latencies, 0.5), 2),
            "p95": round(percentile(embedding_latencies, 0.95), 2),
        },
        "delta_hybrid_minus_dense": {
            key: round(hybrid_metrics[key] - dense_metrics[key], 4)
            for key in ("recall_at_5", "recall_at_10", "mrr")
        },
        "strategies": strategies,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate CareerPilot dense retrieval")
    parser.add_argument("--dataset", type=Path, default=Path("evals/rag_dataset.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("evals/results/dense-hybrid-comparison.json")
    )
    args = parser.parse_args()
    report = await evaluate(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                mode: result["metrics"]
                for mode, result in report["strategies"].items()
            }
            | {"delta_hybrid_minus_dense": report["delta_hybrid_minus_dense"]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
