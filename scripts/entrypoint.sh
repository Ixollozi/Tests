#!/bin/sh
set -e

role="${1:-api}"

wait_for_db() {
  echo "Waiting for database..."
  python - <<'PY'
import os, time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
engine = create_engine(url, pool_pre_ping=True)
for i in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database is ready")
        break
    except Exception as exc:
        print(f"DB not ready ({i+1}/60): {exc}")
        time.sleep(1)
else:
    raise SystemExit("Database did not become ready in time")
PY
}

case "$role" in
  api)
    wait_for_db
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    wait_for_db
    exec celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
    ;;
  beat)
    wait_for_db
    exec celery -A app.workers.celery_app.celery_app beat --loglevel=INFO
    ;;
  test)
    export DATABASE_URL="${TEST_DATABASE_URL}"
    wait_for_db
    alembic upgrade head
    exec pytest -q
    ;;
  *)
    exec "$@"
    ;;
esac
