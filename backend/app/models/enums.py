from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    CLEANING_TRANSCRIPT = "cleaning_transcript"
    ANALYZING_CONTENT = "analyzing_content"
    GENERATING_CLIPS = "generating_clips"
    CUTTING_VIDEO = "cutting_video"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClipStatus(StrEnum):
    PENDING = "pending"
    READY_FOR_LOCAL_CUT = "ready_for_local_cut"
    CUTTING_VIDEO = "cutting_video"
    SUCCESS = "success"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
