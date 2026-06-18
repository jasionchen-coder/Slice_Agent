from pathlib import Path

from app.integrations.ffmpeg_client import FFmpegClient, FFmpegError
from app.models.enums import ClipStatus
from app.repositories.clip_repository import ClipRepository
from app.services.storage_service import StorageService
from app.utils.id_utils import new_entity_id


class ClipValidationError(ValueError):
    pass


class VideoCutError(RuntimeError):
    pass


class ClipService:
    def __init__(
        self,
        clip_repository: ClipRepository | None = None,
        storage_service: StorageService | None = None,
        ffmpeg: FFmpegClient | None = None,
    ) -> None:
        self.clip_repository = clip_repository or ClipRepository()
        self.storage_service = storage_service or StorageService()
        self.ffmpeg = ffmpeg or FFmpegClient()

    def validate_candidate(
        self,
        candidate: dict,
        *,
        min_duration: int,
        max_duration: int,
        video_duration: float,
        risk_filter_enabled: bool,
    ) -> dict:
        start = float(candidate.get("start_time", -1))
        end = float(candidate.get("end_time", -1))
        duration = end - start
        if start < 0:
            raise ClipValidationError("start_time must be greater than or equal to 0")
        if end > video_duration:
            raise ClipValidationError("end_time exceeds video duration")
        if start >= end:
            raise ClipValidationError("start_time must be less than end_time")
        if duration < min_duration or duration > max_duration:
            raise ClipValidationError("clip duration is outside configured range")
        if not candidate.get("title"):
            raise ClipValidationError("title is required")
        if not candidate.get("summary"):
            raise ClipValidationError("summary is required")
        score = int(candidate.get("score", 0))
        if score < 0 or score > 100:
            raise ClipValidationError("score must be between 0 and 100")
        if risk_filter_enabled and candidate.get("risk_level") == "high":
            raise ClipValidationError("high risk clips are filtered")
        return {
            **candidate,
            "start_time": start,
            "end_time": end,
            "duration": duration,
            "score": score,
        }

    def save_clip_plan(
        self,
        task_id: str,
        candidates: list[dict],
        *,
        min_duration: int,
        max_duration: int,
        max_count: int,
        video_duration: float,
        risk_filter_enabled: bool,
    ) -> list[dict]:
        saved: list[dict] = []
        for candidate in candidates:
            if len(saved) >= max_count:
                break
            try:
                valid = self.validate_candidate(
                    candidate,
                    min_duration=min_duration,
                    max_duration=max_duration,
                    video_duration=video_duration,
                    risk_filter_enabled=risk_filter_enabled,
                )
            except ClipValidationError:
                continue
            valid["clip_id"] = new_entity_id("clip", len(saved))
            valid["task_id"] = task_id
            valid["status"] = ClipStatus.PENDING
            valid["clip_path"] = None
            valid["clip_url"] = None
            valid["error_message"] = None
            saved.append(self.clip_repository.create(valid))
        return saved

    def cut_clip(self, task: dict, clip: dict) -> dict:
        clip_id = clip["clip_id"]
        video_path = Path(task["original_video_path"])
        output_path = self.storage_service.clip_path(task["task_id"], clip_id)
        self.clip_repository.update(clip_id, {"status": ClipStatus.CUTTING_VIDEO, "error_message": None})
        try:
            self.ffmpeg.cut_video(video_path, output_path, clip["start_time"], clip["end_time"])
        except FFmpegError as exc:
            self.clip_repository.update(
                clip_id,
                {"status": ClipStatus.FAILED, "error_message": str(exc)},
            )
            raise VideoCutError(str(exc)) from exc
        return self.clip_repository.update(
            clip_id,
            {
                "status": ClipStatus.SUCCESS,
                "clip_path": str(output_path),
                "clip_url": self.storage_service.public_url(output_path),
                "error_message": None,
            },
        )

    def regenerate_clip(self, task: dict, clip: dict) -> dict:
        duration = float(clip["end_time"]) - float(clip["start_time"])
        if duration <= 0:
            raise ClipValidationError("clip duration must be greater than 0")
        return self.cut_clip(task, clip)

