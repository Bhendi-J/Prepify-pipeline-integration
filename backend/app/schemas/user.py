from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel): #payload used when registering a new user
    email: EmailStr
    password: str = Field(min_length=8) #require a minimally strong password before hashing


class UserRead(BaseModel): #public user representation returned to clients
    id: int
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True} #allow SQLAlchemy model instances to be serialized directly


class Token(BaseModel): #JWT response payload returned by login
    access_token: str
    token_type: str = "bearer"

class UserUpdate(BaseModel): #payload used when updating a user's information
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8) #require a minimally strong password before hashing