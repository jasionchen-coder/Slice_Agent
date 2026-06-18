from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.repositories.clip_repository import ClipRepository
from app.repositories.task_log_repository import TaskLogRepository
from app.schemas.clip_schema import ClipListResponse
from app.schemas.task_schema import TaskCreateResponse, TaskListResponse, TaskResponse
from app.services.queue_service import QueueService
from app.services.task_service import TaskNotFoundError, TaskService
from app.utils.validation_utils import UploadValidationError
from app.workers.video_pipeline import process_video_task

router = APIRouter(tags=["tasks"])


def _task_response(task: dict) -> TaskResponse:
    task = task.copy()
    task["risk_filter_enabled"] = bool(task["risk_filter_enabled"])
    return TaskResponse(**task)


@router.post("/tasks", response_model=TaskCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    file: UploadFile | None = File(default=None),
    video_url: str | None = Form(default=None),
    content_type: str = Form(...),
    min_clip_duration: int = Form(30),
    max_clip_duration: int = Form(180),
    max_clip_count: int = Form(10),
    risk_filter_enabled: bool = Form(True),
) -> TaskCreateResponse:
    if file is None:
        if video_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Video URL import is planned for P1. Please upload a local video file.",
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either file or video_url is required.",
        )
    if min_clip_duration >= max_clip_duration:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_clip_duration must be less than max_clip_duration.",
        )

    service = TaskService()
    try:
        task = await service.create_from_upload(
            file,
            content_type=content_type,
            min_clip_duration=min_clip_duration,
            max_clip_duration=max_clip_duration,
            max_clip_count=max_clip_count,
            risk_filter_enabled=risk_filter_enabled,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if service.should_auto_process():
        QueueService().submit(process_video_task, task["task_id"])

    return TaskCreateResponse(
        task_id=task["task_id"],
        status=task["status"],
        message="任务创建成功",
    )


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(limit: int = 50, offset: int = 0) -> TaskListResponse:
    tasks = TaskService().list_tasks(limit=limit, offset=offset)
    return TaskListResponse(tasks=[_task_response(task) for task in tasks])


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> TaskResponse:
    try:
        task = TaskService().get_required(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    return _task_response(task)


@router.get("/tasks/{task_id}/clips", response_model=ClipListResponse)
def list_task_clips(task_id: str) -> ClipListResponse:
    try:
        TaskService().get_required(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    clips = ClipRepository().list_by_task(task_id)
    return ClipListResponse(task_id=task_id, clips=clips)


@router.get("/tasks/{task_id}/logs")
def list_task_logs(task_id: str) -> dict:
    try:
        TaskService().get_required(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    return {"task_id": task_id, "logs": TaskLogRepository().list_by_task(task_id)}


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: str) -> TaskResponse:
    try:
        task = TaskService().cancel(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    return _task_response(task)


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
def retry_task(task_id: str) -> TaskResponse:
    service = TaskService()
    try:
        task = service.mark_retrying(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    QueueService().submit(process_video_task, task_id)
    return _task_response(task)
