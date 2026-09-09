from fastapi.testclient import TestClient


def _register_and_verify(client: TestClient, suffix: str) -> str:
    reg = client.post(
        "/auth/register",
        json={
            "email": f"{suffix}@example.com",
            "username": suffix,
            "full_name": f"Name {suffix.replace('_', ' ').title()}",
            "password": "password123",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["verification_token"]
    verified = client.get(f"/auth/verify-email?token={token}")
    assert verified.status_code == 200
    assert verified.json()["is_verified"] is True

    login = client.post(
        "/auth/login",
        json={"email": f"{suffix}@example.com", "password": "password123"},
    )
    return login.json()["access_token"]


def test_unverified_cannot_create_post(client: TestClient) -> None:
    reg = client.post(
        "/auth/register",
        json={
            "email": "unverified@example.com",
            "username": "unverified",
            "full_name": "Un Verified",
            "password": "password123",
        },
    )
    login = client.post(
        "/auth/login",
        json={"email": "unverified@example.com", "password": "password123"},
    )
    token = login.json()["access_token"]
    response = client.post(
        "/posts",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Hello world", "content": "content"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"
    assert reg.status_code == 201


def test_cannot_like_own_post_and_cannot_like_twice(client: TestClient) -> None:
    author_token = _register_and_verify(client, "author_one")
    other_token = _register_and_verify(client, "liker_one")

    created = client.post(
        "/posts",
        headers={"Authorization": f"Bearer {author_token}"},
        json={"title": "Hello world", "content": "my first post"},
    )
    assert created.status_code == 201
    post_id = created.json()["id"]

    own_like = client.post(
        f"/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {author_token}"},
    )
    assert own_like.status_code == 400
    assert own_like.json()["code"] == "cannot_like_own_post"

    first = client.post(
        f"/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert second.status_code == 400
    assert second.json()["code"] == "already_liked"
