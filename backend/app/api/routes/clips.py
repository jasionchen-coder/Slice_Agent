from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.models.enums import ClipStatus
from app.repositories.clip_repository import ClipRepository
from app.schemas.clip_schema import ClipMutationResponse, ClipResponse, ClipUpdateRequest
from app.services.queue_service import QueueService
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
    if time_changed:
        start = float(update_data.get("start_time", clip["start_time"]))
        end = float(update_data.get("end_time", clip["end_time"]))
        if start >= end:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_time must be less than end_time",
            )
        update_data["duration"] = end - start
        update_data["status"] = ClipStatus.PENDING
        update_data["error_message"] = None

    updated = repository.update(clip_id, update_data)
    if time_changed:
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
    ClipRepository().update(clip_id, {"status": ClipStatus.PENDING, "error_message": None})
    QueueService().submit(regenerate_clip_task, clip_id)
    return ClipMutationResponse(clip_id=clip_id, status=ClipStatus.PENDING, message="切片重新生成中")


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

