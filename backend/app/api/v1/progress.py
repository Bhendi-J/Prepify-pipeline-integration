from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.database import db_session
from app.models.user import User
from app.repositories import mastery_repo, topic_repo
from app.schemas.mastery import DueTopicRead, MasteryRead


router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


@router.get("/due", response_model=list[DueTopicRead])
def get_due_topics(
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> list[DueTopicRead]:
    due_rows = mastery_repo.list_due(db, user_id=current_user.id)
    return [
        DueTopicRead(
            topic_id=topic.id,
            name=topic.name,
            parent_id=topic.parent_id,
            ease_factor=mastery.ease_factor,
            interval_days=mastery.interval_days,
            next_review_at=mastery.next_review_at,
            streak=mastery.streak,
        )
        for mastery, topic in due_rows
    ]


@router.get("/{topic_id}", response_model=MasteryRead)
def get_topic_progress(
    topic_id: int,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> MasteryRead:
    if topic_repo.get_by_id(db, topic_id, user_id=current_user.id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )

    mastery = mastery_repo.get_by_topic(db, user_id=current_user.id, topic_id=topic_id)
    if mastery is None:
        return MasteryRead(
            user_id=current_user.id,
            topic_id=topic_id,
            ease_factor=2.5,
            interval_days=0,
            next_review_at=datetime.now(UTC),
            streak=0,
        )
    return mastery
