from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.question import Question, QuestionChunk
from app.models.topic import Topic
from app.schemas.question import QuestionCreate


def lock_generation_slot(
    db: Session,
    user_id: int,
    topic_id: int,
    difficulty: str,
) -> None:
    lock_key = f"practice-question:{user_id}:{topic_id}:{difficulty}"
    db.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
    )


def get_latest_by_topic(
    db: Session,
    topic_id: int,
    difficulty: str,
    question_type: str = "short_answer",
) -> Question | None:
    return (
        db.query(Question)
        .options(selectinload(Question.source_chunks))
        .filter(
            Question.topic_id == topic_id,
            Question.difficulty == difficulty,
            Question.question_type == question_type,
        )
        .order_by(Question.id.desc())
        .first()
    )


def list_by_topic(
    db: Session,
    topic_id: int,
    user_id: int,
    limit: int = 50,
) -> list[Question]:
    return (
        db.query(Question)
        .options(selectinload(Question.source_chunks))
        .join(Topic, Question.topic_id == Topic.id)
        .filter(
            Question.topic_id == topic_id,
            Topic.user_id == user_id,
        )
        .order_by(Question.id.desc())
        .limit(limit)
        .all()
    )


def get_by_id(db: Session, question_id: int, user_id: int | None = None) -> Question | None:
    query = (
        db.query(Question)
        .options(selectinload(Question.source_chunks))
        .filter(Question.id == question_id)
    )
    if user_id is not None:
        query = query.join(Topic, Question.topic_id == Topic.id).filter(
            Topic.user_id == user_id
        )
    return query.first()


def count_generated_since(db: Session, user_id: int, since: datetime) -> int:
    return (
        db.query(func.count(Question.id))
        .join(Topic, Question.topic_id == Topic.id)
        .filter(
            Topic.user_id == user_id,
            Question.created_at >= since,
        )
        .scalar()
        or 0
    )


def create(db: Session, question_data: QuestionCreate) -> Question:
    payload = question_data.model_dump()
    source_chunk_ids = _dedupe_chunk_ids(payload.pop("source_chunk_ids"))
    if not source_chunk_ids and payload["chunk_id"] is not None:
        source_chunk_ids = [payload["chunk_id"]]

    question = Question(**payload)
    db.add(question)
    db.flush()

    db.add_all(
        QuestionChunk(
            question_id=question.id,
            chunk_id=chunk_id,
            position=position,
        )
        for position, chunk_id in enumerate(source_chunk_ids)
    )
    db.commit()
    db.refresh(question)
    return question


def _dedupe_chunk_ids(chunk_ids: list[int]) -> list[int]:
    seen: set[int] = set()
    deduped: list[int] = []
    for chunk_id in chunk_ids:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        deduped.append(chunk_id)
    return deduped
