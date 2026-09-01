from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.chunk import Chunk


def replace_for_document(
    db: Session,
    document_id: int,
    chunks_data: Sequence[dict],
) -> list[Chunk]:
    db.query(Chunk).filter(Chunk.document_id == document_id).delete(
        synchronize_session=False
    )

    chunks = [Chunk(**chunk_data) for chunk_data in chunks_data]
    db.add_all(chunks)
    db.commit()
    return chunks
