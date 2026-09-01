from app.database import SessionLocal
from app.models.document import Document
from app.models.topic import Topic
from app.models.user import User
from app.repositories.chunk_repo import replace_for_document
from app.services.ingestion import chunk_text, extract_text
from app.services.llm_client import get_embeddings
from app.workers.celery_app import celery_app


@celery_app.task(name="process_document")
def process_document(document_id: int) -> None:
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            return

        document.status = "processing"
        db.commit()

        text = extract_text(document.file_path)
        text_chunks = chunk_text(text)
        embeddings = get_embeddings([chunk.content for chunk in text_chunks])
        replace_for_document(
            db,
            document_id=document.id,
            chunks_data=[
                {
                    "document_id": document.id,
                    "topic_id": document.topic_id,
                    "content": chunk.content,
                    "embedding": embedding,
                    "token_count": chunk.token_count,
                }
                for chunk, embedding in zip(text_chunks, embeddings, strict=True)
            ],
        )

        document.status = "ready"
        db.commit()
    except Exception:
        db.rollback()
        document = db.get(Document, document_id)
        if document is not None:
            document.status = "failed"
            db.commit()
        raise
    finally:
        db.close()
