"""LangGraph 节点函数 — 将现有 Service 包装为 Graph 节点。

每个节点函数签名为 (state: AgentState) -> dict，返回部分状态更新。
"""

import logging
import uuid

from sqlalchemy import select

from app.core.database import SessionFactory
from app.harness.state import AgentState
from app.jobs.models import JobDescription
from app.jobs.service import analyze_job as _analyze_job
from app.rag.schemas import AnswerOut
from app.rag.service import answer_question as _answer_question

logger = logging.getLogger(__name__)


# ── RAG QA 节点 ──

async def rag_qa_node(state: AgentState) -> dict:
    """RAG 问答节点：检索 + 生成回答。"""
    workspace_id = uuid.UUID(state["workspace_id"])
    question = state["input"]["question"]
    run_id = state.get("run_id", "")

    async with SessionFactory() as db:
        result: AnswerOut = await _answer_question(db, workspace_id, question)
        return {
            "output": {
                "answer": result.answer,
                "citations": [
                    {"source": c.source, "content": c.content}
                    for c in result.citations
                ],
            },
            "events": [
                {"event": "step_complete", "step": "rag_qa", "answer": result.answer[:200]},
                {"event": "done", "run_id": run_id},
            ],
        }


# ── JD 分析节点 ──

async def jd_analysis_node(state: AgentState) -> dict:
    """JD 分析节点：抽取要求 → 标准化 → 差距分析。"""
    jd_id = uuid.UUID(state["input"]["jd_id"])
    run_id = state.get("run_id", "")

    async with SessionFactory() as db:
        jd = await db.scalar(select(JobDescription).where(JobDescription.id == jd_id))
        if not jd:
            return {
                "error": "JD 不存在",
                "events": [
                    {"event": "error", "message": "JD 不存在"},
                    {"event": "done", "run_id": run_id},
                ],
            }

        result = await _analyze_job(db, jd)

        return {
            "output": {
                "requirements_count": len(result.requirements),
                "coverage": result.coverage,
                "status": result.status,
            },
            "events": [
                {"event": "step_complete", "step": "jd_analysis",
                 "requirements_count": len(result.requirements),
                 "coverage": result.coverage},
                {"event": "done", "run_id": run_id},
            ],
        }


# ── 节点注册表 ──

NODE_REGISTRY: dict[str, callable] = {
    "rag_qa": rag_qa_node,
    "jd_analysis": jd_analysis_node,
}