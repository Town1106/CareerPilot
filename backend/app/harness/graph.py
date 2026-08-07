"""LangGraph 图构建器。"""

from langgraph.graph import END, StateGraph

from app.harness.nodes import NODE_REGISTRY
from app.harness.state import AgentState


def build_graph(skill_name: str):
    node = NODE_REGISTRY.get(skill_name)
    if node is None:
        raise ValueError(f"Unknown skill: {skill_name}")
    graph = StateGraph(AgentState)
    graph.add_node("execute", node)
    graph.set_entry_point("execute")
    graph.add_edge("execute", END)
    return graph.compile()
