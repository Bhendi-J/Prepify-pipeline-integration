from sqlalchemy.orm import Session

from app.models.question import Question
from app.schemas.question import QuestionCreate


def get_latest_by_topic(
    db: Session,
    topic_id: int,
    difficulty: str,
) -> Question | None:
    return (
        db.query(Question)
        .filter(
            Question.topic_id == topic_id,
            Question.difficulty == difficulty,
        )
        .order_by(Question.id.desc())
        .first()
    )


def create(db: Session, question_data: QuestionCreate) -> Question:
    question = Question(**question_data.model_dump())
    db.add(question)
    db.commit()
    db.refresh(question)
    return question
