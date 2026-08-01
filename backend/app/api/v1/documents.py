from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
import shutil
from pathlib import Path
from fastapi import Form
from app.api.deps import get_current_user
from app.database import db_session
from app.models.user import User
from app.repositories.document_repo import create as create_document, get_by_id, get_by_user_id
from app.schemas.document import DocumentCreate, DocumentRead


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

UPLOAD_DIR = Path("uploads")  # directory to store uploaded files
UPLOAD_DIR.mkdir(exist_ok=True)  # create the directory if it doesn't exist

@router.post("/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document_endpoint(
    db: db_session,
    current_user: User = Depends(get_current_user),
    title: str = Form(...), # Form(...) indicates that the title is expected as form data in the request
    source_type: str = Form(...), # ... indicates that the source_type is also expected as form data in the request
    file: UploadFile = File(...),
) -> DocumentRead:
    # save the uploaded file to the server
    file_path = UPLOAD_DIR / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # create a new document record in the database
    document_data = DocumentCreate(title=title, source_type=source_type, file_path=str(file_path))
    document = create_document(db, document_data, user_id=current_user.id)
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


@router.get("/", response_model=list[DocumentRead])
def list_documents(
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> list[DocumentRead]:
    # retrieve all document records for the authenticated user
    return get_by_user_id(db, user_id=current_user.id)

