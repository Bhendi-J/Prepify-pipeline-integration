from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.database import db_session
from app.models.user import User
from app.models.document import Document
from app.services.ingestion import EmptyDocumentTextError, extract_text
from app.repositories.document_repo import (
    create as create_document,
    delete as delete_document,
    get_by_id,
    get_by_user_id,
    update as update_document,
)
from app.repositories.topic_repo import get_by_id as get_topic_by_id
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate, DocumentContent, DocumentSummary
from app.workers.tasks import process_document, summarize_document


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

UPLOAD_DIR = Path("uploads")  # directory to store uploaded files
UPLOAD_DIR.mkdir(exist_ok=True)  # create the directory if it doesn't exist
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf"}

@router.post("/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document_endpoint(
    db: db_session,
    current_user: User = Depends(get_current_user),
    title: str = Form(...), # Form(...) indicates that the title is expected as form data in the request
    source_type: str = Form(...), # ... indicates that the source_type is also expected as form data in the request
    topic_id: int | None = Form(default=None),
    file: UploadFile = File(...),
) -> DocumentRead:
    original_name = Path(file.filename or "upload.txt").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt and .pdf uploads are supported",
        )

    _validate_topic_owner(db, topic_id, current_user.id)

    # save the uploaded file to the server
    file_path = UPLOAD_DIR / f"{uuid4().hex}_{original_name}"
    _save_upload(file, file_path)

    # create a new document record in the database
    document_data = DocumentCreate(
        title=title,
        source_type=extension,
        file_path=str(file_path),
        topic_id=topic_id,
    )
    document = create_document(db, document_data, user_id=current_user.id)
    try:
        process_document.delay(document.id)  # enqueue the document processing task
    except Exception as exc:
        document.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document processing queue is unavailable",
        ) from exc
    return document


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> DocumentRead:
    # retrieve a document record by its ID for the authenticated user only
    document = get_by_id(db, document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    document_id: int,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> None:
    document = get_by_id(db, document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = Path(document.file_path)
    delete_document(db, document)
    file_path.unlink(missing_ok=True)


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document_endpoint(
    document_id: int,
    document_in: DocumentUpdate,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> DocumentRead:
    document = get_by_id(db, document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    payload = document_in.model_dump(exclude_unset=True)
    if "topic_id" in payload:
        _validate_topic_owner(db, payload["topic_id"], current_user.id)

    return update_document(db, document, document_in)


@router.get("/", response_model=list[DocumentRead])
def list_documents(
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> list[DocumentRead]:
    # retrieve all document records for the authenticated user
    return get_by_user_id(db, user_id=current_user.id)


def _validate_topic_owner(
    db: db_session,
    topic_id: int | None,
    user_id: int,
) -> None:
    if topic_id is None:
        return

    if get_topic_by_id(db, topic_id, user_id=user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic not found",
        )


def _save_upload(file: UploadFile, file_path: Path) -> None:
    bytes_written = 0
    try:
        with file_path.open("wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Uploaded file is too large",
                    )
                buffer.write(chunk)
    except Exception:
        file_path.unlink(missing_ok=True)
        raise


@router.get("/{document_id}/content", response_model=DocumentContent)
def read_document_content(
    document_id: int, db: db_session, page: int = Query(1, ge=1),
    page_size: int = Query(4000, ge=500, le=8000), current_user: User = Depends(get_current_user),
):
    document = get_by_id(db, document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(404, "Document not found")
    try:
        text = extract_text(document.file_path)
    except EmptyDocumentTextError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(422, "The original notes cannot be read") from exc
    total_pages = max(1, (len(text) + page_size - 1) // page_size)
    if page > total_pages:
        raise HTTPException(404, "Notes page not found")
    return DocumentContent(document_id=document.id, title=document.title,
        content=text[(page - 1) * page_size:page * page_size], page=page, page_size=page_size,
        total_pages=total_pages, total_characters=len(text))


@router.get("/{document_id}/summary", response_model=DocumentSummary)
def get_summary(document_id: int, db: db_session, current_user: User = Depends(get_current_user)):
    document = get_by_id(db, document_id, user_id=current_user.id)
    if document is None:
        raise HTTPException(404, "Document not found")
    return DocumentSummary(document_id=document.id, status=document.summary_status, summary=document.summary_text)


@router.post("/{document_id}/summary", response_model=DocumentSummary, status_code=202)
def request_summary(document_id: int, db: db_session, current_user: User = Depends(get_current_user)):
    document = db.query(Document).filter_by(id=document_id, user_id=current_user.id).with_for_update().first()
    if document is None:
        raise HTTPException(404, "Document not found")
    if document.status != "ready":
        raise HTTPException(409, "Wait for these notes to finish processing")
    if document.summary_status in {"ready", "pending", "processing"}:
        return DocumentSummary(document_id=document.id, status=document.summary_status, summary=document.summary_text)
    document.summary_status = "pending"
    db.commit()
    try:
        summarize_document.delay(document.id)
    except Exception as exc:
        document.summary_status = "failed"
        db.commit()
        raise HTTPException(503, "The summary queue is unavailable. Please retry.") from exc
    return DocumentSummary(document_id=document.id, status=document.summary_status, summary=document.summary_text)
