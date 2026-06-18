from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RiskLevelValue = Literal["low", "medium", "high"]


def parse_time_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("time value cannot be empty")
        if ":" not in stripped:
            return float(stripped)
        parts = stripped.split(":")
        if len(parts) > 3:
            raise ValueError("time value has too many components")
        numbers = [float(part) for part in parts]
        while len(numbers) < 3:
            numbers.insert(0, 0.0)
        hours, minutes, seconds = numbers
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError("time value must be number or timestamp string")


class TopicItem(BaseModel):
    topic_id: str = Field(default="")
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    topic_title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    content_type: str = Field(default="other", min_length=1)
    suitable_for_clip: bool = True
    risk_level: RiskLevelValue = "low"
    score: int = Field(default=0, ge=0, le=100)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_time(cls, value: Any) -> float:
        return parse_time_value(value)

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, value: Any) -> str:
        mapping = {
            "低": "low",
            "低风险": "low",
            "中": "medium",
            "中风险": "medium",
            "高": "high",
            "高风险": "high",
        }
        text = str(value or "low").strip().lower()
        return mapping.get(text, text)

    @model_validator(mode="after")
    def validate_time_range(self) -> "TopicItem":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be less than end_time")
        return self


class TopicAnalysisResponse(BaseModel):
    topics: list[TopicItem]


class ClipPlanItem(BaseModel):
    clip_id: str = Field(default="")
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    content_type: str = Field(default="other", min_length=1)
    score: int = Field(ge=0, le=100)
    risk_level: RiskLevelValue = "low"
    tags: list[str] = Field(default_factory=list)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_time(cls, value: Any) -> float:
        return parse_time_value(value)

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, value: Any) -> str:
        return TopicItem.normalize_risk_level(value)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> "ClipPlanItem":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be less than end_time")
        return self


class ClipPlanResponse(BaseModel):
    clips: list[ClipPlanItem]

