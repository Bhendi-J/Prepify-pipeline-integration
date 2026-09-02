from sqlalchemy.orm import Session

from app.models.attempt import Attempt
from app.schemas.attempt import AttemptCreate


def create(
    db: Session,
    attempt_data: AttemptCreate,
    user_id: int,
    question_id: int,
    commit: bool = True,
) -> Attempt:
    attempt = Attempt(
        **attempt_data.model_dump(),
        user_id=user_id,
        question_id=question_id,
    )
    db.add(attempt)
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(attempt)
    return attempt


def exists_for_question(
    db: Session,
    user_id: int,
    question_id: int,
) -> bool:
    return (
        db.query(Attempt.id)
        .filter(
            Attempt.user_id == user_id,
            Attempt.question_id == question_id,
        )
        .first()
        is not None
    )
