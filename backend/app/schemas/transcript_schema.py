from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    speaker: str | None = None
    text: str = Field(min_length=1)

