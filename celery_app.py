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
        'tasks.validation_tasks.*': {'queue': 'validation'},
    },

    # Queue definitions
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('file_processing', routing_key='file_processing'),
        Queue('gap_filling', routing_key='gap_filling'),
        Queue('position_building', routing_key='position_building'),
        Queue('cache_maintenance', routing_key='cache_maintenance'),
        Queue('validation', routing_key='validation'),
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
        # Fill recent gaps during market hours (6 AM - 6 PM CT = 12-00 UTC)
        # Futures markets trade nearly 24/5, but focus on peak hours to minimize API usage
        'fill-recent-gaps': {
            'task': 'tasks.gap_filling.fill_recent_gaps',
            'schedule': crontab(minute='*/15', hour='12-23,0'),  # Every 15 min during market hours
            'options': {'queue': 'gap_filling'}
        },
        # Extended gap filling during off-peak hours to spread API load
        'fill-extended-gaps': {
            'task': 'tasks.gap_filling.fill_extended_gaps',
            'schedule': crontab(minute=0, hour='2,6,10,14,18,22'),  # Every 4 hours at specific times
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
        },
        'validate-all-positions': {
            'task': 'tasks.validation_tasks.validate_all_positions_task',
            'schedule': crontab(minute=0, hour=3),  # Daily at 3 AM
            'args': (None, 7, True),  # status=None, days_back=7, auto_repair=True
            'options': {'queue': 'validation'}
        },
        'validate-recent-positions': {
            'task': 'tasks.validation_tasks.validate_recent_positions_task',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes
            'args': (2, True),  # hours=2, auto_repair=True
            'options': {'queue': 'validation'}
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