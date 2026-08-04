import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app import document_files

TEST_UPLOAD_DIR = Path(__file__).parent / "_uploads"


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
    monkeypatch.setattr(document_files, "UPLOAD_DIR", TEST_UPLOAD_DIR)
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
    assert document["status"] == "ready"
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
    monkeypatch.setattr(document_files, "UPLOAD_DIR", TEST_UPLOAD_DIR)
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

    sections = document_files.parse_document(".docx", content.getvalue())
    assert document_files.make_chunks(sections) == [(None, "CareerPilot project")]
