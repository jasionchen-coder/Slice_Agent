import json
import subprocess
from pathlib import Path

from app.core.config import settings


class FFmpegError(RuntimeError):
    pass


class FFmpegClient:
    def probe(self, video_path: Path) -> dict:
        result = self._run(
            [
                settings.ffprobe_path,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ]
        )
        return json.loads(result.stdout)

    def extract_audio(self, video_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                settings.ffmpeg_path,
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(output_path),
            ]
        )

    def cut_video(self, video_path: Path, output_path: Path, start_time: float, end_time: float) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                settings.ffmpeg_path,
                "-y",
                "-ss",
                f"{start_time:.3f}",
                "-to",
                f"{end_time:.3f}",
                "-i",
                str(video_path),
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                str(output_path),
            ]
        )

    def cut_audio(self, audio_path: Path, output_path: Path, start_time: float, duration: float) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                settings.ffmpeg_path,
                "-y",
                "-ss",
                f"{start_time:.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(audio_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(output_path),
            ]
        )

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "FFmpeg command failed"
            raise FFmpegError(detail)
        return result
