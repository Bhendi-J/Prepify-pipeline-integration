from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttemptCreate(BaseModel):
    is_correct: bool
    response_time_ms: int | None = Field(default=None, ge=0)
    submission_id: UUID | None = None


class AttemptRead(BaseModel):
    id: int
    user_id: int
    question_id: int
    is_correct: bool
    response_time_ms: int | None
    created_at: datetime
    answer_text: str
    next_review_at: datetime

    model_config = {"from_attributes": True}
