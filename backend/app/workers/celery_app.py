from celery import Celery
from app.core.config import settings

redis_url = settings.REDIS_URL or "redis://localhost:6379/0"

celery_app = Celery(
    "prepify",
    broker=redis_url,
    backend=redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app.workers"])
