from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base): #defining the users table for application accounts
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True) #primary key identifier for each user
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False) #unique email address used for login and identity lookup
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False) #stored password hash, never the raw password
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False) #timestamp assigned by the database when the row is created