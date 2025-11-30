"""
Celery Beat periodic task configuration for testing extract_celery_beat_schedules().

Test fixture demonstrating:
- app.conf.beat_schedule dictionary definitions
- crontab() expressions (minute, hour, day_of_week, day_of_month, month_of_year)
- schedule() interval expressions
- @periodic_task decorator (deprecated)
"""

from celery import Celery
from celery.schedules import crontab, schedule

app = Celery("realworld")


app.conf.beat_schedule = {
    "daily-backup": {
        "task": "tasks.celery_tasks.scheduled_backup",
        "schedule": crontab(hour=0, minute=0),
    },
    "hourly-cleanup": {
        "task": "tasks.celery_tasks.cleanup_old_data",
        "schedule": crontab(minute=0),
        "args": (7,),
    },
    "weekly-report": {
        "task": "tasks.celery_tasks.generate_report",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
        "args": ("weekly_summary",),
    },
    "frequent-admin-check": {
        "task": "tasks.celery_tasks.admin_action",
        "schedule": schedule(run_every=300.0),
        "kwargs": {"action_type": "health_check", "target_id": None},
    },
    "high-frequency-metrics": {
        "task": "tasks.celery_tasks.process_metrics",
        "schedule": schedule(run_every=30.0),
    },
    "legacy-interval-task": {
        "task": "tasks.celery_tasks.send_sms",
        "schedule": 60,
        "args": ("+1234567890", "Periodic notification"),
    },
    "monthly-billing": {
        "task": "tasks.celery_tasks.process_payment",
        "schedule": crontab(hour=1, minute=0, day_of_month=1),
        "kwargs": {"user_id": "all", "amount": 0, "currency": "USD"},
    },
    "weekday-emails": {
        "task": "tasks.celery_tasks.send_email",
        "schedule": crontab(hour=10, minute=0, day_of_week="1-5"),
    },
    "quarter-hour-sync": {
        "task": "tasks.celery_tasks.fetch_external_api",
        "schedule": crontab(minute="*/15"),
        "args": ("https://api.example.com/data",),
    },
    "nightly-export": {
        "task": "tasks.celery_tasks.long_running_export",
        "schedule": schedule(run_every=86400.0),
        "args": ("export_id_123", "json"),
    },
    "weekend-maintenance": {
        "task": "tasks.celery_tasks.comprehensive_task",
        "schedule": crontab(hour=3, minute=0, day_of_week="6,0"),
        "kwargs": {"user_id": "system", "action": "maintenance", "data": {}},
    },
    "year-end-cleanup": {
        "task": "tasks.celery_tasks.cleanup_old_data",
        "schedule": crontab(hour=0, minute=0, day_of_month=31, month_of_year=12),
        "args": (365,),
    },
}


from celery.task import periodic_task


@periodic_task(run_every=3600)
def deprecated_hourly_task():
    """Hourly task using deprecated @periodic_task decorator (3600 seconds = 1 hour)."""
    pass


@periodic_task(run_every=86400)
def deprecated_daily_task():
    """Daily task using deprecated @periodic_task decorator (86400 seconds = 24 hours)."""
    pass
