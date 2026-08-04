from fastapi.testclient import TestClient


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    assert "httponly" in response.headers["set-cookie"].lower()


def test_authentication_is_required(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/workspaces").status_code == 401


def test_register_login_and_duplicate_email(client: TestClient) -> None:
    register(client, "user@example.com")
    assert client.get("/api/v1/auth/me").json()["email"] == "user@example.com"
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "correct-horse-battery"},
    )
    assert duplicate.status_code == 409


def test_workspace_crud_and_user_isolation(client: TestClient) -> None:
    register(client, "first@example.com")
    created = client.post(
        "/api/v1/workspaces",
        json={"name": "Java 求职", "target_role": "Java 后端"},
    )
    assert created.status_code == 201
    workspace_id = created.json()["id"]

    renamed = client.patch(
        "/api/v1/workspaces/" + workspace_id,
        json={"name": "AI 应用求职"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "AI 应用求职"

    client.post("/api/v1/auth/logout")
    register(client, "second@example.com")
    assert client.get("/api/v1/workspaces").json() == []
    assert (
        client.patch("/api/v1/workspaces/" + workspace_id, json={"name": "越权"}).status_code
        == 404
    )

    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login",
        json={"email": "first@example.com", "password": "correct-horse-battery"},
    )
    assert client.delete("/api/v1/workspaces/" + workspace_id).status_code == 204
    assert client.get("/api/v1/workspaces").json() == []
