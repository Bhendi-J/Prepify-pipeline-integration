from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.database import db_session
from app.models.attempt import Attempt
from app.models.question import Question
from app.models.topic import Topic
from app.models.user import User
from app.repositories import mastery_repo, topic_repo
from app.schemas.mastery import ActivityDayRead, DueTopicRead, MasteryRead, ProgressStatsRead


router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


@router.get("/stats", response_model=ProgressStatsRead)
def get_progress_stats(
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> ProgressStatsRead:
    today = datetime.now(UTC).date()
    first_day = today - timedelta(days=34)
    window_start = datetime.combine(first_day, datetime.min.time(), tzinfo=UTC)
    attempts = (
        db.query(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .join(Topic, Topic.id == Question.topic_id)
        .filter(
            Attempt.user_id == current_user.id,
            Topic.user_id == current_user.id,
            Attempt.created_at >= window_start,
        )
        .all()
    )
    totals = (
        db.query(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .join(Topic, Topic.id == Question.topic_id)
        .filter(Attempt.user_id == current_user.id, Topic.user_id == current_user.id)
        .all()
    )

    by_day: dict[date, dict[str, int]] = {}
    for attempt in attempts:
        attempted_at = attempt.created_at
        if attempted_at.tzinfo is None:
            attempted_at = attempted_at.replace(tzinfo=UTC)
        attempted_on = attempted_at.astimezone(UTC).date()
        row = by_day.setdefault(attempted_on, {"attempted": 0, "correct": 0})
        row["attempted"] += 1
        if attempt.is_correct:
            row["correct"] += 1

    days = []
    for offset in range(35):
        day = first_day + timedelta(days=offset)
        row = by_day.get(day, {"attempted": 0, "correct": 0})
        days.append(ActivityDayRead(date=day.isoformat(), attempted=row["attempted"], correct=row["correct"]))

    total_attempted = len(totals)
    total_correct = sum(1 for attempt in totals if attempt.is_correct)
    return ProgressStatsRead(
        attempted=total_attempted,
        correct=total_correct,
        accuracy=round(total_correct / total_attempted, 3) if total_attempted else 0,
        activity_streak=_activity_streak(by_day, today),
        days=days,
    )


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


def _activity_streak(by_day: dict[date, dict[str, int]], today: date) -> int:
    streak = 0
    current = today
    while by_day.get(current, {}).get("attempted", 0) > 0:
        streak += 1
        current -= timedelta(days=1)
    return streak


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
