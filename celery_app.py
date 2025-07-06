"""
Celery Application Configuration

Production-ready task queue for replacing threading-based background services.
Provides durability, retries, monitoring, and horizontal scaling capabilities.
"""

import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue
from config import config

# Create Celery app instance
app = Celery('futures_trading_log')

# Configure Celery
app.conf.update(
    # Broker settings (Redis)
    broker_url=config.redis_url or 'redis://localhost:6379/1',
    result_backend=config.redis_url or 'redis://localhost:6379/1',
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'tasks.file_processing.*': {'queue': 'file_processing'},
        'tasks.gap_filling.*': {'queue': 'gap_filling'},
        'tasks.position_building.*': {'queue': 'position_building'},
        'tasks.cache_maintenance.*': {'queue': 'cache_maintenance'},
    },
    
    # Queue definitions
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('file_processing', routing_key='file_processing'),
        Queue('gap_filling', routing_key='gap_filling'),
        Queue('position_building', routing_key='position_building'),
        Queue('cache_maintenance', routing_key='cache_maintenance'),
    ),
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Results settings
    result_expires=3600,  # 1 hour
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'fill-recent-gaps': {
            'task': 'tasks.gap_filling.fill_recent_gaps',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
            'options': {'queue': 'gap_filling'}
        },
        'fill-extended-gaps': {
            'task': 'tasks.gap_filling.fill_extended_gaps',
            'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
            'options': {'queue': 'gap_filling'}
        },
        'check-for-new-files': {
            'task': 'tasks.file_processing.check_for_new_files',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
            'options': {'queue': 'file_processing'}
        },
        'cache-maintenance': {
            'task': 'tasks.cache_maintenance.cleanup_expired_cache',
            'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
            'options': {'queue': 'cache_maintenance'}
        },
        'position-rebuild-check': {
            'task': 'tasks.position_building.check_rebuild_needed',
            'schedule': crontab(minute=0, hour=1),  # Daily at 1 AM
            'options': {'queue': 'position_building'}
        }
    }
)

# Auto-discover tasks
app.autodiscover_tasks(['tasks'])

# Celery signal handlers for monitoring
@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')
    return 'Debug task completed'


if __name__ == '__main__':
    app.start()