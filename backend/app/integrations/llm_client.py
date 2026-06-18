import json

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.llm_schema import ClipPlanResponse, TopicAnalysisResponse
from app.schemas.transcript_schema import TranscriptSegment
from app.utils.time_utils import clamp_time


class LLMError(RuntimeError):
    pass


class LLMClient:
    def analyze_topics(self, segments: list[TranscriptSegment], *, content_type: str) -> list[dict]:
        raise NotImplementedError

    def generate_clips(
        self,
        topics: list[dict],
        *,
        min_duration: int,
        max_duration: int,
        max_count: int,
        risk_filter_enabled: bool,
        video_duration: float,
    ) -> list[dict]:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def analyze_topics(self, segments: list[TranscriptSegment], *, content_type: str) -> list[dict]:
        topics: list[dict] = []
        for index, segment in enumerate(segments):
            topics.append(
                {
                    "topic_id": f"topic_{index + 1:03d}",
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "topic_title": f"直播高价值片段 {index + 1}",
                    "summary": segment.text,
                    "content_type": content_type or "other",
                    "suitable_for_clip": True,
                    "risk_level": "low",
                    "score": max(60, 90 - index * 3),
                    "raw_llm_output": {"provider": "mock"},
                }
            )
        return _validate_topics({"topics": topics}, provider="mock")

    def generate_clips(
        self,
        topics: list[dict],
        *,
        min_duration: int,
        max_duration: int,
        max_count: int,
        risk_filter_enabled: bool,
        video_duration: float,
    ) -> list[dict]:
        clips: list[dict] = []
        for index, topic in enumerate(topics):
            if len(clips) >= max_count:
                break
            if risk_filter_enabled and topic.get("risk_level") == "high":
                continue
            start = clamp_time(float(topic["start_time"]) - 2.0, 0.0, video_duration)
            desired_end = max(float(topic["end_time"]) + 2.0, start + min_duration)
            end = clamp_time(desired_end, start, min(start + max_duration, video_duration))
            clips.append(
                {
                    "clip_id": f"clip_{index + 1:03d}",
                    "start_time": start,
                    "end_time": end,
                    "title": topic.get("topic_title") or f"直播切片 {index + 1}",
                    "summary": topic.get("summary") or "系统生成的候选切片。",
                    "reason": "该片段来自 mock LLM，真实环境会由大模型给出推荐理由。",
                    "content_type": topic.get("content_type") or "other",
                    "score": int(topic.get("score") or 70),
                    "risk_level": topic.get("risk_level") or "low",
                    "tags": ["mock", "mvp"],
                }
            )
        return _validate_clips({"clips": clips}, provider="mock")


class GroqLLMClient(LLMClient):
    def analyze_topics(self, segments: list[TranscriptSegment], *, content_type: str) -> list[dict]:
        prompt = (
            "你是一个直播内容分析助手。根据带时间戳的文字稿识别话题结构。"
            "只输出合法 JSON，格式为 {\"topics\":[{\"topic_id\":\"topic_001\","
            "\"start_time\":0,\"end_time\":0,\"topic_title\":\"\",\"summary\":\"\","
            "\"content_type\":\"other\",\"suitable_for_clip\":true,\"risk_level\":\"low\","
            "\"score\":0}]}。risk_level 只能是 low、medium、high。"
        )
        transcript = [
            {
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "speaker": segment.speaker,
                "text": segment.text,
            }
            for segment in segments
        ]
        payload = self._chat_json(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"content_type": content_type, "transcript_segments": transcript},
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        topics = payload.get("topics")
        if not isinstance(topics, list):
            raise LLMError("Groq LLM topic response missing topics array")
        return _validate_topics(payload, provider="Groq")

    def generate_clips(
        self,
        topics: list[dict],
        *,
        min_duration: int,
        max_duration: int,
        max_count: int,
        risk_filter_enabled: bool,
        video_duration: float,
    ) -> list[dict]:
        prompt = (
            "你是一个直播切片策略专家。根据话题分析结果生成短视频切片方案。"
            "只输出合法 JSON，格式为 {\"clips\":[{\"clip_id\":\"clip_001\","
            "\"start_time\":0,\"end_time\":0,\"title\":\"\",\"summary\":\"\","
            "\"reason\":\"\",\"content_type\":\"other\",\"score\":0,\"risk_level\":\"low\","
            "\"tags\":[]}]}。不要输出 JSON 以外内容。"
        )
        payload = self._chat_json(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "rules": {
                                "min_duration": min_duration,
                                "max_duration": max_duration,
                                "max_count": max_count,
                                "risk_filter_enabled": risk_filter_enabled,
                                "video_duration": video_duration,
                            },
                            "topic_analysis": topics,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        clips = payload.get("clips")
        if not isinstance(clips, list):
            raise LLMError("Groq LLM clip response missing clips array")
        return _validate_clips(payload, provider="Groq")

    def _chat_json(self, messages: list[dict]) -> dict:
        if not settings.groq_api_key:
            raise LLMError("APP_GROQ_API_KEY is required for Groq LLM")
        url = f"{settings.groq_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.groq_llm_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=body,
                timeout=settings.request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _safe_error_detail(exc.response)
            raise LLMError(f"Groq LLM request failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Groq LLM request failed: {exc}") from exc

        content = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("Groq LLM returned invalid JSON") from exc


class ArkLLMClient(GroqLLMClient):
    def _chat_json(self, messages: list[dict]) -> dict:
        if not settings.ark_api_key:
            raise LLMError("ARK_API_KEY or APP_ARK_API_KEY is required for Ark LLM")
        if not settings.ark_model:
            raise LLMError("ARK_MODEL or APP_ARK_MODEL is required for Ark LLM")
        url = f"{settings.ark_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.ark_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.ark_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=body,
                timeout=settings.request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _safe_error_detail(exc.response)
            raise LLMError(f"Ark LLM request failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Ark LLM request failed: {exc}") from exc

        content = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("Ark LLM returned invalid JSON") from exc


def _safe_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]
    return str(payload.get("error") or payload)[:500]


def _validate_topics(payload: dict, *, provider: str) -> list[dict]:
    try:
        parsed = TopicAnalysisResponse.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"{provider} LLM topic response schema validation failed: {exc}") from exc
    return [topic.model_dump() for topic in parsed.topics]


def _validate_clips(payload: dict, *, provider: str) -> list[dict]:
    try:
        parsed = ClipPlanResponse.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"{provider} LLM clip response schema validation failed: {exc}") from exc
    return [clip.model_dump() for clip in parsed.clips]


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "mock":
        return MockLLMClient()
    if settings.llm_provider == "groq":
        return GroqLLMClient()
    if settings.llm_provider == "ark":
        return ArkLLMClient()
    raise LLMError(f"Unsupported LLM provider: {settings.llm_provider}")
