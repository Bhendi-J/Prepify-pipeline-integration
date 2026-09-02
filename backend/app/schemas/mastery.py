from datetime import datetime

from pydantic import BaseModel


class MasteryRead(BaseModel):
    user_id: int
    topic_id: int
    ease_factor: float
    interval_days: int
    next_review_at: datetime
    streak: int

    model_config = {"from_attributes": True}


class DueTopicRead(BaseModel):
    topic_id: int
    name: str
    parent_id: int | None
    ease_factor: float
    interval_days: int
    next_review_at: datetime
    streak: int
