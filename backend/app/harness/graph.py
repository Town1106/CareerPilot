"""LangGraph 图构建器 — 根据 Skill 构建多节点 StateGraph。"""

import logging

from langgraph.graph import END, StateGraph

from app.harness.nodes import NODE_REGISTRY, rag_has_results
from app.harness.state import AgentState

logger = logging.getLogger(__name__)


def _build_rag_qa() -> StateGraph:
    """RAG 问答图：retrieve → (有条件) → generate → END
                                     └→ no_results → END
    """
    nodes = NODE_REGISTRY["rag_qa"]
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", nodes["rag_retrieve"])
    graph.add_node("generate", nodes["rag_generate"])
    graph.add_node("no_results", nodes["rag_no_results"])

    graph.set_entry_point("retrieve")

    # 条件路由：有结果 → generate，无结果 → no_results
    graph.add_conditional_edges("retrieve", rag_has_results, {
        "generate": "generate",
        "no_results": "no_results",
    })

    graph.add_edge("generate", END)
    graph.add_edge("no_results", END)

    return graph.compile()


def _build_jd_analysis() -> StateGraph:
    """JD 分析图：extract → normalize → retrieve_evidence → judge → END"""
    nodes = NODE_REGISTRY["jd_analysis"]
    graph = StateGraph(AgentState)

    graph.add_node("extract", nodes["jd_extract"])
    graph.add_node("normalize", nodes["jd_normalize"])
    graph.add_node("retrieve_evidence", nodes["jd_retrieve_evidence"])
    graph.add_node("judge", nodes["jd_judge"])

    graph.set_entry_point("extract")
    graph.add_edge("extract", "normalize")
    graph.add_edge("normalize", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "judge")
    graph.add_edge("judge", END)

    return graph.compile()


def _build_study_plan() -> StateGraph:
    """学习计划图：analyze_gaps → generate → END"""
    nodes = NODE_REGISTRY["study_plan"]
    graph = StateGraph(AgentState)

    graph.add_node("analyze_gaps", nodes["plan_analyze_gaps"])
    graph.add_node("generate", nodes["plan_generate"])

    graph.set_entry_point("analyze_gaps")
    graph.add_edge("analyze_gaps", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


_GRAPH_BUILDERS = {
    "rag_qa": _build_rag_qa,
    "jd_analysis": _build_jd_analysis,
    "study_plan": _build_study_plan,
}


def build_graph(skill_name: str) -> StateGraph:
    """为指定 Skill 构建多节点 LangGraph StateGraph。

    支持的 Skill:
    - ``rag_qa``: retrieve → generate / no_results → END
    - ``jd_analysis``: extract → normalize → retrieve_evidence → judge → END
    - ``study_plan``: analyze_gaps → generate → END
    """
    builder = _GRAPH_BUILDERS.get(skill_name)
    if builder is None:
        raise ValueError(f"Unknown skill: {skill_name}")
    return builder()