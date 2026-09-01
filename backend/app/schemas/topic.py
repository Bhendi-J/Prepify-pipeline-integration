from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: int | None = None


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: int | None = None


class TopicRead(BaseModel):
    id: int
    user_id: int
    name: str
    parent_id: int | None

    model_config = {"from_attributes": True}


class TopicSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class TopicSearchResult(BaseModel):
    chunk_id: int
    document_id: int
    topic_id: int | None
    content: str
    token_count: int
    distance: float
