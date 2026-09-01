from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import db_session
from app.models.topic import Topic
from app.models.user import User
from app.repositories import topic_repo
from app.schemas.topic import (
    TopicCreate,
    TopicRead,
    TopicSearchRequest,
    TopicSearchResult,
    TopicUpdate,
)
from app.services.retrieval import similarity_search


router = APIRouter(prefix="/api/v1/topics", tags=["topics"])


@router.post("/", response_model=TopicRead, status_code=status.HTTP_201_CREATED)
def create_topic(
    topic_in: TopicCreate,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> TopicRead:
    _validate_parent(db, current_user.id, topic_in.parent_id)
    return topic_repo.create(db, topic_in, user_id=current_user.id)


@router.get("/", response_model=list[TopicRead])
def list_topics(
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> list[TopicRead]:
    return topic_repo.list_by_user_id(db, user_id=current_user.id)


@router.get("/{topic_id}", response_model=TopicRead)
def get_topic(
    topic_id: int,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> TopicRead:
    topic = _get_user_topic(db, current_user.id, topic_id)
    return topic


@router.patch("/{topic_id}", response_model=TopicRead)
def update_topic(
    topic_id: int,
    topic_in: TopicUpdate,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> TopicRead:
    topic = _get_user_topic(db, current_user.id, topic_id)
    payload = topic_in.model_dump(exclude_unset=True)

    if "parent_id" in payload:
        _validate_parent(db, current_user.id, payload["parent_id"], topic_id=topic.id)

    return topic_repo.update(db, topic, topic_in)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(
    topic_id: int,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> Response:
    topic = _get_user_topic(db, current_user.id, topic_id)
    topic_repo.delete(db, topic)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{topic_id}/search", response_model=list[TopicSearchResult])
def search_topic(
    topic_id: int,
    search_in: TopicSearchRequest,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> list[TopicSearchResult]:
    _get_user_topic(db, current_user.id, topic_id)
    results = similarity_search(
        db,
        user_id=current_user.id,
        topic_id=topic_id,
        query=search_in.query,
        k=search_in.k,
    )

    return [
        TopicSearchResult(
            chunk_id=result.chunk.id,
            document_id=result.chunk.document_id,
            topic_id=result.chunk.topic_id,
            content=result.chunk.content,
            token_count=result.chunk.token_count,
            distance=result.distance,
        )
        for result in results
    ]


def _get_user_topic(db: Session, user_id: int, topic_id: int) -> Topic:
    topic = topic_repo.get_by_id(db, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    return topic


def _validate_parent(
    db: Session,
    user_id: int,
    parent_id: int | None,
    topic_id: int | None = None,
) -> None:
    if parent_id is None:
        return

    parent = topic_repo.get_by_id(db, parent_id, user_id=user_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent topic not found",
        )

    current = parent
    seen_topic_ids: set[int] = set()
    while current is not None:
        if topic_id is not None and current.id == topic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Topic parent would create a cycle",
            )
        if current.id in seen_topic_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Topic parent hierarchy already contains a cycle",
            )
        seen_topic_ids.add(current.id)
        current = (
            topic_repo.get_by_id(db, current.parent_id, user_id=user_id)
            if current.parent_id is not None
            else None
        )
