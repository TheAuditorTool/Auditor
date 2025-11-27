"""Celery task extraction test fixture."""

from datetime import datetime, timedelta

from celery import Celery
from celery.schedules import crontab

app = Celery('tasks', broker='redis://localhost:6379/0')


@app.task
def add(x, y):
    """Simple addition task."""
    return x + y


@app.task(bind=True, max_retries=3)
def send_email(self, to, subject, body):
    """Send email task with retry."""
    try:
        # Simulate sending email
        print(f"Sending email to {to}")
        return {'status': 'sent', 'to': to}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc


@app.task(rate_limit='10/m')
def process_data(data_id):
    """Process data with rate limiting."""
    # Process the data
    return {'processed': data_id}


@app.task(bind=True, name='tasks.custom_task')
def custom_named_task(self, param):
    """Task with custom name."""
    return f"Processed: {param}"


# Task invocations
def trigger_tasks():
    """Trigger various tasks."""
    # Simple delay call
    add.delay(4, 4)

    # Apply async with kwargs
    send_email.apply_async(
        args=['user@example.com', 'Hello', 'Message body'],
        countdown=10
    )

    # Another delay call
    process_data.delay('data_123')

    # Apply async with eta
    custom_named_task.apply_async(
        args=['test'],
        eta=datetime.now() + timedelta(minutes=5)
    )


# Beat schedule configuration
app.conf.beat_schedule = {
    'add-every-30-seconds': {
        'task': 'tasks.add',
        'schedule': 30.0,
        'args': (16, 16)
    },
    'send-report-monday-morning': {
        'task': 'tasks.send_email',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),
        'kwargs': {
            'to': 'admin@example.com',
            'subject': 'Weekly Report',
            'body': 'Report content'
        }
    },
    'process-hourly': {
        'task': 'tasks.process_data',
        'schedule': crontab(minute=0),
        'args': ('hourly_batch',)
    }
}
