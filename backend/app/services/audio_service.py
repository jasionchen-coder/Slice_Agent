from pathlib import Path
from dataclasses import dataclass

from app.integrations.ffmpeg_client import FFmpegClient, FFmpegError


class AudioExtractError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioChunk:
    path: Path
    start_time: float
    end_time: float

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class AudioService:
    def __init__(self, ffmpeg: FFmpegClient | None = None) -> None:
        self.ffmpeg = ffmpeg or FFmpegClient()

    def extract_audio(self, video_path: Path, output_path: Path) -> Path:
        try:
            self.ffmpeg.extract_audio(video_path, output_path)
        except FFmpegError as exc:
            raise AudioExtractError(str(exc)) from exc
        return output_path

    def split_audio(
        self,
        audio_path: Path,
        chunks_dir: Path,
        *,
        total_duration: float,
        chunk_seconds: int,
        overlap_seconds: int,
    ) -> list[AudioChunk]:
        if total_duration <= 0:
            raise AudioExtractError("Audio duration must be greater than 0")

        chunk_seconds = max(1, chunk_seconds)
        overlap_seconds = max(0, min(overlap_seconds, chunk_seconds - 1))
        chunks_dir.mkdir(parents=True, exist_ok=True)

        if total_duration <= chunk_seconds:
            output_path = chunks_dir / "audio_001.wav"
            try:
                self.ffmpeg.cut_audio(audio_path, output_path, 0, total_duration)
            except FFmpegError as exc:
                raise AudioExtractError(str(exc)) from exc
            return [AudioChunk(path=output_path, start_time=0, end_time=total_duration)]

        chunks: list[AudioChunk] = []
        start = 0.0
        step = chunk_seconds - overlap_seconds
        index = 1
        while start < total_duration:
            end = min(start + chunk_seconds, total_duration)
            output_path = chunks_dir / f"audio_{index:03d}.wav"
            try:
                self.ffmpeg.cut_audio(audio_path, output_path, start, end - start)
            except FFmpegError as exc:
                raise AudioExtractError(str(exc)) from exc
            chunks.append(AudioChunk(path=output_path, start_time=start, end_time=end))
            if end >= total_duration:
                break
            start += step
            index += 1
        return chunks
