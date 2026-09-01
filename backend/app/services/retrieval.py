from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.topic import Topic
from app.services.llm_client import get_embeddings


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    distance: float


def embed_query(text: str) -> list[float]:
    return get_embeddings([text])[0]


def similarity_search(
    db: Session,
    user_id: int,
    topic_id: int,
    query: str,
    k: int = 5,
) -> list[SearchResult]:
    query_embedding = embed_query(query)
    distance = Chunk.embedding.l2_distance(query_embedding).label("distance")

    statement = (
        select(Chunk, distance)
        .join(Topic, Chunk.topic_id == Topic.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Topic.id == topic_id,
            Topic.user_id == user_id,
            Document.user_id == user_id,
            Document.status == "ready",
            func.vector_dims(Chunk.embedding) == len(query_embedding),
        )
        .order_by(distance)
        .limit(k)
    )

    return [
        SearchResult(chunk=chunk, distance=float(score))
        for chunk, score in db.execute(statement).all()
    ]
