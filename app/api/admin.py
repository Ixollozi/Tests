from fastapi import APIRouter

from app.schemas import TaskEnqueued
from app.workers.tasks import cleanup_unverified_users_task

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/cleanup-unverified", response_model=TaskEnqueued)
def cleanup_unverified() -> TaskEnqueued:
    result = cleanup_unverified_users_task.delay()
    return TaskEnqueued(
        detail="Cleanup task enqueued",
        task_id=result.id,
        code="task_enqueued",
    )
