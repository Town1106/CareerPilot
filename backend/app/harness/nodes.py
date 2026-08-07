"""LangGraph 节点：编排现有 Service，不复制业务实现。"""

import uuid

from pydantic import BaseModel
from sqlalchemy import select

from app.harness.state import AgentState
from app.jobs.models import JobDescription
from app.jobs.service import analyze_job
from app.plans.schemas import PlanGenerate
from app.plans.service import generate_plan
from app.rag.schemas import QuestionRequest
from app.rag.service import answer_question
from app.workspaces.models import Workspace


class JDAnalysisInput(BaseModel):
    jd_id: uuid.UUID


async def rag_execute(state: AgentState) -> dict:
    payload = QuestionRequest.model_validate(state["input"])
    result = await answer_question(
        state["db"], uuid.UUID(state["workspace_id"]), payload.question
    )
    return {
        "output": result.model_dump(mode="json"),
        "events": [{"event": "step_complete", "step": "rag_qa"}],
    }


async def jd_execute(state: AgentState) -> dict:
    payload = JDAnalysisInput.model_validate(state["input"])
    workspace_id = uuid.UUID(state["workspace_id"])
    db = state["db"]
    job = await db.scalar(
        select(JobDescription).where(
            JobDescription.id == payload.jd_id,
            JobDescription.workspace_id == workspace_id,
        )
    )
    if not job:
        raise ValueError("JD 不存在")
    result = await analyze_job(db, job)
    return {
        "output": result.model_dump(mode="json"),
        "events": [{"event": "step_complete", "step": "jd_analysis"}],
    }


async def plan_execute(state: AgentState) -> dict:
    payload = PlanGenerate.model_validate(state["input"])
    workspace_id = uuid.UUID(state["workspace_id"])
    db = state["db"]
    workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not workspace:
        raise ValueError("工作空间不存在")
    result = await generate_plan(
        db,
        workspace,
        payload.start_date,
        payload.end_date,
        payload.daily_minutes,
    )
    return {
        "output": result.model_dump(mode="json"),
        "events": [{"event": "step_complete", "step": "study_plan"}],
    }


NODE_REGISTRY = {
    "rag_qa": rag_execute,
    "jd_analysis": jd_execute,
    "study_plan": plan_execute,
}
