"""Agent 状态定义 — LangGraph StateGraph 的共享状态。"""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph Agent 共享状态。

    各节点通过返回部分字段来更新状态，未返回的字段保持不变。
    """

    # 元信息
    skill_name: str
    workspace_id: str
    user_id: str
    db: Any

    # 输入
    input: dict[str, Any]

    # 消息历史（使用 LangGraph 的 add_messages reducer）
    events: list[dict[str, Any]]

    # 步骤事件（流式推送到前端）

    # 追踪
    run_id: str
    error: str | None

    # ── RAG QA 中间状态 ──
    # retrieved_chunks: list[tuple[DocumentChunk, Document, DocumentVersion, float]]

    # ── JD 分析中间状态 ──

    # ── 学习计划中间状态 ──

    # ── 最终输出 ──
    output: dict[str, Any]
