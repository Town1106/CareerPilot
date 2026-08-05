import asyncio

from fastapi.testclient import TestClient

from app.rag import gateway


def create_analyzed_job(client: TestClient, monkeypatch) -> tuple[str, str]:
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": "research@example.com", "password": "password123"},
        ).status_code
        == 201
    )
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "公司面经", "target_role": "Java 后端"},
    ).json()

    async def extract(_: str, __: str) -> dict:
        return {
            "requirements": [
                {
                    "name": "Java",
                    "category": "technical",
                    "requirement_type": "must",
                    "raw_evidence": "熟悉 Java 并发编程",
                }
            ]
        }

    monkeypatch.setattr(gateway, "structured_chat", extract)
    jobs_url = f"/api/v1/workspaces/{workspace['id']}/jobs"
    job = client.post(
        jobs_url,
        json={
            "company": "示例科技",
            "title": "Java 后端工程师",
            "raw_text": "负责核心服务开发，要求熟悉 Java 并发编程和常见中间件。" * 2,
        },
    ).json()
    assert client.post(f"{jobs_url}/{job['id']}/analyze").status_code == 200
    return workspace["id"], job["id"]


def test_question_modes_shortage_and_pool_reuse(client: TestClient, monkeypatch) -> None:
    workspace_id, job_id = create_analyzed_job(client, monkeypatch)
    source_one = "https://example.com/interview/1?from=search"
    source_two = "https://example.org/posts/2"
    web_calls: list[list[str]] = []

    async def fake_web(
        company: str,
        role: str,
        wanted_count: int,
        interview_type: str,
        excluded_questions: list[str],
    ) -> tuple[str, list[str]]:
        assert (company, role) == ("示例科技", "Java 后端工程师")
        assert wanted_count in {2, 3}
        assert interview_type == "mixed"
        web_calls.append(excluded_questions)
        return "搜索到两道公开面经题。", [source_one, source_two]

    async def fake_structured(system: str, _: str) -> dict:
        if "面经题库结构化抽取器" in system:
            return {
                "questions": [
                    {
                        "question": "线程池的核心参数如何根据业务场景设置？",
                        "competency": "Java 并发",
                        "interview_stage": "technical",
                        "source_url": "https://example.com/interview/1",
                        "source_title": "示例科技 Java 面经",
                        "excerpt": "面试官询问了线程池参数设置。",
                    },
                    {
                        "question": "如何处理缓存穿透和缓存雪崩？",
                        "competency": "Redis",
                        "interview_stage": "system_design",
                        "source_url": source_two,
                        "source_title": "后端面试复盘",
                        "excerpt": "系统设计环节讨论缓存异常。",
                    },
                    {
                        "question": "这道题的来源是模型虚构的。",
                        "competency": "安全",
                        "interview_stage": "technical",
                        "source_url": "https://invalid.example/fake",
                        "source_title": "无效来源",
                        "excerpt": "不应入库。",
                    },
                ]
            }
        if "模拟面试官" in system:
            return {"question": "请解释 Java 内存模型。"}
        raise AssertionError(system)

    monkeypatch.setattr(gateway, "web_search_interview_questions", fake_web)
    monkeypatch.setattr(gateway, "structured_chat", fake_structured)
    interviews_url = f"/api/v1/workspaces/{workspace_id}/interviews"

    all_real = client.post(
        interviews_url,
        json={
            "job_description_id": job_id,
            "question_limit": 3,
            "interview_type": "mixed",
            "question_source_mode": "all_real",
        },
    ).json()
    shortage = client.post(f"{interviews_url}/{all_real['id']}/start")
    assert shortage.status_code == 409
    assert "需要 3 道，仅找到 2 道" in shortage.text

    mixed = client.post(
        interviews_url,
        json={
            "job_description_id": job_id,
            "question_limit": 3,
            "interview_type": "mixed",
            "question_source_mode": "mixed",
        },
    ).json()
    started = client.post(f"{interviews_url}/{mixed['id']}/start")
    assert started.status_code == 200, started.text
    assert started.json()["turns"][0]["source_type"] == "company_research"
    assert started.json()["turns"][0]["source_url"].startswith("https://example.")
    assert len(web_calls) == 2
    assert len(web_calls[1]) == 2

    reused = client.post(
        interviews_url,
        json={
            "job_description_id": job_id,
            "question_limit": 3,
            "interview_type": "mixed",
            "question_source_mode": "mixed",
        },
    ).json()
    reused_started = client.post(f"{interviews_url}/{reused['id']}/start")
    assert reused_started.status_code == 200
    assert len(web_calls) == 2

    plain = client.post(
        interviews_url,
        json={
            "job_description_id": job_id,
            "question_limit": 3,
            "interview_type": "mixed",
            "question_source_mode": "no_search",
        },
    ).json()
    plain_started = client.post(f"{interviews_url}/{plain['id']}/start")
    assert plain_started.status_code == 200
    assert plain_started.json()["turns"][0]["source_type"] == "job_gap"
    assert len(web_calls) == 2
    assert (
        client.get(f"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/research").status_code == 404
    )


def test_web_search_parses_responses_sources(monkeypatch) -> None:
    monkeypatch.setattr(gateway, "DASHSCOPE_API_KEY", "test-key")

    async def fake_post(_, path: str, payload: dict) -> dict:
        assert path == "/responses"
        assert payload["tool_choice"] == "required"
        assert payload["enable_thinking"] is False
        assert "已有问题" in payload["input"]
        return {
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [{"type": "url", "url": "https://example.com/experience"}]
                    },
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "搜索摘要"}],
                },
            ]
        }

    monkeypatch.setattr(gateway, "_post", fake_post)
    text, sources = asyncio.run(
        gateway.web_search_interview_questions("公司", "岗位", 5, "technical", ["已有问题"])
    )
    assert text == "搜索摘要"
    assert sources == ["https://example.com/experience"]
