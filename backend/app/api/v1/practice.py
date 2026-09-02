from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.database import db_session
from app.models.user import User
from app.repositories import attempt_repo, mastery_repo, question_repo, topic_repo
from app.schemas.attempt import AttemptCreate, AttemptRead
from app.schemas.question import PracticeQuestionRequest, QuestionCreate, QuestionPublic
from app.services.adaptive_engine import sm2_update
from app.services.question_gen import QuestionGenerationError, generate_question
from app.services.retrieval import similarity_search


router = APIRouter(prefix="/api/v1/practice", tags=["practice"])


@router.post(
    "/{topic_id}/question",
    response_model=QuestionPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_practice_question(
    topic_id: int,
    db: db_session,
    question_in: PracticeQuestionRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> QuestionPublic:
    topic = topic_repo.get_by_id(db, topic_id, user_id=current_user.id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )

    request = question_in or PracticeQuestionRequest()
    if request.query is None and not request.force_new:
        question_repo.lock_generation_slot(
            db,
            user_id=current_user.id,
            topic_id=topic.id,
            difficulty=request.difficulty,
        )
        existing_question = question_repo.get_latest_by_topic(
            db,
            topic_id=topic.id,
            difficulty=request.difficulty,
            question_type=request.question_type,
        )
        if existing_question is not None:
            was_attempted = attempt_repo.exists_for_question(
                db,
                user_id=current_user.id,
                question_id=existing_question.id,
            )
            if not was_attempted:
                return existing_question
    else:
        question_repo.lock_generation_slot(
            db,
            user_id=current_user.id,
            topic_id=topic.id,
            difficulty=request.difficulty,
        )

    _enforce_question_generation_limit(db, current_user.id)

    results = similarity_search(
        db,
        user_id=current_user.id,
        topic_id=topic.id,
        query=request.query or topic.name,
        k=request.k,
    )
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ready chunks found for this topic",
        )

    chunks = [result.chunk for result in results]
    try:
        generated = generate_question(
            chunks,
            difficulty=request.difficulty,
            question_type=request.question_type,
        )
    except QuestionGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    question = question_repo.create(
        db,
        QuestionCreate(
            topic_id=topic.id,
            chunk_id=chunks[0].id,
            source_chunk_ids=[chunk.id for chunk in chunks],
            question_text=generated.question_text,
            answer_text=generated.answer_text,
            difficulty=request.difficulty,
            question_type=request.question_type,
        ),
    )
    return question


@router.get("/{topic_id}/questions", response_model=list[QuestionPublic])
def list_practice_questions(
    topic_id: int,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> list[QuestionPublic]:
    topic = topic_repo.get_by_id(db, topic_id, user_id=current_user.id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    return question_repo.list_by_topic(
        db,
        topic_id=topic.id,
        user_id=current_user.id,
    )


@router.post(
    "/{question_id}/attempt",
    response_model=AttemptRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_attempt(
    question_id: int,
    attempt_in: AttemptCreate,
    db: db_session,
    current_user: User = Depends(get_current_user),
) -> AttemptRead:
    question = question_repo.get_by_id(db, question_id, user_id=current_user.id)
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    mastery_repo.lock_mastery_slot(
        db,
        user_id=current_user.id,
        topic_id=question.topic_id,
    )
    mastery = mastery_repo.get_or_create_for_update(
        db,
        user_id=current_user.id,
        topic_id=question.topic_id,
    )
    attempt = attempt_repo.create(
        db,
        attempt_data=attempt_in,
        user_id=current_user.id,
        question_id=question.id,
        commit=False,
    )
    updated_state = sm2_update(
        mastery_repo.to_state(mastery),
        was_correct=attempt.is_correct,
    )
    mastery = mastery_repo.apply_state(db, mastery, updated_state)

    return AttemptRead(
        id=attempt.id,
        user_id=attempt.user_id,
        question_id=attempt.question_id,
        is_correct=attempt.is_correct,
        response_time_ms=attempt.response_time_ms,
        created_at=attempt.created_at,
        answer_text=question.answer_text,
        next_review_at=mastery.next_review_at,
    )


def _enforce_question_generation_limit(db: db_session, user_id: int) -> None:
    since = datetime.now(UTC) - timedelta(days=1)
    generated_count = question_repo.count_generated_since(db, user_id=user_id, since=since)
    if generated_count >= settings.MAX_QUESTION_GENERATIONS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily question generation limit reached",
        )
