"""Celery configuration shared by the API, workers and Flower."""

from __future__ import annotations

import os

from celery import Celery


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "nexova",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["async_jobs"],
)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    result_expires=86_400,
    task_acks_late=True,
    task_default_queue="nexova",
    task_reject_on_worker_lost=True,
    task_serializer="json",
    task_send_sent_event=True,
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    worker_send_task_events=True,
    worker_prefetch_multiplier=1,
)
