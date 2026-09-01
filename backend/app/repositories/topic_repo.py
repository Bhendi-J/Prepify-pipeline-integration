from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.schemas.topic import TopicCreate, TopicUpdate


def list_by_user_id(db: Session, user_id: int) -> list[Topic]:
    return (
        db.query(Topic)
        .filter(Topic.user_id == user_id)
        .order_by(Topic.name.asc(), Topic.id.asc())
        .all()
    )


def get_by_id(db: Session, topic_id: int, user_id: int | None = None) -> Topic | None:
    query = db.query(Topic).filter(Topic.id == topic_id)
    if user_id is not None:
        query = query.filter(Topic.user_id == user_id)
    return query.first()


def create(db: Session, topic_data: TopicCreate, user_id: int) -> Topic:
    topic = Topic(**topic_data.model_dump(), user_id=user_id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


def update(db: Session, topic: Topic, topic_data: TopicUpdate) -> Topic:
    payload = topic_data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(topic, field, value)

    db.commit()
    db.refresh(topic)
    return topic


def delete(db: Session, topic: Topic) -> None:
    db.delete(topic)
    db.commit()
