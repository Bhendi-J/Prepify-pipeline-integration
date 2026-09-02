from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.mastery import Mastery
from app.models.topic import Topic
from app.services.adaptive_engine import MasteryState


def get_or_create(
    db: Session,
    user_id: int,
    topic_id: int,
    now: datetime | None = None,
) -> Mastery:
    mastery = get_by_topic(db, user_id=user_id, topic_id=topic_id)
    if mastery is not None:
        return mastery

    current_time = now or datetime.now(UTC)
    mastery = Mastery(
        user_id=user_id,
        topic_id=topic_id,
        ease_factor=2.5,
        interval_days=0,
        next_review_at=current_time,
        streak=0,
    )
    db.add(mastery)
    db.commit()
    db.refresh(mastery)
    return mastery


def lock_mastery_slot(db: Session, user_id: int, topic_id: int) -> None:
    lock_key = f"mastery:{user_id}:{topic_id}"
    db.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
    )


def get_or_create_for_update(
    db: Session,
    user_id: int,
    topic_id: int,
    now: datetime | None = None,
) -> Mastery:
    mastery = get_by_topic(db, user_id=user_id, topic_id=topic_id, for_update=True)
    if mastery is not None:
        return mastery

    current_time = now or datetime.now(UTC)
    mastery = Mastery(
        user_id=user_id,
        topic_id=topic_id,
        ease_factor=2.5,
        interval_days=0,
        next_review_at=current_time,
        streak=0,
    )
    db.add(mastery)
    db.flush()
    return mastery


def get_by_topic(
    db: Session,
    user_id: int,
    topic_id: int,
    for_update: bool = False,
) -> Mastery | None:
    query = (
        db.query(Mastery)
        .filter(
            Mastery.user_id == user_id,
            Mastery.topic_id == topic_id,
        )
    )
    if for_update:
        query = query.with_for_update()
    return query.first()


def list_due(
    db: Session,
    user_id: int,
    now: datetime | None = None,
) -> list[tuple[Mastery, Topic]]:
    current_time = now or datetime.now(UTC)
    return (
        db.query(Mastery, Topic)
        .join(Topic, Topic.id == Mastery.topic_id)
        .filter(
            Mastery.user_id == user_id,
            Topic.user_id == user_id,
            Mastery.next_review_at <= current_time,
        )
        .order_by(Mastery.next_review_at.asc(), Topic.name.asc())
        .all()
    )


def apply_state(db: Session, mastery: Mastery, state: MasteryState) -> Mastery:
    mastery.ease_factor = state.ease_factor
    mastery.interval_days = state.interval_days
    if state.next_review_at is None:
        raise ValueError("next_review_at is required")
    mastery.next_review_at = state.next_review_at
    mastery.streak = state.streak
    db.commit()
    db.refresh(mastery)
    return mastery


def to_state(mastery: Mastery) -> MasteryState:
    return MasteryState(
        ease_factor=mastery.ease_factor,
        interval_days=mastery.interval_days,
        next_review_at=mastery.next_review_at,
        streak=mastery.streak,
    )
