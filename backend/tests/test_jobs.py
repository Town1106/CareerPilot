import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.documents import files
from app.documents import router as documents_router
from app.jobs.schemas import ExtractedRequirement, ExtractionResult
from app.jobs.service import atomic_requirements
from app.rag import gateway, store

TEST_UPLOAD_DIR = Path(__file__).parent / "_uploads"


def test_atomic_requirements_normalizes_grouped_jd_terms() -> None:
    result = ExtractionResult(
        requirements=[
            ExtractedRequirement(
                name="Java, Spring Boot, RESTful API",
                category="technical",
                requirement_type="must",
                raw_evidence="熟悉 Java、Spring Boot 和 RESTful API",
            ),
            ExtractedRequirement(
                name="Java 后端开发经验",
                category="experience",
                requirement_type="must",
                raw_evidence="具备 Java 后端开发经验",
            ),
            ExtractedRequirement(
                name="MySQL/PostgreSQL, SQL 优化",
                category="technical",
                requirement_type="must",
                raw_evidence="熟悉 MySQL/PostgreSQL 和 SQL 优化",
            ),
            ExtractedRequirement(
                name="Kubernetes 生产环境运维经验",
                category="experience",
                requirement_type="preferred",
                raw_evidence="有 Kubernetes 生产环境运维经验",
            ),
            ExtractedRequirement(
                name="五年以上后端开发经验",
                category="experience",
                requirement_type="must",
                raw_evidence="五年以上后端开发经验",
            ),
        ]
    )

    requirements = atomic_requirements(result)
    by_name = {item.name: item for item in requirements}
    assert set(by_name) == {
        "java",
        "spring boot",
        "restful api",
        "后端开发经验",
        "mysql",
        "postgresql",
        "sql 优化",
        "kubernetes",
    }
    assert by_name["java"].category == "technical"
    assert by_name["kubernetes"].category == "technical"
    assert by_name["后端开发经验"].category == "experience"


def create_workspace(client: TestClient) -> str:
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": "jobs@example.com", "password": "password123"},
        ).status_code
        == 201
    )
    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Java 求职", "target_role": "Java 后端"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def fake_ai(monkeypatch):
    qdrant = QdrantClient(":memory:", force_disable_check_same_thread=True)
    monkeypatch.setattr(store, "get_client", lambda: qdrant)
    monkeypatch.setattr(files, "UPLOAD_DIR", TEST_UPLOAD_DIR)
    monkeypatch.setattr(documents_router, "DASHSCOPE_API_KEY", "")

    async def fake_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1023 for _ in texts]

    async def fake_structured(system: str, prompt: str) -> dict:
        if "JD 结构化" in system:
            if "第二个岗位" in prompt:
                return {
                    "requirements": [
                        {
                            "name": "Spring Boot",
                            "category": "technical",
                            "requirement_type": "must",
                            "raw_evidence": "熟练使用 Spring Boot",
                        },
                        {
                            "name": "Redis",
                            "category": "technical",
                            "requirement_type": "preferred",
                            "raw_evidence": "了解 Redis",
                        },
                    ]
                }
            return {
                "requirements": [
                    {
                        "name": "SpringBoot",
                        "category": "technical",
                        "requirement_type": "must",
                        "raw_evidence": "熟练使用 Spring Boot",
                    },
                    {
                        "name": "Kubernetes",
                        "category": "technical",
                        "requirement_type": "preferred",
                        "raw_evidence": "了解 Kubernetes",
                    },
                    {
                        "name": "Spring Boot框架",
                        "category": "responsibility",
                        "requirement_type": "responsibility",
                        "raw_evidence": "负责 Spring Boot 服务开发",
                    },
                ]
            }
        requirements = json.loads(prompt)["requirements"]
        return {
            "judgments": [
                {
                    "requirement_index": item["index"],
                    "coverage": "covered" if item["index"] == 0 else "uncovered",
                    "confidence": 0.9,
                    "explanation": "资料中有明确证据" if item["index"] == 0 else "未找到证据",
                    "evidence_labels": [item["candidates"][0]["label"]]
                    if item["index"] == 0
                    else [],
                }
                for item in requirements
            ]
        }

    monkeypatch.setattr(gateway, "embed_texts", fake_embeddings)
    monkeypatch.setattr(gateway, "structured_chat", fake_structured)
    yield qdrant
    qdrant.close()


def test_job_analysis_gap_and_comparison(client: TestClient, fake_ai) -> None:
    workspace_id = create_workspace(client)
    documents_url = f"/api/v1/workspaces/{workspace_id}/documents"
    document = client.post(
        documents_url,
        data={"category": "resume"},
        files={
            "file": (
                "resume.md",
                "候选人有三年 Java 经验，熟练使用 Spring Boot 开发 REST API。",
                "text/markdown",
            )
        },
    ).json()
    assert client.post(f"{documents_url}/{document['id']}/index").status_code == 200

    jobs_url = f"/api/v1/workspaces/{workspace_id}/jobs"
    first = client.post(
        jobs_url,
        json={
            "company": "甲公司",
            "title": "Java 后端",
            "raw_text": "岗位要求熟练使用 Spring Boot 开发服务，并了解 Kubernetes 容器编排。" * 2,
        },
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    analysis = client.post(f"{jobs_url}/{first_id}/analyze")
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["job"]["coverage_score"] == 75.0
    requirements = analysis.json()["requirements"]
    assert [item["competency"] for item in requirements] == ["kubernetes", "spring boot"]
    spring = next(item for item in requirements if item["competency"] == "spring boot")
    assert spring["coverage"] == "covered"
    assert spring["evidence"][0]["original_name"] == "resume.md"

    gap = client.get(f"/api/v1/workspaces/{workspace_id}/competency-gap")
    assert gap.status_code == 200
    assert gap.json()[0]["competency"] == "kubernetes"

    second = client.post(
        jobs_url,
        json={
            "company": "乙公司",
            "title": "平台开发",
            "raw_text": "第二个岗位要求熟练使用 Spring Boot，并将 Redis 作为加分项。" * 2,
        },
    ).json()
    second_id = second["id"]
    assert client.post(f"{jobs_url}/{second_id}/analyze").status_code == 200
    compared = client.post(
        f"{jobs_url}/compare", json={"job_ids": [first_id, second_id]}
    )
    assert compared.status_code == 200, compared.text
    assert [item["competency"] for item in compared.json()["common"]] == ["spring boot"]
    assert {item["competency"] for item in compared.json()["differences"]} == {
        "kubernetes",
        "redis",
    }

    assert client.delete(f"/api/v1/workspaces/{workspace_id}").status_code == 204
    assert list(TEST_UPLOAD_DIR.iterdir()) == []


def test_job_analysis_rejects_invalid_model_output(client: TestClient, monkeypatch) -> None:
    workspace_id = create_workspace(client)

    async def invalid_structured(_: str, __: str) -> dict:
        return {"requirements": []}

    monkeypatch.setattr(gateway, "structured_chat", invalid_structured)
    jobs_url = f"/api/v1/workspaces/{workspace_id}/jobs"
    job = client.post(
        jobs_url,
        json={
            "company": "测试公司",
            "title": "测试岗位",
            "raw_text": "这是一段长度足够但模型将返回空要求的测试岗位描述，用于验证结构化输出失败处理。" * 2,
        },
    ).json()
    response = client.post(f"{jobs_url}/{job['id']}/analyze")
    assert response.status_code == 502
    assert client.get(jobs_url).json()[0]["status"] == "failed"
