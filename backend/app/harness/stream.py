"""SSE 流式推送 — 将 LangGraph 多节点执行过程转为 Server-Sent Events。"""

import json
import logging
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.graph import build_graph
from app.harness.state import AgentState

logger = logging.getLogger(__name__)


async def stream_agent(
    skill_name: str,
    workspace_id: str,
    user_id: str,
    input_data: dict,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """执行 LangGraph 多节点图并将每个节点的事件作为 SSE 流式推送。

    每个事件格式为 SSE: ``data: {json}\\n\\n``。
    """
    run_id = str(uuid.uuid4())

    # 发送开始事件
    yield _sse({"event": "start", "run_id": run_id, "skill": skill_name})

    try:
        graph = build_graph(skill_name)
        initial_state: AgentState = {
            "skill_name": skill_name,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "input": input_data,
            "db": db,
            "run_id": run_id,
        }

        final_output = None
        async for chunk in graph.astream(initial_state, {"recursion_limit": 25}):
            for node_name, node_output in chunk.items():
                if isinstance(node_output, dict):
                    # 推送节点产出的事件
                    events = node_output.get("events", [])
                    for evt in events:
                        yield _sse(evt)

                    if "output" in node_output:
                        final_output = node_output["output"]

                    # 推送节点产出的错误
                    error = node_output.get("error")
                    if error:
                        yield _sse({"event": "error", "node": node_name, "message": str(error)})
                        return

        yield _sse({"event": "done", "run_id": run_id, "output": final_output})

    except Exception as exc:
        logger.exception("Agent stream failed for skill %s", skill_name)
        yield _sse({"event": "error", "message": str(exc), "run_id": run_id})


def _sse(data: dict) -> str:
    """将 dict 格式化为 SSE data 行。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
