"""End-to-end smoke against TestClient + embedded/test Postgres."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "smoke-secret")
os.environ.setdefault("DEBUG", "true")

from embedded_postgres import PostgresServer
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.models import Comment, EmailVerificationToken, Like, Post, User  # noqa: F401
from app.workers.celery_app import celery_app

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True
celery_app.conf.broker_url = "memory://"
celery_app.conf.result_backend = "cache+memory://"


def _sa(uri: str) -> str:
    if uri.startswith("postgresql://"):
        return "postgresql+psycopg2://" + uri.removeprefix("postgresql://")
    return uri


def main() -> None:
    pgdata = Path(".pgdata_test")
    pgdata.mkdir(exist_ok=True)
    server = PostgresServer(pgdata, cleanup_mode=None)
    server.ensure_pgdata_inited()
    server.ensure_postgres_running()
    admin = create_engine(_sa(server.get_uri()), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname='medicalka_smoke'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE medicalka_smoke"))
    admin.dispose()
    port = server.get_uri().rsplit(":", 1)[1].split("/")[0]
    url = f"postgresql+psycopg2://postgres:@127.0.0.1:{port}/medicalka_smoke"
    os.environ["DATABASE_URL"] = url

    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"

    r1 = client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "username": "alice",
            "full_name": "Alice Example",
            "password": "password123",
        },
    )
    assert r1.status_code == 201, r1.text
    vtoken = r1.json()["verification_token"]
    assert client.get(f"/auth/verify-email?token={vtoken}").status_code == 200

    r2 = client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "username": "bob",
            "full_name": "Bob Example",
            "password": "password123",
        },
    )
    assert r2.status_code == 201, r2.text
    bob_token = r2.json()["verification_token"]
    assert client.get(f"/auth/verify-email?token={bob_token}").status_code == 200

    alice = client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    ).json()["access_token"]
    bob = client.post(
        "/auth/login", json={"email": "bob@example.com", "password": "password123"}
    ).json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {alice}"})
    assert me.status_code == 200 and me.json()["username"] == "alice"

    post = client.post(
        "/posts",
        headers={"Authorization": f"Bearer {alice}"},
        json={"title": "Hello world", "content": "i love rust"},
    )
    assert post.status_code == 201, post.text
    post_id = post.json()["id"]

    assert (
        client.post(
            f"/posts/{post_id}/like", headers={"Authorization": f"Bearer {alice}"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/posts/{post_id}/like", headers={"Authorization": f"Bearer {bob}"}
        ).status_code
        == 201
    )

    comment = client.post(
        f"/posts/{post_id}/comments",
        headers={"Authorization": f"Bearer {bob}"},
        json={"content": "nice post"},
    )
    assert comment.status_code == 201, comment.text

    detail = client.get(f"/posts/{post_id}")
    assert detail.status_code == 200
    assert detail.json()["likes_count"] == 1
    assert len(detail.json()["comments"]) == 1

    feed = client.get("/feed?page=1&page_size=20")
    assert feed.status_code == 200, feed.text
    items = feed.json()["items"]
    assert any(u["username"] == "alice" for u in items)
    alice_block = next(u for u in items if u["username"] == "alice")
    assert alice_block["posts"][0]["likes"]

    cleanup = client.post("/admin/cleanup-unverified")
    assert cleanup.status_code == 200, cleanup.text
    assert cleanup.json()["code"] == "task_enqueued"

    posts = client.get("/posts?q=rust&page=1&page_size=10")
    assert posts.status_code == 200
    assert posts.json()["total"] >= 1

    app.dependency_overrides.clear()
    engine.dispose()
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
