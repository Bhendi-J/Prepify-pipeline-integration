from sqlalchemy.orm import Session

from app.models.document import Document
from app.repositories.chunk_repo import set_topic_for_document
from app.schemas.document import DocumentCreate, DocumentUpdate


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


def update(db: Session, document: Document, document_data: DocumentUpdate) -> Document:
    payload = document_data.model_dump(exclude_unset=True)
    topic_changed = "topic_id" in payload and payload["topic_id"] != document.topic_id

    for field, value in payload.items():
        setattr(document, field, value)

    if topic_changed:
        set_topic_for_document(db, document.id, payload["topic_id"])

    db.commit()
    db.refresh(document)
    return document
