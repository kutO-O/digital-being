"""Celery application configuration for async task execution."""

from celery import Celery
import os

# Redis connection
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
app = Celery(
    'digital_being',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks.heavy_tick_tasks']
)

# Configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120,  # Hard limit: 2 minutes
    task_soft_time_limit=90,  # Soft limit: 90 seconds
    task_acks_late=True,  # Acknowledge after task completion
    worker_prefetch_multiplier=1,  # One task at a time per worker
    result_expires=3600,  # Results expire after 1 hour
)

if __name__ == '__main__':
    app.start()