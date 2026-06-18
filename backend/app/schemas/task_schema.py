from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class TaskCreateParams(BaseModel):
    content_type: str = Field(min_length=1)
    min_clip_duration: int = Field(default=30, ge=5, le=3600)
    max_clip_duration: int = Field(default=180, ge=5, le=7200)
    max_clip_count: int = Field(default=10, ge=1, le=100)
    risk_filter_enabled: bool = True

    @model_validator(mode="after")
    def validate_duration_range(self) -> "TaskCreateParams":
        if self.min_clip_duration >= self.max_clip_duration:
            raise ValueError("min_clip_duration must be less than max_clip_duration")
        return self


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskResponse(BaseModel):
    task_id: str
    video_name: str
    video_url: str | None = None
    video_duration: float | None = None
    video_size: int | None = None
    video_format: str | None = None
    video_resolution: str | None = None
    content_type: str | None = None
    min_clip_duration: int
    max_clip_duration: int
    max_clip_count: int
    risk_filter_enabled: bool
    status: str
    progress: int
    current_stage: str | None = None
    failed_stage: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]

