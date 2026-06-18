from app.models.enums import ClipStatus
from app.repositories.clip_repository import ClipRepository
from app.services.clip_service import ClipService, ClipValidationError, VideoCutError
from app.services.task_service import TaskNotFoundError, TaskService
from app.workers.celery_app import celery_app


@celery_app.task(name="regenerate_clip_task")
def regenerate_clip_task(clip_id: str) -> None:
    clip_repository = ClipRepository()
    clip = clip_repository.get(clip_id)
    if clip is None:
        return
    try:
        task = TaskService().get_required(clip["task_id"])
        ClipService(clip_repository=clip_repository).regenerate_clip(task, clip)
    except (TaskNotFoundError, ClipValidationError, VideoCutError) as exc:
        clip_repository.update(
            clip_id,
            {"status": ClipStatus.FAILED, "error_message": str(exc)},
        )
