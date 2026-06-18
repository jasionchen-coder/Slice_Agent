from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class ClipResponse(BaseModel):
    clip_id: str
    task_id: str
    title: str | None = None
    summary: str | None = None
    reason: str | None = None
    start_time: float
    end_time: float
    duration: float
    score: int | None = None
    risk_level: str | None = None
    tags: list[str]
    content_type: str | None = None
    clip_url: str | None = None
    status: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ClipListResponse(BaseModel):
    task_id: str
    clips: list[ClipResponse]


class ClipUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_time_range(self) -> "ClipUpdateRequest":
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be less than end_time")
        return self


class ClipMutationResponse(BaseModel):
    clip_id: str
    status: str | None = None
    message: str

