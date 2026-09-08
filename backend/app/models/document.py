from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Document(Base): #defining the documents table for application data
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        index=True) #primary key identifier for each document

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True)

    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True)

    
    title: Mapped[str] = mapped_column(
        String(255), 
        nullable=False) #title of the document

    source_type: Mapped[str] = mapped_column(
        String(100), 
        nullable=False) #type of the source document (e.g., PDF, DOCX)
    
    file_path: Mapped[str]  = mapped_column(
        String(255), 
        nullable=False) #path to the stored document file

    status: Mapped[str] = mapped_column(
        String(50), 
        nullable=False,
        default="pending") #current status of the document (e.g., uploaded, processed)
    
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False) #timestamp assigned by the database when the row is created

    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_status: Mapped[str] = mapped_column(String(50), default="none")
