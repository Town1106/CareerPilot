"""LangGraph 节点函数 — 将现有 Service 拆分为独立的 Graph 节点。

每个节点函数签名为 (state: AgentState) -> dict，返回部分状态更新。
"""

import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.database import SessionFactory
from app.harness.state import AgentState
from app.jobs.models import JobDescription
from app.jobs.schemas import (
    ExtractedRequirement,
    ExtractionResult,
)
from app.jobs.service import (
    COVERAGE_SCORE,
    IMPORTANCE,
    atomic_requirements,
    extract_requirements,
    judge_evidence,
)
from app.plans.service import competency_gap
from app.rag import gateway
from app.rag.gateway import AIServiceError
from app.rag.service import retrieve_chunks

logger = logging.getLogger(__name__)


def _emit(event_type: str, **kwargs: object) -> dict:
    return {"events": [{"event": event_type, "step": event_type, **kwargs}]}


# ════════════════════════════════════════════════════════════════════
# RAG QA 节点
# ════════════════════════════════════════════════════════════════════

async def rag_retrieve(state: AgentState) -> dict:
    """检索节点：向量检索相关文档 Chunk。"""
    ws_id = uuid.UUID(state["workspace_id"])
    question = state["input"]["question"]

    async with SessionFactory() as db:
        hits = await retrieve_chunks(db, ws_id, question)
        chunk_records = [
            {
                "chunk_id": str(chunk.id),
                "document": version.original_name,
                "score": round(score, 4),
                "content": chunk.content[:200],
            }
            for chunk, _, version, score in hits
        ]
        return {
            "retrieved_chunks": [(chunk, doc, version, score) for chunk, doc, version, score in hits],
            "events": [
                {"event": "step_start", "step": "retrieve", "message": "正在检索知识库…"},
                {"event": "step_complete", "step": "retrieve", "chunk_count": len(hits), "chunks": chunk_records},
            ],
        }


def rag_has_results(state: AgentState) -> str:
    """条件路由：有检索结果走 generate，无结果走 no_results。"""
    chunks = state.get("retrieved_chunks", [])
    return "no_results" if not chunks else "generate"


async def rag_generate(state: AgentState) -> dict:
    """生成节点：基于检索证据生成回答。"""
    chunks = state.get("retrieved_chunks", [])
    evidence = []
    for i, (chunk, document, version, score) in enumerate(chunks, 1):
        label = f"S{i}"
        evidence.append((label, chunk, document, version, score))

    sources = [
        f"[{label}] 文件：{version.original_name}；"
        f"页码：{chunk.page_number or '无'}；内容：{chunk.content}"
        for label, chunk, _, version, _ in evidence
    ]

    question = state["input"]["question"]
    answer = await gateway.answer_with_context(question, sources)

    cited_labels = set(re.findall(r"\[S(\d+)\]", answer))
    citations = [
        {
            "label": label,
            "chunk_id": str(chunk.id),
            "document_id": str(document.id),
            "original_name": version.original_name,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "score": score,
        }
        for label, chunk, document, version, score in evidence
        if label.removeprefix("S") in cited_labels
    ]

    return {
        "raw_answer": answer,
        "citations": citations,
        "output": {"answer": answer, "citations": citations},
        "events": [
            {"event": "step_complete", "step": "generate", "answer": answer[:200], "citations_count": len(citations)},
            {"event": "done", "run_id": state.get("run_id", "")},
        ],
    }


async def rag_no_results(state: AgentState) -> dict:
    """兜底节点：无检索结果时返回提示。"""
    return {
        "output": {
            "answer": "当前知识库中没有可用于回答该问题的已索引证据。",
            "citations": [],
        },
        "events": [
            {"event": "step_complete", "step": "no_results", "message": "未找到相关证据"},
            {"event": "done", "run_id": state.get("run_id", "")},
        ],
    }


# ════════════════════════════════════════════════════════════════════
# JD 分析节点
# ════════════════════════════════════════════════════════════════════

async def jd_extract(state: AgentState) -> dict:
    """JD 抽取节点：从 JD 原文中结构化抽取要求。"""
    jd_id = uuid.UUID(state["input"]["jd_id"])

    async with SessionFactory() as db:
        jd = await db.scalar(select(JobDescription).where(JobDescription.id == jd_id))
        if not jd:
            return {
                "error": "JD 不存在",
                "events": [{"event": "error", "message": "JD 不存在"}, {"event": "done", "run_id": state.get("run_id", "")}],
            }

        extraction, _raw_output = await extract_requirements(jd.raw_text)
        return {
            "jd_raw_text": jd.raw_text,
            "extraction_result": {
                "requirements": [
                    {"name": r.name, "category": r.category, "requirement_type": r.requirement_type, "raw_evidence": r.raw_evidence}
                    for r in extraction.requirements
                ]
            },
            "events": [
                {"event": "step_start", "step": "extract", "message": "正在抽取 JD 要求…"},
                {"event": "step_complete", "step": "extract", "requirement_count": len(extraction.requirements)},
            ],
        }


async def jd_normalize(state: AgentState) -> dict:
    """标准化节点：别名归一化、原子化拆分。"""
    raw = state.get("extraction_result", {})
    raw_requirements = raw.get("requirements", [])
    if not raw_requirements:
        return {
            "error": "抽取结果为空",
            "events": [{"event": "error", "message": "抽取结果为空"}],
        }

    extraction = ExtractionResult(
        requirements=[
            ExtractedRequirement(**r) for r in raw_requirements
        ]
    )
    normalized = atomic_requirements(extraction)

    return {
        "normalized_items": [
            {"name": item.name, "category": item.category, "requirement_type": item.requirement_type, "raw_evidence": item.raw_evidence}
            for item in normalized
        ],
        "events": [
            {"event": "step_start", "step": "normalize", "message": "正在标准化能力要求…"},
            {"event": "step_complete", "step": "normalize", "normalized_count": len(normalized)},
        ],
    }


async def jd_retrieve_evidence(state: AgentState) -> dict:
    """证据检索节点：为每项要求检索知识库证据。"""
    ws_id = uuid.UUID(state["workspace_id"])
    items = state.get("normalized_items", [])

    async with SessionFactory() as db:
        drafts = []
        candidate_labels = {}

        for index, item in enumerate(items):
            query = f"{item['name']}；{item['raw_evidence']}"
            hits = await retrieve_chunks(db, ws_id, query, limit=3)
            candidates = []
            for position, (chunk, document, version, score) in enumerate(hits, 1):
                label = f"R{index}S{position}"
                candidates.append({
                    "label": label,
                    "file": version.original_name,
                    "page": chunk.page_number,
                    "text": chunk.content,
                })
                candidate_labels[label] = {
                    "index": index,
                    "chunk_id": str(chunk.id),
                    "document_name": version.original_name,
                    "score": score,
                    "content": chunk.content[:200],
                }
            drafts.append({
                "index": index,
                "name": item["name"],
                "raw_requirement": item["raw_evidence"],
                "candidates": candidates,
            })

        return {
            "draft_requirements": drafts,
            "candidate_labels": candidate_labels,
            "events": [
                {"event": "step_start", "step": "retrieve_evidence", "message": f"正在为 {len(items)} 项要求检索证据…"},
                {"event": "step_complete", "step": "retrieve_evidence", "total_candidates": len(candidate_labels)},
            ],
        }


async def jd_judge(state: AgentState) -> dict:
    """证据核验节点：LLM 判断每项要求的覆盖度。"""
    drafts = state.get("draft_requirements", [])
    has_candidates = any(draft["candidates"] for draft in drafts)

    if has_candidates:
        judgments = await judge_evidence(drafts)
        judgment_data = [
            {
                "requirement_index": j.requirement_index,
                "coverage": j.coverage,
                "confidence": j.confidence,
                "explanation": j.explanation,
                "evidence_labels": j.evidence_labels,
            }
            for j in judgments.judgments
        ]
    else:
        judgment_data = []

    # 计算覆盖率
    items = state.get("normalized_items", [])
    weighted = 0.0
    total = 0
    judgment_map = {j["requirement_index"]: j for j in judgment_data}

    for i, item in enumerate(items):
        imp = IMPORTANCE.get(item["requirement_type"], 1)
        cov = judgment_map[i]["coverage"] if i in judgment_map else "uncovered"
        weighted += imp * COVERAGE_SCORE.get(cov, 0.0)
        total += imp

    coverage = round(100 * weighted / total, 1) if total else 0

    return {
        "judgment_result": {"judgments": judgment_data},
        "output": {
            "coverage": coverage,
            "requirements_count": len(items),
            "judged_count": len(judgment_data),
        },
        "events": [
            {"event": "step_start", "step": "judge", "message": "正在核验证据覆盖度…"},
            {"event": "step_complete", "step": "judge",
             "coverage": coverage,
             "covered": sum(1 for j in judgment_data if j["coverage"] == "covered"),
             "partial": sum(1 for j in judgment_data if j["coverage"] == "partial"),
             "uncovered": sum(1 for j in judgment_data if j["coverage"] == "uncovered")},
            {"event": "done", "run_id": state.get("run_id", "")},
        ],
    }


# ════════════════════════════════════════════════════════════════════
# 学习计划节点
# ════════════════════════════════════════════════════════════════════

async def plan_analyze_gaps(state: AgentState) -> dict:
    """差距分析节点：获取工作空间的能力差距。"""
    ws_id = uuid.UUID(state["workspace_id"])

    async with SessionFactory() as db:
        gaps = await competency_gap(db, ws_id)
        gap_data = [
            {
                "competency": g.competency,
                "category": g.category,
                "worst_coverage": g.worst_coverage,
                "max_importance": g.max_importance,
                "priority": g.priority,
                "job_count": g.job_count,
            }
            for g in gaps
        ]
        return {
            "competency_gaps": gap_data,
            "events": [
                {"event": "step_start", "step": "analyze_gaps", "message": "正在分析能力差距…"},
                {"event": "step_complete", "step": "analyze_gaps", "gap_count": len(gap_data)},
            ],
        }


async def plan_generate(state: AgentState) -> dict:
    """计划生成节点：基于差距生成学习计划。"""
    gaps = state.get("competency_gaps", [])
    input_data = state["input"]
    start_date_str = input_data.get("start_date", datetime.now(UTC).date().isoformat())
    end_date_str = input_data.get("end_date", (datetime.now(UTC).date() + timedelta(days=14)).isoformat())
    daily_minutes = input_data.get("daily_minutes", 120)

    gap_text = json.dumps(gaps[:10], ensure_ascii=False) if gaps else "暂无明确的能力差距数据"

    prompt = (
        "你是学习计划生成器。根据用户的能力差距，生成一个为期 "
        f"{start_date_str} 至 {end_date_str}、每天 {daily_minutes} 分钟的学习计划。"
        "返回 JSON 对象，包含 goal（计划目标，一句话）和 tasks（任务数组）。"
        "每个任务包含 competency_name、title、description、scheduled_date、duration_minutes、priority。"
        "优先安排高优先级差距对应的学习任务，每天不超过 3 个任务。"
    )

    try:
        result = await gateway.structured_chat(prompt, gap_text)
        tasks = result.get("tasks", []) if isinstance(result, dict) else []
        goal = result.get("goal", "个性化学习计划") if isinstance(result, dict) else "个性化学习计划"

        return {
            "plan_goal": goal,
            "plan_tasks": tasks,
            "output": {
                "goal": goal,
                "tasks_count": len(tasks),
                "tasks": tasks,
            },
            "events": [
                {"event": "step_start", "step": "generate_plan", "message": "正在生成学习计划…"},
                {"event": "step_complete", "step": "generate_plan", "task_count": len(tasks), "goal": goal},
                {"event": "done", "run_id": state.get("run_id", "")},
            ],
        }
    except AIServiceError as e:
        return {
            "error": str(e),
            "events": [{"event": "error", "message": str(e)}, {"event": "done", "run_id": state.get("run_id", "")}],
        }


# ════════════════════════════════════════════════════════════════════
# 节点注册表
# ════════════════════════════════════════════════════════════════════

NODE_REGISTRY = {
    "rag_qa": {
        "rag_retrieve": rag_retrieve,
        "rag_generate": rag_generate,
        "rag_no_results": rag_no_results,
    },
    "jd_analysis": {
        "jd_extract": jd_extract,
        "jd_normalize": jd_normalize,
        "jd_retrieve_evidence": jd_retrieve_evidence,
        "jd_judge": jd_judge,
    },
    "study_plan": {
        "plan_analyze_gaps": plan_analyze_gaps,
        "plan_generate": plan_generate,
    },
}