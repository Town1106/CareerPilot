"""LangGraph 图构建器 — 根据 Skill 名称构建 StateGraph。"""

import logging

from langgraph.graph import END, StateGraph

from app.harness.nodes import NODE_REGISTRY
from app.harness.state import AgentState

logger = logging.getLogger(__name__)


def build_graph(skill_name: str) -> StateGraph:
    """为指定 Skill 构建 LangGraph StateGraph。

    每个 Skill 对应一个简单的线性图：start → work_node → END。
    后续可扩展为多节点复杂图（如 RAG: retrieve → generate → cite）。
    """
    node_fn = NODE_REGISTRY.get(skill_name)
    if node_fn is None:
        raise ValueError(f"Unknown skill: {skill_name}")

    graph = StateGraph(AgentState)
    graph.add_node("work", node_fn)
    graph.set_entry_point("work")
    graph.add_edge("work", END)

    return graph.compile()