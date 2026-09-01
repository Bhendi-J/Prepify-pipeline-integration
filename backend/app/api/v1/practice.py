from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.database import db_session
from app.models.user import User
from app.repositories import question_repo, topic_repo
from app.schemas.question import PracticeQuestionRequest, QuestionCreate, QuestionRead
from app.services.question_gen import QuestionGenerationError, generate_question
from app.services.retrieval import similarity_search


router = APIRouter(prefix="/api/v1/practice", tags=["practice"])


@router.post(
    "/{topic_id}/question",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_practice_question(
    topic_id: int,
    db: db_session,
    question_in: PracticeQuestionRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> QuestionRead:
    topic = topic_repo.get_by_id(db, topic_id, user_id=current_user.id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )

    request = question_in or PracticeQuestionRequest()
    if request.query is None:
        existing_question = question_repo.get_latest_by_topic(
            db,
            topic_id=topic.id,
            difficulty=request.difficulty,
        )
        if existing_question is not None:
            return existing_question

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
        generated = generate_question(chunks, difficulty=request.difficulty)
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
            question_text=generated.question_text,
            answer_text=generated.answer_text,
            difficulty=request.difficulty,
        ),
    )
    return question
