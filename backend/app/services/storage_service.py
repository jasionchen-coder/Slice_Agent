import json
import shutil
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.utils.validation_utils import validate_audio_filename, validate_upload_size, validate_video_filename


class StorageService:
    def task_root(self, task_id: str) -> Path:
        return settings.storage_root / "live-slicing" / "tasks" / task_id

    def original_path(self, task_id: str, filename: str) -> Path:
        suffix = Path(filename).suffix.lower()
        return self.task_root(task_id) / "original" / f"source{suffix}"

    def audio_path(self, task_id: str) -> Path:
        return self.task_root(task_id) / "audio" / "audio.wav"

    def uploaded_audio_path(self, task_id: str, filename: str) -> Path:
        suffix = Path(filename).suffix.lower() or ".mp3"
        return self.task_root(task_id) / "audio" / f"source{suffix}"

    def audio_chunks_dir(self, task_id: str) -> Path:
        return self.task_root(task_id) / "audio" / "chunks"

    def audio_manifest_path(self, task_id: str) -> Path:
        return self.task_root(task_id) / "audio" / "manifest.json"

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

    async def save_audio_upload(self, task_id: str, upload: UploadFile) -> Path:
        validate_audio_filename(upload.filename or "")
        output_path = self.uploaded_audio_path(task_id, upload.filename or "source.mp3")
        await self._save_upload_file(upload, output_path)
        return output_path

    async def save_audio_chunks(
        self,
        task_id: str,
        uploads: list[UploadFile],
        manifest: list[dict],
    ) -> list[dict]:
        if len(uploads) != len(manifest):
            raise ValueError("audio_files count must match audio_manifest count")

        chunks_dir = self.audio_chunks_dir(task_id)
        chunks_dir.mkdir(parents=True, exist_ok=True)
        saved_manifest: list[dict] = []

        for index, upload in enumerate(uploads):
            validate_audio_filename(upload.filename or "")
            suffix = Path(upload.filename or "audio.mp3").suffix.lower() or ".mp3"
            output_path = chunks_dir / f"audio_{index + 1:03d}{suffix}"
            await self._save_upload_file(upload, output_path)

            item = manifest[index].copy()
            item["path"] = str(output_path)
            item["chunk_index"] = int(item.get("chunk_index", index))
            item["start_time"] = float(item["start_time"])
            item["end_time"] = float(item["end_time"])
            saved_manifest.append(item)

        self.write_json(self.audio_manifest_path(task_id), {"chunks": saved_manifest})
        return saved_manifest

    def load_audio_manifest(self, task_id: str) -> list[dict]:
        path = self.audio_manifest_path(task_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        chunks = payload.get("chunks") or []
        return chunks if isinstance(chunks, list) else []

    def write_json(self, path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def remove_task(self, task_id: str) -> None:
        root = self.task_root(task_id)
        if root.exists():
            shutil.rmtree(root)

    async def _save_upload_file(self, upload: UploadFile, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with output_path.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                validate_upload_size(size)
                target.write(chunk)
