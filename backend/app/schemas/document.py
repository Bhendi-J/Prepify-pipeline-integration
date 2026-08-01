from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class DocumentCreate(BaseModel): #payload used when creating a new document
    title: str = Field(max_length=255)
    source_type: str = Field(max_length=100)
    file_path: str = Field(max_length=255)

class DocumentRead(BaseModel): #public document representation returned to clients
    id: int
    user_id: int
    title: str
    source_type: str
    file_path: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True} #allow SQLAlchemy model instances to be serialized directly


class DocumentUpdate(BaseModel): #payload used when updating a document's status
    status: Optional[str] = Field(default=None, max_length=50)  
    title: Optional[str] = Field(default=None, max_length=255)
    