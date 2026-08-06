"""Agent 状态定义 — LangGraph StateGraph 的共享状态。"""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """LangGraph Agent 共享状态。

    各节点通过返回部分字段来更新状态，未返回的字段保持不变。
    """

    # 元信息
    skill_name: str
    workspace_id: str
    user_id: str

    # 输入输出
    input: dict[str, Any]
    output: dict[str, Any]

    # 消息历史（使用 LangGraph 的 add_messages reducer）
    messages: Annotated[list, add_messages]

    # 步骤事件（流式推送到前端）
    events: Annotated[list[dict[str, Any]], lambda a, b: a + b]

    # 追踪
    run_id: str
    error: str | None