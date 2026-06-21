from pathlib import Path

from app.core.config import settings


class UploadValidationError(ValueError):
    pass


def validate_video_filename(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_video_extensions:
        allowed = ", ".join(sorted(settings.allowed_video_extensions))
        raise UploadValidationError(f"Unsupported video format. Allowed: {allowed}")


def validate_audio_filename(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    allowed_extensions = {".mp3", ".wav", ".m4a", ".aac"}
    if suffix not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise UploadValidationError(f"Unsupported audio format. Allowed: {allowed}")


def validate_upload_size(size: int) -> None:
    if size > settings.max_upload_bytes:
        raise UploadValidationError(
            f"File is too large. Max upload size is {settings.max_upload_mb} MB"
        )
