from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.core.config import settings
from app.models.enums import TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.storage_service import StorageService
from app.services.video_service import VideoService
from app.utils.id_utils import new_task_id


class TaskNotFoundError(LookupError):
    pass


class TaskService:
    def __init__(
        self,
        task_repository: TaskRepository | None = None,
        storage_service: StorageService | None = None,
        video_service: VideoService | None = None,
    ) -> None:
        self.task_repository = task_repository or TaskRepository()
        self.storage_service = storage_service or StorageService()
        self.video_service = video_service or VideoService()

    async def create_from_upload(
        self,
        upload: UploadFile,
        *,
        content_type: str,
        min_clip_duration: int,
        max_clip_duration: int,
        max_clip_count: int,
        risk_filter_enabled: bool,
    ) -> dict[str, Any]:
        task_id = new_task_id()
        original_path = await self.storage_service.save_upload(task_id, upload)
        video_info = self.video_service.get_video_info(original_path)
        return self.task_repository.create(
            {
                "task_id": task_id,
                "video_name": upload.filename or Path(original_path).name,
                "original_video_path": str(original_path),
                "content_type": content_type,
                "min_clip_duration": min_clip_duration,
                "max_clip_duration": max_clip_duration,
                "max_clip_count": max_clip_count,
                "risk_filter_enabled": risk_filter_enabled,
                "status": TaskStatus.UPLOADED,
                "progress": 5,
                "current_stage": "任务创建完成",
                **video_info,
            }
        )

    def get_required(self, task_id: str) -> dict[str, Any]:
        task = self.task_repository.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def list_tasks(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.task_repository.list(limit=limit, offset=offset)

    def cancel(self, task_id: str) -> dict[str, Any]:
        self.get_required(task_id)
        return self.task_repository.update_status(
            task_id,
            status=TaskStatus.CANCELLED,
            progress=0,
            current_stage="任务已取消",
        )

    def mark_retrying(self, task_id: str) -> dict[str, Any]:
        self.get_required(task_id)
        return self.task_repository.update_status(
            task_id,
            status=TaskStatus.PENDING,
            progress=0,
            current_stage="任务已重新进入队列",
            failed_stage=None,
            error_message=None,
        )

    def should_auto_process(self) -> bool:
        return settings.auto_process
