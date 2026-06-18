from pathlib import Path

import httpx

from app.core.config import settings
from app.schemas.transcript_schema import TranscriptSegment


class ASRError(RuntimeError):
    pass


class ASRClient:
    def transcribe(self, audio_path: Path, *, duration: float | None = None) -> list[TranscriptSegment]:
        raise NotImplementedError


class MockASRClient(ASRClient):
    def transcribe(self, audio_path: Path, *, duration: float | None = None) -> list[TranscriptSegment]:
        if not audio_path.exists():
            raise ASRError("Audio file does not exist")
        total = max(float(duration or 180), 30.0)
        segment_length = 30.0
        segments: list[TranscriptSegment] = []
        start = 0.0
        index = 1
        while start < total:
            end = min(start + segment_length, total)
            segments.append(
                TranscriptSegment(
                    start_time=start,
                    end_time=end,
                    speaker="speaker_1",
                    text=f"模拟转写片段 {index}：这里是直播内容摘要，可替换为真实 ASR 结果。",
                )
            )
            start = end
            index += 1
        return segments


class GroqASRClient(ASRClient):
    def transcribe(self, audio_path: Path, *, duration: float | None = None) -> list[TranscriptSegment]:
        if not settings.groq_api_key:
            raise ASRError("APP_GROQ_API_KEY is required for Groq ASR")
        if not audio_path.exists():
            raise ASRError("Audio file does not exist")

        url = f"{settings.groq_base_url.rstrip('/')}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        data = {
            "model": settings.groq_asr_model,
            "language": settings.default_language,
            "response_format": "verbose_json",
        }
        try:
            with audio_path.open("rb") as audio_file:
                files = {"file": (audio_path.name, audio_file, "audio/wav")}
                response = httpx.post(
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=settings.request_timeout_seconds,
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _safe_error_detail(exc.response)
            raise ASRError(f"Groq ASR request failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise ASRError(f"Groq ASR request failed: {exc}") from exc

        payload = response.json()
        raw_segments = payload.get("segments") or []
        segments: list[TranscriptSegment] = []
        for item in raw_segments:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            start = float(item.get("start") or item.get("start_time") or 0)
            end = float(item.get("end") or item.get("end_time") or start)
            if end <= start:
                end = start + 0.01
            segments.append(
                TranscriptSegment(
                    start_time=start,
                    end_time=end,
                    speaker=None,
                    text=text,
                )
            )

        if segments:
            return segments

        text = str(payload.get("text") or "").strip()
        if text:
            return [
                TranscriptSegment(
                    start_time=0,
                    end_time=max(float(duration or 0), 0.01),
                    speaker=None,
                    text=text,
                )
            ]
        return []


def _safe_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]
    return str(payload.get("error") or payload)[:500]


def get_asr_client() -> ASRClient:
    if settings.asr_provider == "mock":
        return MockASRClient()
    if settings.asr_provider == "groq":
        return GroqASRClient()
    raise ASRError(f"Unsupported ASR provider: {settings.asr_provider}")
