from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.models import Comment, EmailVerificationToken, Like, Post, User  # noqa: F401
from app.workers.celery_app import celery_app

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True
celery_app.conf.broker_url = "memory://"
celery_app.conf.result_backend = "cache+memory://"


def _sqlalchemy_url(uri: str) -> str:
    if uri.startswith("postgresql://"):
        return "postgresql+psycopg2://" + uri.removeprefix("postgresql://")
    return uri


@pytest.fixture(scope="session")
def pg_url() -> Generator[str, None, None]:
    """Prefer TEST_DATABASE_URL; otherwise boot embedded Postgres (no Docker needed)."""
    import os

    external = os.getenv("TEST_DATABASE_URL")
    if external:
        os.environ["DATABASE_URL"] = external
        yield external
        return

    from embedded_postgres import PostgresServer

    pgdata = Path(__file__).resolve().parents[1] / ".pgdata_test"
    pgdata.mkdir(exist_ok=True)
    server = PostgresServer(pgdata, cleanup_mode=None)
    server.ensure_pgdata_inited()
    server.ensure_postgres_running()
    admin_uri = server.get_uri()
    admin_engine = create_engine(_sqlalchemy_url(admin_uri), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'medicalka_test'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE medicalka_test"))
    admin_engine.dispose()

    port = admin_uri.rsplit(":", 1)[1].split("/")[0]
    url = f"postgresql+psycopg2://postgres:@127.0.0.1:{port}/medicalka_test"
    os.environ["DATABASE_URL"] = url
    os.environ["TEST_DATABASE_URL"] = url
    yield url


@pytest.fixture(scope="session")
def engine(pg_url: str) -> Generator[Engine, None, None]:
    eng = create_engine(pg_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine: Engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans) -> None:  # noqa: ANN001
        if trans.nested and not trans._parent.nested:  # noqa: SLF001
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
