import asyncio
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DASHSCOPE_CHAT_MODEL, RAG_RETRIEVAL_MODE, RAG_TOP_K
from app.core.database import utc_now
from app.documents.models import Document, DocumentChunk, DocumentVersion
from app.rag import gateway, store
from app.rag.gateway import AIServiceError
from app.rag.schemas import AnswerOut, CitationOut
from app.rag.store import VectorStoreError
from app.traces.service import add_step, create_run, finalize_run


async def retrieve_chunks(
    db: AsyncSession, workspace_id: uuid.UUID, question: str, limit: int = RAG_TOP_K
) -> list[tuple[DocumentChunk, Document, DocumentVersion, float]]:
    if not await db.scalar(
        select(Document.id)
        .join(DocumentVersion, DocumentVersion.id == Document.active_version_id)
        .where(
            Document.workspace_id == workspace_id, DocumentVersion.status == "indexed"
        )
    ):
        return []
    query_vector = (await gateway.embed_texts([question]))[0]
    hits = await asyncio.to_thread(
        store.search, workspace_id, query_vector, question, limit, RAG_RETRIEVAL_MODE
    )
    if not hits:
        return []

    score_by_id = dict(hits)
    rows = (
        await db.execute(
            select(DocumentChunk, Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.version_id)
            .join(Document, Document.active_version_id == DocumentVersion.id)
            .where(
                Document.workspace_id == workspace_id,
                DocumentVersion.status == "indexed",
                DocumentChunk.id.in_(score_by_id),
            )
        )
    ).all()
    row_by_id = {
        chunk.id: (chunk, document, version) for chunk, document, version in rows
    }
    return [
        (*row_by_id[chunk_id], score)
        for chunk_id, score in hits
        if chunk_id in row_by_id
    ]


async def index_document(
    db: AsyncSession, document: Document, version: DocumentVersion
) -> DocumentVersion:
    chunks = list(
        (
            await db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.version_id == version.id)
                .order_by(DocumentChunk.position)
            )
        ).all()
    )
    version.status = "indexing"
    version.index_error = None
    version.indexed_at = None
    await db.commit()
    try:
        await asyncio.to_thread(store.delete_document, document.id)
        vectors = await gateway.embed_texts([chunk.content for chunk in chunks])
        await asyncio.to_thread(
            store.upsert_chunks,
            document.workspace_id,
            document.id,
            [chunk.id for chunk in chunks],
            [chunk.content for chunk in chunks],
            vectors,
        )
    except (AIServiceError, VectorStoreError) as error:
        version.status = "failed"
        version.index_error = str(error)[:500]
    else:
        version.status = "indexed"
        version.indexed_at = utc_now()
    await db.commit()
    await db.refresh(version)
    return version


async def answer_question(
    db: AsyncSession, workspace_id: uuid.UUID, question: str
) -> AnswerOut:
    run = await create_run(db, workspace_id, "rag_qa", DASHSCOPE_CHAT_MODEL)
    try:
        hits = await retrieve_chunks(db, workspace_id, question)
        chunk_records = [
            {
                "chunk_id": str(chunk.id),
                "document": version.original_name,
                "score": round(score, 4),
                "content": chunk.content[:200],
            }
            for chunk, _, version, score in hits
        ]
        await add_step(
            db, run, "retrieve", status="completed",
            input_summary=question[:500],
            retrieved_chunks=chunk_records,
            latency_ms=0,
        )
        if not hits:
            await finalize_run(db, run, "completed")
            await db.commit()
            return AnswerOut(answer="当前知识库中没有可用于回答该问题的已索引证据。", citations=[])

        evidence: list[tuple[str, DocumentChunk, Document, DocumentVersion, float]] = []
        for chunk, document, version, score in hits:
            label = f"S{len(evidence) + 1}"
            evidence.append((label, chunk, document, version, score))

        sources = [
            f"[{label}] 文件：{version.original_name}；"
            f"页码：{chunk.page_number or '无'}；内容：{chunk.content}"
            for label, chunk, _, version, _ in evidence
        ]
        usage = {}
        answer = await gateway.answer_with_context(question, sources, usage=usage)
        await add_step(
            db, run, "generate", status="completed",
            input_summary=f"基于 {len(sources)} 条证据生成回答",
            output_summary=answer[:500],
            latency_ms=0,
        )
        await finalize_run(
            db, run, "completed",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        await db.commit()
        cited_labels = set(re.findall(r"\[S(\d+)\]", answer))
        citations = [
            CitationOut(
                label=label,
                chunk_id=chunk.id,
                document_id=document.id,
                original_name=version.original_name,
                page_number=chunk.page_number,
                position=chunk.position,
                content=chunk.content,
                score=score,
            )
            for label, chunk, document, version, score in evidence
            if label.removeprefix("S") in cited_labels
        ]
        return AnswerOut(answer=answer, citations=citations)
    except (AIServiceError, VectorStoreError) as error:
        await finalize_run(db, run, "failed", error_code=str(error)[:500])
        await db.commit()
        raise