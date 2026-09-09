from fastapi.testclient import TestClient


def _register(client: TestClient, suffix: str = "1") -> dict:
    payload = {
        "email": f"user{suffix}@example.com",
        "username": f"user_{suffix}",
        "full_name": f"User {suffix}",
        "password": "password123",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_register_success(client: TestClient) -> None:
    data = _register(client, "ok")
    assert data["user"]["email"] == "userok@example.com"
    assert data["user"]["is_verified"] is False
    assert data["user"].get("password_hash") is None
    assert data["verification_token"]


def test_register_duplicate_email(client: TestClient) -> None:
    _register(client, "dup")
    response = client.post(
        "/auth/register",
        json={
            "email": "userdup@example.com",
            "username": "other_user",
            "full_name": "Other User",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "email_taken"


def test_register_duplicate_username(client: TestClient) -> None:
    _register(client, "name")
    response = client.post(
        "/auth/register",
        json={
            "email": "unique@example.com",
            "username": "user_name",
            "full_name": "Other User",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "username_taken"


def test_login_success(client: TestClient) -> None:
    _register(client, "login")
    response = client.post(
        "/auth/login",
        json={"email": "userlogin@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_me_with_valid_and_invalid_token(client: TestClient) -> None:
    _register(client, "me")
    login = client.post(
        "/auth/login",
        json={"email": "userme@example.com", "password": "password123"},
    )
    token = login.json()["access_token"]

    ok = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["username"] == "user_me"

    bad = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_token"

    missing = client.get("/auth/me")
    assert missing.status_code == 401
