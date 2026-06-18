from pathlib import Path

from app.integrations.ffmpeg_client import FFmpegClient, FFmpegError


class VideoParseError(RuntimeError):
    pass


class VideoService:
    def __init__(self, ffmpeg: FFmpegClient | None = None) -> None:
        self.ffmpeg = ffmpeg or FFmpegClient()

    def get_video_info(self, video_path: Path) -> dict:
        try:
            probe = self.ffmpeg.probe(video_path)
        except FFmpegError as exc:
            raise VideoParseError(str(exc)) from exc

        video_stream = next(
            (stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"),
            None,
        )
        audio_stream = next(
            (stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"),
            None,
        )
        if video_stream is None:
            raise VideoParseError("No video stream found")
        if audio_stream is None:
            raise VideoParseError("No audio stream found")

        fmt = probe.get("format", {})
        duration = float(fmt.get("duration") or video_stream.get("duration") or 0)
        width = video_stream.get("width")
        height = video_stream.get("height")
        return {
            "video_duration": duration,
            "video_size": int(fmt.get("size") or video_path.stat().st_size),
            "video_format": video_path.suffix.lower().lstrip("."),
            "video_resolution": f"{width}x{height}" if width and height else None,
        }

