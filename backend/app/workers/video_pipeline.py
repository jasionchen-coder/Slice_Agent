from pathlib import Path

from app.core.config import settings
from app.integrations.asr_client import get_asr_client
from app.integrations.llm_client import get_llm_client
from app.models.enums import ClipStatus, TaskStatus
from app.repositories.clip_repository import ClipRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.task_log_repository import TaskLogRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audio_service import AudioChunk, AudioService
from app.services.clip_service import ClipService, VideoCutError
from app.services.storage_service import StorageService
from app.services.transcript_service import TranscriptService
from app.utils.id_utils import new_entity_id
from app.utils.retry_utils import run_with_retries
from app.workers.celery_app import celery_app


class TaskCancelled(RuntimeError):
    pass


class VideoPipeline:
    def __init__(self) -> None:
        self.task_repository = TaskRepository()
        self.clip_repository = ClipRepository()
        self.task_log_repository = TaskLogRepository()
        self.transcript_repository = TranscriptRepository()
        self.storage_service = StorageService()
        self.audio_service = AudioService()
        self.transcript_service = TranscriptService()
        self.clip_service = ClipService(self.clip_repository, self.storage_service)
        self.asr_client = get_asr_client()
        self.llm_client = get_llm_client()

    def process(self, task_id: str) -> None:
        stage = "process_video_task"
        try:
            task = self._get_task(task_id)
            self._ensure_not_cancelled(task_id)

            if self._is_frontend_audio_task(task):
                chunks = self._frontend_audio_chunks(task_id)
                self._log(task_id, str(TaskStatus.EXTRACTING_AUDIO), "info", f"使用前端上传音频，共 {len(chunks)} 段")
            else:
                stage = TaskStatus.EXTRACTING_AUDIO
                self._log(task_id, str(stage), "info", "开始提取音频")
                self.task_repository.update_status(
                    task_id, status=TaskStatus.EXTRACTING_AUDIO, progress=15, current_stage="音频提取中"
                )
                audio_path = run_with_retries(
                    lambda: self.audio_service.extract_audio(
                        Path(task["original_video_path"]),
                        self.storage_service.audio_path(task_id),
                    ),
                    retries=settings.audio_extract_retries,
                    on_retry=lambda attempt, exc: self._log_retry(task_id, str(stage), attempt, exc),
                )
                chunks = self.audio_service.split_audio(
                    audio_path,
                    self.storage_service.audio_chunks_dir(task_id),
                    total_duration=float(task.get("video_duration") or 0),
                    chunk_seconds=settings.audio_chunk_seconds,
                    overlap_seconds=settings.audio_chunk_overlap_seconds,
                )
                self._log(task_id, str(stage), "info", f"音频分片完成，共 {len(chunks)} 段")

            self._ensure_not_cancelled(task_id)
            stage = TaskStatus.TRANSCRIBING
            self._log(task_id, str(stage), "info", "开始 ASR 转写")
            self.task_repository.update_status(
                task_id, status=TaskStatus.TRANSCRIBING, progress=40, current_stage="语音识别中"
            )
            chunk_segments = []
            for index, chunk in enumerate(chunks):
                self._ensure_not_cancelled(task_id)
                transcribed = run_with_retries(
                    lambda chunk=chunk: self.asr_client.transcribe(
                        chunk.path,
                        duration=chunk.duration,
                    ),
                    retries=settings.asr_retries,
                    on_retry=lambda attempt, exc, chunk_index=index: self._log_retry(
                        task_id,
                        str(stage),
                        attempt,
                        exc,
                        message=f"ASR 分片 {chunk_index + 1} 重试",
                    ),
                )
                chunk_segments.append(
                    self.transcript_service.offset_segments(
                        transcribed,
                        offset_seconds=chunk.start_time,
                    )
                )
            segments = self.transcript_service.merge_chunk_segments(chunk_segments)
            if not segments:
                raise RuntimeError("ASR did not return any transcript segments")
            raw_segments = [segment.model_dump() for segment in segments]
            self.storage_service.write_json(
                self.storage_service.transcript_path(task_id, "raw_transcript.json"),
                {"segments": raw_segments},
            )

            self._ensure_not_cancelled(task_id)
            stage = TaskStatus.CLEANING_TRANSCRIPT
            self._log(task_id, str(stage), "info", "开始清洗文字稿")
            self.task_repository.update_status(
                task_id,
                status=TaskStatus.CLEANING_TRANSCRIPT,
                progress=50,
                current_stage="文字清洗中",
            )
            cleaned_segments = self.transcript_service.clean_segments(segments)
            cleaned_payload = [segment.model_dump() for segment in cleaned_segments]
            self.storage_service.write_json(
                self.storage_service.transcript_path(task_id, "cleaned_transcript.json"),
                {"segments": cleaned_payload},
            )
            transcript_id = new_entity_id("transcript")
            self.transcript_repository.create_transcript(
                {
                    "transcript_id": transcript_id,
                    "task_id": task_id,
                    "raw_text": "\n".join(segment.text for segment in segments),
                    "cleaned_text": "\n".join(segment.text for segment in cleaned_segments),
                    "language": settings.default_language,
                    "asr_provider": settings.asr_provider,
                }
            )
            self.transcript_repository.create_segments(
                [
                    {
                        "segment_id": new_entity_id("segment", index),
                        "task_id": task_id,
                        "transcript_id": transcript_id,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "speaker": segment.speaker,
                        "text": raw_segments[index]["text"] if index < len(raw_segments) else segment.text,
                        "cleaned_text": segment.text,
                        "segment_index": index,
                    }
                    for index, segment in enumerate(cleaned_segments)
                ]
            )

            self._ensure_not_cancelled(task_id)
            stage = TaskStatus.ANALYZING_CONTENT
            self._log(task_id, str(stage), "info", "开始 LLM 话题分析")
            self.task_repository.update_status(
                task_id,
                status=TaskStatus.ANALYZING_CONTENT,
                progress=70,
                current_stage="内容分析中",
            )
            topics = run_with_retries(
                lambda: self.llm_client.analyze_topics(
                    cleaned_segments,
                    content_type=task.get("content_type") or "other",
                ),
                retries=settings.llm_retries,
                on_retry=lambda attempt, exc: self._log_retry(task_id, str(stage), attempt, exc),
            )
            self.storage_service.write_json(
                self.storage_service.llm_path(task_id, "topic_analysis.json"),
                {"topics": topics},
            )
            self.transcript_repository.create_topics(
                [
                    {
                        "topic_id": new_entity_id("topic", index),
                        "task_id": task_id,
                        "start_time": topic["start_time"],
                        "end_time": topic["end_time"],
                        "topic_title": topic.get("topic_title"),
                        "summary": topic.get("summary"),
                        "content_type": topic.get("content_type"),
                        "suitable_for_clip": topic.get("suitable_for_clip", True),
                        "risk_level": topic.get("risk_level"),
                        "score": topic.get("score"),
                        "raw_llm_output": topic,
                    }
                    for index, topic in enumerate(topics)
                ]
            )

            self._ensure_not_cancelled(task_id)
            stage = TaskStatus.GENERATING_CLIPS
            self._log(task_id, str(stage), "info", "开始 LLM 生成切片方案")
            self.task_repository.update_status(
                task_id,
                status=TaskStatus.GENERATING_CLIPS,
                progress=80,
                current_stage="切片方案生成中",
            )
            candidates = run_with_retries(
                lambda: self.llm_client.generate_clips(
                    topics,
                    min_duration=task["min_clip_duration"],
                    max_duration=task["max_clip_duration"],
                    max_count=task["max_clip_count"],
                    risk_filter_enabled=bool(task["risk_filter_enabled"]),
                    video_duration=float(task["video_duration"] or 0),
                ),
                retries=settings.llm_retries,
                on_retry=lambda attempt, exc: self._log_retry(task_id, str(stage), attempt, exc),
            )
            self.storage_service.write_json(
                self.storage_service.llm_path(task_id, "clip_plan.json"),
                {"clips": candidates},
            )
            self.clip_repository.delete_by_task(task_id)
            clips = self.clip_service.save_clip_plan(
                task_id,
                candidates,
                min_duration=task["min_clip_duration"],
                max_duration=task["max_clip_duration"],
                max_count=task["max_clip_count"],
                risk_filter_enabled=bool(task["risk_filter_enabled"]),
                video_duration=float(task["video_duration"] or 0),
            )

            if self._is_frontend_audio_task(task):
                for clip in clips:
                    self.clip_repository.update(clip["clip_id"], {"status": ClipStatus.READY_FOR_LOCAL_CUT})
                self._log(task_id, str(TaskStatus.COMPLETED), "info", "切片时间方案已生成，等待前端本地切片")
                self.task_repository.update_status(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    current_stage="切片方案已生成",
                )
                return

            self._ensure_not_cancelled(task_id)
            stage = TaskStatus.CUTTING_VIDEO
            self._log(task_id, str(stage), "info", "开始切割视频")
            self.task_repository.update_status(
                task_id, status=TaskStatus.CUTTING_VIDEO, progress=95, current_stage="视频切割中"
            )
            task = self._get_task(task_id)
            for clip in clips:
                try:
                    run_with_retries(
                        lambda clip=clip: self.clip_service.cut_clip(task, clip),
                        retries=settings.ffmpeg_cut_retries,
                        on_retry=lambda attempt, exc, clip_id=clip["clip_id"]: self._log_retry(
                            task_id,
                            str(stage),
                            attempt,
                            exc,
                            message=f"切片 {clip_id} 重试",
                        ),
                    )
                except VideoCutError:
                    self._log(task_id, str(stage), "error", f"切片 {clip['clip_id']} 失败")
                    continue

            self._log(task_id, str(TaskStatus.COMPLETED), "info", "任务处理完成")
            self.task_repository.update_status(
                task_id, status=TaskStatus.COMPLETED, progress=100, current_stage="处理完成"
            )
        except TaskCancelled:
            self.task_repository.update_status(
                task_id,
                status=TaskStatus.CANCELLED,
                progress=0,
                current_stage="任务已取消",
            )
        except Exception as exc:
            self._log(task_id, str(stage), "error", "任务处理失败", error_message=str(exc))
            self.task_repository.update_status(
                task_id,
                status=TaskStatus.FAILED,
                progress=0,
                current_stage="处理失败",
                failed_stage=str(stage),
                error_message=str(exc),
            )

    def _get_task(self, task_id: str) -> dict:
        task = self.task_repository.get(task_id)
        if task is None:
            raise RuntimeError(f"Task not found: {task_id}")
        return task

    def _ensure_not_cancelled(self, task_id: str) -> None:
        task = self._get_task(task_id)
        if task["status"] == TaskStatus.CANCELLED:
            raise TaskCancelled(task_id)

    def _is_frontend_audio_task(self, task: dict) -> bool:
        return task.get("video_url") == "frontend-audio"

    def _frontend_audio_chunks(self, task_id: str) -> list[AudioChunk]:
        manifest = self.storage_service.load_audio_manifest(task_id)
        chunks = [
            AudioChunk(
                path=Path(item["path"]),
                start_time=float(item["start_time"]),
                end_time=float(item["end_time"]),
            )
            for item in manifest
        ]
        if not chunks:
            raise RuntimeError("Frontend audio task has no uploaded audio chunks")
        for chunk in chunks:
            if not chunk.path.exists():
                raise RuntimeError(f"Uploaded audio chunk does not exist: {chunk.path}")
        return chunks

    def _log(
        self,
        task_id: str,
        stage: str,
        level: str,
        message: str,
        *,
        attempt: int | None = None,
        error_message: str | None = None,
    ) -> None:
        self.task_log_repository.create(
            task_id=task_id,
            stage=stage,
            level=level,
            message=message,
            attempt=attempt,
            error_message=error_message,
        )

    def _log_retry(
        self,
        task_id: str,
        stage: str,
        attempt: int,
        exc: Exception,
        *,
        message: str = "阶段执行失败，准备重试",
    ) -> None:
        self._log(
            task_id,
            stage,
            "warning",
            message,
            attempt=attempt,
            error_message=str(exc),
        )


@celery_app.task(name="process_video_task")
def process_video_task(task_id: str) -> None:
    VideoPipeline().process(task_id)
