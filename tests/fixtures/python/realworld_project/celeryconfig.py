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
from datetime import timedelta

app = Celery('realworld')

# Celery Beat Schedule Configuration
app.conf.beat_schedule = {
    # 1. Crontab: Daily backup at midnight (SECURITY: sensitive data export)
    'daily-backup': {
        'task': 'tasks.celery_tasks.scheduled_backup',
        'schedule': crontab(hour=0, minute=0),  # Every day at 00:00
    },

    # 2. Crontab: Hourly cleanup (standard maintenance)
    'hourly-cleanup': {
        'task': 'tasks.celery_tasks.cleanup_old_data',
        'schedule': crontab(minute=0),  # Every hour
        'args': (7,),  # Delete data older than 7 days
    },

    # 3. Crontab: Weekly report on Monday morning
    'weekly-report': {
        'task': 'tasks.celery_tasks.generate_report',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday 09:00
        'args': ('weekly_summary',),
    },

    # 4. Interval: Every 5 minutes (SECURITY RISK: too frequent for admin task)
    'frequent-admin-check': {
        'task': 'tasks.celery_tasks.admin_action',
        'schedule': schedule(run_every=300.0),  # 300 seconds = 5 minutes
        'kwargs': {'action_type': 'health_check', 'target_id': None},
    },

    # 5. Interval: Every 30 seconds (DOS RISK: very high frequency)
    'high-frequency-metrics': {
        'task': 'tasks.celery_tasks.process_metrics',
        'schedule': schedule(run_every=30.0),  # Every 30 seconds
    },

    # 6. Direct number interval (legacy pattern - seconds as int)
    'legacy-interval-task': {
        'task': 'tasks.celery_tasks.send_sms',
        'schedule': 60,  # Every 60 seconds
        'args': ('+1234567890', 'Periodic notification'),
    },

    # 7. Crontab: First day of month (monthly billing)
    'monthly-billing': {
        'task': 'tasks.celery_tasks.process_payment',
        'schedule': crontab(hour=1, minute=0, day_of_month=1),  # 1st of month at 01:00
        'kwargs': {'user_id': 'all', 'amount': 0, 'currency': 'USD'},
    },

    # 8. Crontab: Weekdays only (business hours task)
    'weekday-emails': {
        'task': 'tasks.celery_tasks.send_email',
        'schedule': crontab(hour=10, minute=0, day_of_week='1-5'),  # Mon-Fri at 10:00
    },

    # 9. Crontab: Every 15 minutes (frequent task)
    'quarter-hour-sync': {
        'task': 'tasks.celery_tasks.fetch_external_api',
        'schedule': crontab(minute='*/15'),  # */15 = every 15 minutes
        'args': ('https://api.example.com/data',),
    },

    # 10. Interval: Long-running nightly task
    'nightly-export': {
        'task': 'tasks.celery_tasks.long_running_export',
        'schedule': schedule(run_every=86400.0),  # 86400 seconds = 24 hours
        'args': ('export_id_123', 'json'),
    },

    # 11. Crontab: Weekend task only
    'weekend-maintenance': {
        'task': 'tasks.celery_tasks.comprehensive_task',
        'schedule': crontab(hour=3, minute=0, day_of_week='6,0'),  # Sat=6, Sun=0 at 03:00
        'kwargs': {'user_id': 'system', 'action': 'maintenance', 'data': {}},
    },

    # 12. Crontab: Specific month task (end of year cleanup)
    'year-end-cleanup': {
        'task': 'tasks.celery_tasks.cleanup_old_data',
        'schedule': crontab(hour=0, minute=0, day_of_month=31, month_of_year=12),  # Dec 31 at 00:00
        'args': (365,),  # Delete data older than 1 year
    },
}

# Pattern 2: @periodic_task decorator (deprecated but still in use)
# NOTE: These would normally be in a tasks file, but shown here for extraction testing
from celery.task import periodic_task

@periodic_task(run_every=3600)
def deprecated_hourly_task():
    """Hourly task using deprecated @periodic_task decorator (3600 seconds = 1 hour)."""
    pass

@periodic_task(run_every=86400)
def deprecated_daily_task():
    """Daily task using deprecated @periodic_task decorator (86400 seconds = 24 hours)."""
    pass

# Security Patterns Demonstrated:
# - daily-backup: Scheduled sensitive data export (backup task)
# - frequent-admin-check: Admin task running every 5 minutes (privilege escalation risk if exposed)
# - high-frequency-metrics: Task every 30 seconds (DoS risk - resource exhaustion)
# - monthly-billing: Automated payment processing (critical financial operation)
# - year-end-cleanup: Automated data deletion (data loss risk if misconfigured)
