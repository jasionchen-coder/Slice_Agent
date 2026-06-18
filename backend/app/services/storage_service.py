import json
import shutil
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.utils.validation_utils import validate_upload_size, validate_video_filename


class StorageService:
    def task_root(self, task_id: str) -> Path:
        return settings.storage_root / "live-slicing" / "tasks" / task_id

    def original_path(self, task_id: str, filename: str) -> Path:
        suffix = Path(filename).suffix.lower()
        return self.task_root(task_id) / "original" / f"source{suffix}"

    def audio_path(self, task_id: str) -> Path:
        return self.task_root(task_id) / "audio" / "audio.wav"

    def audio_chunks_dir(self, task_id: str) -> Path:
        return self.task_root(task_id) / "audio" / "chunks"

    def transcript_path(self, task_id: str, name: str) -> Path:
        return self.task_root(task_id) / "transcript" / name

    def llm_path(self, task_id: str, name: str) -> Path:
        return self.task_root(task_id) / "llm" / name

    def clip_path(self, task_id: str, clip_id: str) -> Path:
        return self.task_root(task_id) / "clips" / f"{clip_id}.mp4"

    def public_url(self, path: Path) -> str:
        relative = path.relative_to(settings.storage_root).as_posix()
        return f"/media/{relative}"

    async def save_upload(self, task_id: str, upload: UploadFile) -> Path:
        validate_video_filename(upload.filename or "")
        output_path = self.original_path(task_id, upload.filename or "source.mp4")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with output_path.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                validate_upload_size(size)
                target.write(chunk)
        return output_path

    def write_json(self, path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def remove_task(self, task_id: str) -> None:
        root = self.task_root(task_id)
        if root.exists():
            shutil.rmtree(root)
