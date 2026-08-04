import asyncio
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RAG_TOP_K
from app.core.database import utc_now
from app.documents.models import Document, DocumentChunk
from app.rag import gateway, store
from app.rag.gateway import AIServiceError
from app.rag.schemas import AnswerOut, CitationOut
from app.rag.store import VectorStoreError


async def index_document(db: AsyncSession, document: Document) -> Document:
    chunks = list(
        (
            await db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.position)
            )
        ).all()
    )
    document.status = "indexing"
    document.index_error = None
    document.indexed_at = None
    await db.commit()
    try:
        vectors = await gateway.embed_texts([chunk.content for chunk in chunks])
        await asyncio.to_thread(
            store.upsert_chunks,
            document.workspace_id,
            document.id,
            [chunk.id for chunk in chunks],
            vectors,
        )
    except (AIServiceError, VectorStoreError) as error:
        document.status = "failed"
        document.index_error = str(error)[:500]
    else:
        document.status = "indexed"
        document.indexed_at = utc_now()
    await db.commit()
    await db.refresh(document)
    return document


async def answer_question(db: AsyncSession, workspace_id: uuid.UUID, question: str) -> AnswerOut:
    if not await db.scalar(
        select(Document.id).where(
            Document.workspace_id == workspace_id, Document.status == "indexed"
        )
    ):
        return AnswerOut(answer="当前知识库中没有可用于回答该问题的已索引证据。", citations=[])
    query_vector = (await gateway.embed_texts([question]))[0]
    hits = await asyncio.to_thread(store.search, workspace_id, query_vector, RAG_TOP_K)
    if not hits:
        return AnswerOut(answer="当前知识库中没有可用于回答该问题的已索引证据。", citations=[])

    score_by_id = dict(hits)
    rows = (
        await db.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.workspace_id == workspace_id,
                Document.status == "indexed",
                DocumentChunk.id.in_(score_by_id),
            )
        )
    ).all()
    row_by_id = {chunk.id: (chunk, document) for chunk, document in rows}
    evidence: list[tuple[str, DocumentChunk, Document, float]] = []
    for chunk_id, score in hits:
        if chunk_id in row_by_id:
            chunk, document = row_by_id[chunk_id]
            label = f"S{len(evidence) + 1}"
            evidence.append((label, chunk, document, score))
    if not evidence:
        return AnswerOut(answer="检索结果未通过数据库归属校验，无法生成答案。", citations=[])

    sources = [
        f"[{label}] 文件：{document.original_name}；"
        f"页码：{chunk.page_number or '无'}；内容：{chunk.content}"
        for label, chunk, document, _ in evidence
    ]
    answer = await gateway.answer_with_context(question, sources)
    cited_labels = set(re.findall(r"\[S(\d+)\]", answer))
    citations = [
        CitationOut(
            label=label,
            chunk_id=chunk.id,
            document_id=document.id,
            original_name=document.original_name,
            page_number=chunk.page_number,
            position=chunk.position,
            content=chunk.content,
            score=score,
        )
        for label, chunk, document, score in evidence
        if label.removeprefix("S") in cited_labels
    ]
    return AnswerOut(answer=answer, citations=citations)
