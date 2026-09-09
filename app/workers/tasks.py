import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.auth import cleanup_unverified_users
from app.workers.celery_app import celery_app


def _make_session():
    url = os.environ.get("DATABASE_URL") or settings.database_url
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal(), engine


@celery_app.task(name="app.workers.tasks.cleanup_unverified_users_task")
def cleanup_unverified_users_task(older_than_hours: int | None = None) -> dict:
    db, engine = _make_session()
    try:
        deleted = cleanup_unverified_users(
            db, older_than_hours or settings.unverified_user_ttl_hours
        )
        return {"deleted": deleted}
    finally:
        db.close()
        engine.dispose()
