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

    # 输入
    input: dict[str, Any]

    # 消息历史（使用 LangGraph 的 add_messages reducer）
    messages: Annotated[list, add_messages]

    # 步骤事件（流式推送到前端）
    events: Annotated[list[dict[str, Any]], lambda a, b: a + b]

    # 追踪
    run_id: str
    error: str | None

    # ── RAG QA 中间状态 ──
    # retrieved_chunks: list[tuple[DocumentChunk, Document, DocumentVersion, float]]
    retrieved_chunks: list[Any]
    formatted_sources: list[str]  # 格式化后的证据文本
    raw_answer: str  # LLM 原始回答
    citations: list[dict[str, Any]]  # 引用列表

    # ── JD 分析中间状态 ──
    jd_raw_text: str  # JD 原始文本
    extraction_result: Any  # ExtractionResult
    normalized_items: list[Any]  # 原子化后的要求列表
    draft_requirements: list[dict[str, Any]]  # 带候选证据的要求
    candidate_labels: dict[str, Any]  # label → (index, chunk, ...)
    judgment_result: Any  # JudgmentResult

    # ── 学习计划中间状态 ──
    competency_gaps: list[Any]  # 能力差距列表
    plan_goal: str  # 计划目标
    plan_tasks: list[dict[str, Any]]  # 生成的任务列表

    # ── 最终输出 ──
    output: dict[str, Any]