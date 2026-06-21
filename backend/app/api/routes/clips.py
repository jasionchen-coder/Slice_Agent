from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.models.enums import ClipStatus
from app.repositories.clip_repository import ClipRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.clip_schema import ClipMutationResponse, ClipResponse, ClipUpdateRequest
from app.services.queue_service import QueueService
from app.services.storage_service import StorageService
from app.utils.validation_utils import validate_upload_size
from app.workers.clip_tasks import regenerate_clip_task

router = APIRouter(tags=["clips"])


@router.get("/clips/{clip_id}", response_model=ClipResponse)
def get_clip(clip_id: str) -> ClipResponse:
    clip = ClipRepository().get(clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return ClipResponse(**clip)


@router.patch("/clips/{clip_id}", response_model=ClipMutationResponse)
def update_clip(clip_id: str, payload: ClipUpdateRequest) -> ClipMutationResponse:
    repository = ClipRepository()
    clip = repository.get(clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return ClipMutationResponse(clip_id=clip_id, status=clip["status"], message="没有需要更新的字段")

    time_changed = "start_time" in update_data or "end_time" in update_data
    frontend_audio = _is_frontend_audio_clip(clip)
    if time_changed:
        start = float(update_data.get("start_time", clip["start_time"]))
        end = float(update_data.get("end_time", clip["end_time"]))
        if start >= end:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_time must be less than end_time",
            )
        update_data["duration"] = end - start
        update_data["status"] = ClipStatus.READY_FOR_LOCAL_CUT if frontend_audio else ClipStatus.PENDING
        update_data["error_message"] = None

    updated = repository.update(clip_id, update_data)
    if time_changed and not frontend_audio:
        QueueService().submit(regenerate_clip_task, clip_id)

    return ClipMutationResponse(
        clip_id=clip_id,
        status=updated["status"] if updated else None,
        message="切片信息更新成功",
    )


@router.post("/clips/{clip_id}/regenerate", response_model=ClipMutationResponse)
def regenerate_clip(clip_id: str) -> ClipMutationResponse:
    clip = ClipRepository().get(clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    if _is_frontend_audio_clip(clip):
        ClipRepository().update(clip_id, {"status": ClipStatus.READY_FOR_LOCAL_CUT, "error_message": None})
        return ClipMutationResponse(
            clip_id=clip_id,
            status=ClipStatus.READY_FOR_LOCAL_CUT,
            message="已标记为等待前端本地切片",
        )
    ClipRepository().update(clip_id, {"status": ClipStatus.PENDING, "error_message": None})
    QueueService().submit(regenerate_clip_task, clip_id)
    return ClipMutationResponse(clip_id=clip_id, status=ClipStatus.PENDING, message="切片重新生成中")


@router.post("/clips/{clip_id}/upload", response_model=ClipMutationResponse)
async def upload_clip_file(clip_id: str, file: UploadFile = File(...)) -> ClipMutationResponse:
    repository = ClipRepository()
    clip = repository.get(clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    filename = file.filename or f"{clip_id}.mp4"
    if not filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only mp4 clips are supported.")

    storage = StorageService()
    output_path = storage.clip_path(clip["task_id"], clip_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with output_path.open("wb") as target:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            validate_upload_size(size)
            target.write(chunk)

    updated = repository.update(
        clip_id,
        {
            "status": ClipStatus.SUCCESS,
            "clip_path": str(output_path),
            "clip_url": storage.public_url(output_path),
            "error_message": None,
        },
    )
    return ClipMutationResponse(
        clip_id=clip_id,
        status=updated["status"] if updated else ClipStatus.SUCCESS,
        message="切片文件已保存",
    )


@router.get("/clips/{clip_id}/download")
def download_clip(clip_id: str) -> FileResponse:
    clip = ClipRepository().get(clip_id)
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    clip_path = clip.get("clip_path")
    if not clip_path or not Path(clip_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip file not found")
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=f"{clip_id}.mp4",
    )


def _is_frontend_audio_clip(clip: dict) -> bool:
    task = TaskRepository().get(clip["task_id"])
    return bool(task and task.get("video_url") == "frontend-audio")
