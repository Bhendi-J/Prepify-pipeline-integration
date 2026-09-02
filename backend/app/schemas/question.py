from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    topic_id: int
    chunk_id: int | None = None
    question_text: str
    answer_text: str
    difficulty: str = Field(max_length=50)
    question_type: str = Field(default="short_answer", max_length=50)
    source_chunk_ids: list[int] = Field(default_factory=list)


class QuestionPublic(BaseModel):
    id: int
    topic_id: int
    chunk_id: int | None
    source_chunk_ids: list[int]
    question_text: str
    difficulty: str
    question_type: str

    model_config = {"from_attributes": True}


class PracticeQuestionRequest(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    difficulty: str = Field(default="medium", max_length=50)
    question_type: str = Field(default="short_answer", max_length=50)
    k: int = Field(default=5, ge=1, le=10)
    force_new: bool = False
