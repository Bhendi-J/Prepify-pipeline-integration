from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from app.schemas.question import QuestionPublic
from app.schemas.attempt import AttemptRead


class SessionCreate(BaseModel):
    topic_id: int
    document_id: int | None = None
    query: str | None = Field(default=None, max_length=1000)
    count: int = Field(default=3, ge=1, le=5)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_type: Literal["short_answer", "multiple_choice", "true_false", "conceptual"] = "short_answer"
    request_id: UUID


class SessionRead(BaseModel):
    id: int
    topic_id: int
    document_id: int | None
    title: str
    focus: str | None
    difficulty: str
    question_type: str
    is_legacy: bool
    created_at: datetime
    question_count: int

    model_config = {"from_attributes": True}


class SessionPage(BaseModel):
    items: list[SessionRead]
    total: int
    page: int
    page_size: int


class SessionQuestions(BaseModel):
    session: SessionRead
    attempts: list[AttemptRead] = Field(default_factory=list)
    items: list[QuestionPublic]
    total: int
    page: int
    page_size: int
