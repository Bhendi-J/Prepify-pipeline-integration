from datetime import datetime
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel): #payload used when creating a new document
    title: str = Field(max_length=255)
    source_type: str = Field(max_length=100)
    file_path: str = Field(max_length=255)
    topic_id: int | None = None

class DocumentRead(BaseModel): #public document representation returned to clients
    id: int
    user_id: int
    topic_id: int | None
    title: str
    source_type: str
    file_path: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True} #allow SQLAlchemy model instances to be serialized directly


class DocumentUpdate(BaseModel): #payload used when updating a document's status
    status: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=255)
    topic_id: int | None = None


class DocumentContent(BaseModel):
    document_id: int
    title: str
    content: str
    page: int
    page_size: int
    total_pages: int
    total_characters: int


class DocumentSummary(BaseModel):
    document_id: int
    status: str
    summary: str | None
