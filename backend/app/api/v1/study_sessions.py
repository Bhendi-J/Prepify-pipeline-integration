from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func

from app.api.deps import get_current_user
from app.core.config import settings
from app.database import db_session
from app.models.question import Question, QuestionChunk
from app.models.study_session import StudySession
from app.models.user import User
from app.models.attempt import Attempt
from app.schemas.attempt import AttemptRead
from app.repositories import mastery_repo
from app.repositories import document_repo, question_repo, topic_repo
from app.schemas.study_session import SessionCreate, SessionPage, SessionQuestions, SessionRead
from app.services.question_gen import QuestionGenerationError, generate_questions
from app.services.retrieval import similarity_search
from datetime import UTC, datetime, timedelta

router = APIRouter(prefix="/api/v1/study-sessions", tags=["study sessions"])


def session_read(db, row):
    count = db.query(func.count(Question.id)).filter(Question.session_id == row.id).scalar()
    return SessionRead(
        id=row.id, topic_id=row.topic_id, document_id=row.document_id,
        title=row.title, focus=row.focus, difficulty=row.difficulty,
        question_type=row.question_type, is_legacy=row.is_legacy,
        created_at=row.created_at, question_count=count,
    )


@router.get("/", response_model=SessionPage)
def list_sessions(
    db: db_session, topic_id: int, page: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=30), current_user: User = Depends(get_current_user),
):
    if topic_repo.get_by_id(db, topic_id, user_id=current_user.id) is None:
        raise HTTPException(404, "Topic not found")
    query = db.query(StudySession).filter_by(user_id=current_user.id, topic_id=topic_id)
    total = query.count()
    rows = query.order_by(StudySession.created_at.desc(), StudySession.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return SessionPage(items=[session_read(db, row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/{session_id}", response_model=SessionQuestions)
def get_session(
    session_id: int, db: db_session, page: int = Query(1, ge=1),
    page_size: int = Query(1, ge=1, le=5), current_user: User = Depends(get_current_user),
):
    row = db.query(StudySession).filter_by(id=session_id, user_id=current_user.id).first()
    if row is None:
        raise HTTPException(404, "Study session not found")
    query = db.query(Question).filter_by(session_id=row.id)
    total = query.count()
    if page > max(1, (total + page_size - 1) // page_size):
        raise HTTPException(404, "Question page not found")
    questions = query.order_by(Question.id).offset((page - 1) * page_size).limit(page_size).all()
    attempts = []
    mastery = mastery_repo.get_by_topic(db, current_user.id, row.topic_id)
    for question in questions:
        attempt = db.query(Attempt).filter_by(user_id=current_user.id, question_id=question.id).order_by(Attempt.id.desc()).first()
        if attempt is not None and mastery is not None:
            attempts.append(AttemptRead(
                id=attempt.id, user_id=attempt.user_id, question_id=attempt.question_id,
                is_correct=attempt.is_correct, response_time_ms=attempt.response_time_ms,
                created_at=attempt.created_at, answer_text=question.answer_text,
                next_review_at=mastery.next_review_at,
            ))
    return SessionQuestions(
        session=session_read(db, row), items=questions, attempts=attempts,
        total=total, page=page, page_size=page_size,
    )


@router.post("/", response_model=SessionQuestions, status_code=201)
def create_session(payload: SessionCreate, db: db_session, current_user: User = Depends(get_current_user)):
    topic = topic_repo.get_by_id(db, payload.topic_id, user_id=current_user.id)
    if topic is None:
        raise HTTPException(404, "Topic not found")
    document = None
    if payload.document_id is not None:
        document = document_repo.get_by_id(db, payload.document_id, user_id=current_user.id)
        if document is None or document.topic_id != topic.id:
            raise HTTPException(404, "Selected notes do not belong to this topic")
        if document.status != "ready":
            raise HTTPException(409, "Selected notes are not ready yet")
    question_repo.lock_generation_slot(db, current_user.id, topic.id, payload.difficulty)
    existing = db.query(StudySession).filter_by(user_id=current_user.id, request_id=payload.request_id).first()
    if existing is not None:
        if (existing.topic_id, existing.document_id, existing.focus, existing.difficulty, existing.question_type,
            db.query(Question).filter_by(session_id=existing.id).count()) != (
            topic.id, payload.document_id, (payload.query or "").strip() or None, payload.difficulty, payload.question_type, payload.count):
            raise HTTPException(409, "This generation request was already used with different settings")
        return get_session(existing.id, db, 1, 1, current_user)
    used = question_repo.count_generated_since(db, current_user.id, datetime.now(UTC) - timedelta(days=1))
    if used + payload.count > settings.MAX_QUESTION_GENERATIONS_PER_DAY:
        raise HTTPException(429, f"Only {max(0, settings.MAX_QUESTION_GENERATIONS_PER_DAY - used)} questions remain in your daily allowance")
    results = similarity_search(
        db, user_id=current_user.id, topic_id=topic.id,
        query=(payload.query or "").strip() or (document.title if document else topic.name),
        k=5, document_id=payload.document_id,
    )
    if not results:
        raise HTTPException(404, "No ready chunks found in the selected notes")
    previous = [text for (text,) in db.query(Question.question_text).filter_by(topic_id=topic.id).order_by(Question.id).all()]
    try:
        generated = generate_questions([r.chunk for r in results], payload.count, payload.difficulty, payload.question_type, previous, payload.query)
    except QuestionGenerationError as exc:
        raise HTTPException(502, str(exc)) from exc
    row = StudySession(
        user_id=current_user.id, topic_id=topic.id, document_id=payload.document_id,
        title=(document.title if document else topic.name)[:220] + " — Practice",
        focus=(payload.query or "").strip() or None, difficulty=payload.difficulty,
        question_type=payload.question_type, request_id=payload.request_id,
    )
    db.add(row)
    db.flush()
    chunk_ids = list(dict.fromkeys(r.chunk.id for r in results))
    for item in generated:
        question = Question(session_id=row.id, topic_id=topic.id, chunk_id=chunk_ids[0],
            question_text=item.question_text, answer_text=item.answer_text,
            difficulty=payload.difficulty, question_type=payload.question_type)
        db.add(question)
        db.flush()
        db.add_all(QuestionChunk(question_id=question.id, chunk_id=chunk_id, position=index) for index, chunk_id in enumerate(chunk_ids))
    db.commit()
    return get_session(row.id, db, 1, 1, current_user)
