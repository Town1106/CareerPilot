import io
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.documents import files
from app.documents import router as documents_router
from app.rag import gateway, store

TEST_UPLOAD_DIR = Path(__file__).parent / "_uploads"


@pytest.fixture(autouse=True)
def disable_real_auto_index(monkeypatch) -> None:
    monkeypatch.setattr(documents_router, "DASHSCOPE_API_KEY", "")


def register_and_create_workspace(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "documents@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    response = client.post(
        "/api/v1/workspaces",
        json={"name": "求职资料", "target_role": "Python 工程师"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_list_and_delete_document(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(files, "UPLOAD_DIR", TEST_UPLOAD_DIR)
    workspace_id = register_and_create_workspace(client)
    url = f"/api/v1/workspaces/{workspace_id}/documents"

    response = client.post(
        url,
        data={"category": "resume"},
        files={"file": ("resume.txt", "个人简介\n\n" + "项目经验" * 300, "text/plain")},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["category"] == "resume"
    assert document["status"] == "parsed"
    assert document["chunk_count"] >= 2
    assert len(list(TEST_UPLOAD_DIR.iterdir())) == 1

    response = client.get(url)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [document["id"]]

    response = client.delete(f"{url}/{document['id']}")
    assert response.status_code == 204
    assert list(TEST_UPLOAD_DIR.iterdir()) == []

    response = client.post(
        url,
        files={"file": ("project.md", "# CareerPilot\n\n项目证据", "text/markdown")},
    )
    assert response.status_code == 201
    assert len(list(TEST_UPLOAD_DIR.iterdir())) == 1
    assert client.delete(f"/api/v1/workspaces/{workspace_id}").status_code == 204
    assert list(TEST_UPLOAD_DIR.iterdir()) == []


def test_rejects_unsupported_document(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(files, "UPLOAD_DIR", TEST_UPLOAD_DIR)
    workspace_id = register_and_create_workspace(client)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("resume.exe", b"not a document", "application/octet-stream")},
    )
    assert response.status_code == 415
    assert list(TEST_UPLOAD_DIR.iterdir()) == []


def test_parses_docx_with_standard_library() -> None:
    content = io.BytesIO()
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>CareerPilot project</w:t></w:r></w:p></w:body>
    </w:document>"""
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("word/document.xml", xml)

    sections = files.parse_document(".docx", content.getvalue())
    assert files.make_chunks(sections) == [(None, "CareerPilot project")]


def test_document_deduplication_and_versions(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(files, "UPLOAD_DIR", TEST_UPLOAD_DIR)
    workspace_id = register_and_create_workspace(client)
    url = f"/api/v1/workspaces/{workspace_id}/documents"
    first = client.post(
        url,
        files={"file": ("resume.md", "第一版简历", "text/markdown")},
    )
    assert first.status_code == 201, first.text
    document = first.json()
    assert document["current_version"] == 1
    assert len(document["sha256"]) == 64

    duplicate = client.post(
        url,
        files={"file": ("copy.md", "第一版简历", "text/markdown")},
    )
    assert duplicate.status_code == 409
    assert len(list(TEST_UPLOAD_DIR.iterdir())) == 1

    second = client.post(
        f"{url}/{document['id']}/versions",
        files={"file": ("resume-v2.md", "第二版简历增加项目经验", "text/markdown")},
    )
    assert second.status_code == 201, second.text
    assert second.json()["current_version"] == 2
    assert second.json()["original_name"] == "resume-v2.md"

    versions = client.get(f"{url}/{document['id']}/versions")
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [2, 1]
    assert len({item["sha256"] for item in versions.json()}) == 2
    assert len(list(TEST_UPLOAD_DIR.iterdir())) == 2

    assert client.delete(f"{url}/{document['id']}").status_code == 204
    assert list(TEST_UPLOAD_DIR.iterdir()) == []


def test_index_and_cited_question(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(files, "UPLOAD_DIR", TEST_UPLOAD_DIR)
    qdrant = QdrantClient(":memory:", force_disable_check_same_thread=True)
    monkeypatch.setattr(store, "get_client", lambda: qdrant)

    async def fake_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1023 for _ in texts]

    async def fake_answer(question: str, sources: list[str]) -> str:
        assert question == "这个项目使用什么后端框架？"
        assert "Django" in sources[0]
        assert "FastAPI" not in sources[0]
        return "项目新版使用 Django 作为后端框架。[S1]"

    monkeypatch.setattr(gateway, "embed_texts", fake_embeddings)
    monkeypatch.setattr(gateway, "answer_with_context", fake_answer)
    workspace_id = register_and_create_workspace(client)
    invalid_question = client.post(
        f"/api/v1/workspaces/{workspace_id}/rag/ask", json={"question": "   "}
    )
    assert invalid_question.status_code == 422
    url = f"/api/v1/workspaces/{workspace_id}/documents"
    uploaded = client.post(
        url,
        data={"category": "project"},
        files={"file": ("project.md", "CareerPilot 使用 FastAPI 开发后端。", "text/markdown")},
    ).json()

    indexed = client.post(f"{url}/{uploaded['id']}/index")
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["status"] == "indexed"

    updated = client.post(
        f"{url}/{uploaded['id']}/versions",
        files={
            "file": (
                "project-v2.md",
                "CareerPilot 新版使用 Django 开发后端。",
                "text/markdown",
            )
        },
    )
    assert updated.status_code == 201, updated.text
    assert updated.json()["current_version"] == 2

    indexed = client.post(f"{url}/{uploaded['id']}/index")
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["status"] == "indexed"

    rebuilt = client.post(f"/api/v1/workspaces/{workspace_id}/rag/reindex")
    assert rebuilt.status_code == 200, rebuilt.text
    assert rebuilt.json()[0]["status"] == "indexed"

    answer = client.post(
        f"/api/v1/workspaces/{workspace_id}/rag/ask",
        json={"question": "这个项目使用什么后端框架？"},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["answer"].endswith("[S1]")
    assert answer.json()["citations"][0]["original_name"] == "project-v2.md"

    assert client.delete(f"/api/v1/workspaces/{workspace_id}").status_code == 204
    assert (
        store.search(
            uuid.UUID(workspace_id),
            [1.0] + [0.0] * 1023,
            "FastAPI",
            5,
            "hybrid",
        )
        == []
    )
    qdrant.close()
