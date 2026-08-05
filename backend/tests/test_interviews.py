import json

from fastapi.testclient import TestClient

from app.rag import gateway


def create_analyzed_job(client: TestClient, monkeypatch) -> tuple[str, str]:
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": "interview@example.com", "password": "password123"},
        ).status_code
        == 201
    )
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "模拟面试", "target_role": "Java 后端"},
    ).json()

    async def extract(system: str, _: str) -> dict:
        assert "JD 结构化抽取器" in system
        return {
            "requirements": [
                {
                    "name": "Java",
                    "category": "technical",
                    "requirement_type": "must",
                    "raw_evidence": "熟悉 Java 并发编程",
                },
                {
                    "name": "Redis",
                    "category": "technical",
                    "requirement_type": "preferred",
                    "raw_evidence": "了解 Redis 缓存设计",
                },
            ]
        }

    monkeypatch.setattr(gateway, "structured_chat", extract)
    jobs_url = f"/api/v1/workspaces/{workspace['id']}/jobs"
    job = client.post(
        jobs_url,
        json={
            "company": "示例公司",
            "title": "后端开发工程师",
            "raw_text": "负责核心业务系统开发，要求熟悉 Java 并发编程，了解 Redis 缓存设计。" * 2,
        },
    ).json()
    assert client.post(f"{jobs_url}/{job['id']}/analyze").status_code == 200
    return workspace["id"], job["id"]


def test_interview_resume_report_and_memory(client: TestClient, monkeypatch) -> None:
    workspace_id, job_id = create_analyzed_job(client, monkeypatch)
    question_number = 0

    async def interview_ai(system: str, prompt: str) -> dict:
        nonlocal question_number
        if "模拟面试官" in system:
            question_number += 1
            competency = json.loads(prompt)["competency"]
            return {"question": f"第 {question_number} 题：请解释你的 {competency} 实践。"}
        if "流程控制器" in system:
            answer = json.loads(prompt)["answer"]
            return {
                "quality": 40 if "简短" in answer else 80,
                "should_follow_up": "简短" in answer,
                "observation": "回答缺少细节" if "简短" in answer else "回答包含原理和案例",
                "follow_up_question": "请补充一个具体案例。" if "简短" in answer else None,
            }
        if "独立面试评分官" in system:
            competencies = json.loads(prompt)["allowed_competencies"]
            return {
                "overall_score": 72,
                "summary": "基础较好，但需要补充边界条件。",
                "strengths": ["能够结合项目回答"],
                "issues": ["部分原理不够完整"],
                "competency_scores": [
                    {
                        "competency": competency,
                        "score": 75 if competency == "java" else 58,
                        "rubric": "原理、场景和取舍各占一定权重。",
                        "evidence": "回答 1 提到了实际使用场景",
                        "strengths": ["有实践经验"],
                        "issues": ["边界条件不足"],
                        "suggestion": "补充失败场景和方案取舍。",
                    }
                    for competency in competencies
                ],
            }
        raise AssertionError(system)

    monkeypatch.setattr(gateway, "structured_chat", interview_ai)
    url = f"/api/v1/workspaces/{workspace_id}/interviews"
    created = client.post(
        url,
        json={
            "job_description_id": job_id,
            "interview_type": "mixed",
            "question_limit": 3,
        },
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    started = client.post(f"{url}/{session_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    assert len(started.json()["turns"]) == 1

    followed = client.post(f"{url}/{session_id}/answers", json={"answer": "简短回答"})
    assert followed.status_code == 200, followed.text
    assert followed.json()["turns"][1]["is_follow_up"] is True
    assert client.get(f"{url}/{session_id}").json()["turns"][0]["answer"] == "简短回答"

    continued = client.post(
        f"{url}/{session_id}/answers",
        json={"answer": "我结合线程池原理和线上案例进行了完整说明。"},
    )
    assert continued.status_code == 200, continued.text
    assert len(continued.json()["turns"]) == 3
    assert continued.json()["turns"][2]["competency_name"] == "redis"

    completed = client.post(
        f"{url}/{session_id}/answers",
        json={"answer": "我说明了缓存穿透、雪崩和一致性的处理方案。"},
    )
    assert completed.status_code == 200, completed.text
    report = completed.json()
    assert report["status"] == "completed"
    assert report["overall_score"] == 72
    assert {item["competency_name"] for item in report["scores"]} == {"java", "redis"}
    assert client.get(f"{url}/{session_id}/report").status_code == 200

    memories_url = f"/api/v1/workspaces/{workspace_id}/memories"
    memories = client.get(memories_url).json()
    assert {item["competency_name"] for item in memories} == {"java", "redis"}
    redis = next(item for item in memories if item["competency_name"] == "redis")
    assert redis["error_count"] == 1
    updated = client.patch(
        f"{memories_url}/{redis['id']}", json={"confirmed": True, "mastery_score": 60}
    )
    assert updated.status_code == 200
    assert updated.json()["confirmed"] is True
    assert updated.json()["mastery_score"] == 60
    assert client.delete(f"{memories_url}/{redis['id']}").status_code == 204
    assert len(client.get(memories_url).json()) == 1


def test_interview_requires_analyzed_job(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": "draft@example.com", "password": "password123"},
        ).status_code
        == 201
    )
    workspace = client.post("/api/v1/workspaces", json={"name": "待分析"}).json()
    jobs_url = f"/api/v1/workspaces/{workspace['id']}/jobs"
    job = client.post(
        jobs_url,
        json={
            "company": "公司",
            "title": "岗位",
            "raw_text": "这是一段尚未分析但长度满足校验要求的岗位描述文本。" * 3,
        },
    ).json()
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/interviews",
        json={"job_description_id": job["id"], "question_limit": 5},
    )
    assert response.status_code == 409
