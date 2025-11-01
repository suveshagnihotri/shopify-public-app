"""
Celery configuration for background tasks
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Create Celery instance
# In Docker, use service name 'redis', locally use 'localhost'
default_redis = 'redis://redis:6379/0' if os.getenv('FLASK_ENV') == 'production' else 'redis://localhost:6379/0'
redis_url = os.getenv('REDIS_URL', default_redis)
celery = Celery(
    'shopify_app',
    broker=redis_url,
    backend=redis_url,
    include=['tasks']
)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Optional configuration for production
if os.getenv('FLASK_ENV') == 'production':
    celery.conf.update(
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=10,
    )
