from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document import DocumentCreate


def get_by_user_id(db: Session, user_id: int) -> list[Document]:
    # lookup helper used to retrieve all documents for a given user
    return db.query(Document).filter(Document.user_id == user_id).all()


def get_by_id(db: Session, document_id: int, user_id: int | None = None) -> Document | None:
    # lookup helper used to retrieve a document by its ID for an optional owner
    query = db.query(Document).filter(Document.id == document_id)
    if user_id is not None:
        query = query.filter(Document.user_id == user_id)
    return query.first()


def create(db: Session, document_data: DocumentCreate, user_id: int, status: str = "pending") -> Document:
    # persist a new document record using already-prepared values
    payload = document_data.model_dump()
    payload["user_id"] = user_id
    payload["status"] = status

    document = Document(**payload)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document