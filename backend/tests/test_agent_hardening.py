import asyncio
import json

from fastapi.testclient import TestClient

from app.jobs.schemas import EvidenceJudgment, JudgmentResult
from app.jobs.service import enforce_evidence_links
from app.tools.models import ToolDefinition, ToolPolicy


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201


def create_workspace(client: TestClient, name: str = "Agent 测试") -> str:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_agent_stream_checks_workspace_owner(client: TestClient) -> None:
    register(client, "agent-owner@example.com")
    workspace_id = create_workspace(client)
    client.post("/api/v1/auth/logout")
    register(client, "agent-other@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/agent/stream",
        json={"skill_name": "rag_qa", "input": {"question": "项目用了什么技术？"}},
    )
    assert response.status_code == 404


def test_agent_stream_returns_complete_done_output(client: TestClient) -> None:
    register(client, "agent-output@example.com")
    workspace_id = create_workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/agent/stream",
        json={"skill_name": "rag_qa", "input": {"question": "项目用了什么技术？"}},
    )
    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    done = next(event for event in events if event["event"] == "done")
    assert done["output"] == {
        "answer": "当前知识库中没有可用于回答该问题的已索引证据。",
        "citations": [],
    }


def test_evidence_coverage_requires_valid_labels() -> None:
    result = enforce_evidence_links(
        [{"index": 0, "candidates": [{"label": "R0S1"}]}],
        JudgmentResult(
            judgments=[
                EvidenceJudgment(
                    requirement_index=0,
                    coverage="covered",
                    confidence=0.9,
                    explanation="模型声称有证据",
                    evidence_labels=["R0S99"],
                )
            ]
        ),
    )
    assert result.judgments[0].coverage == "uncovered"
    assert result.judgments[0].evidence_labels == []


async def add_document_upload_policy(test_session_factory) -> None:
    async with test_session_factory() as db:
        db.add(
            ToolDefinition(
                name="document-upload",
                version="1.0.0",
                description="上传文档",
                manifest_path="test",
                risk_level="R1",
            )
        )
        db.add(ToolPolicy(tool_name="document-upload", require_approval=True))
        await db.commit()


def test_tool_approval_is_persisted_and_owner_scoped(
    client: TestClient, test_session_factory
) -> None:
    register(client, "approval-owner@example.com")
    workspace_id = create_workspace(client)
    asyncio.run(add_document_upload_policy(test_session_factory))

    blocked = client.post(
        "/api/v1/mcp/github/import",
        json={"workspace_id": workspace_id, "repo_full_name": "owner/repo"},
    )
    assert blocked.status_code == 409
    approval_id = blocked.json()["detail"]["approval_id"]

    client.post("/api/v1/auth/logout")
    register(client, "approval-other@example.com")
    assert (
        client.post(
            f"/api/v1/tools/approvals/{approval_id}/decide", json={"approve": True}
        ).status_code
        == 404
    )

    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login",
        json={"email": "approval-owner@example.com", "password": "correct-horse-battery"},
    )
    decided = client.post(
        f"/api/v1/tools/approvals/{approval_id}/decide", json={"approve": True}
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert client.get("/api/v1/tools/approvals/pending").json() == {"approvals": []}
