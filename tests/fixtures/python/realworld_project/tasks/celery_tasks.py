"""
Celery task definitions for background processing.

Test fixture for extract_celery_tasks().
Covers @task, @shared_task, @app.task decorators with various security configurations.
"""

from celery import shared_task
from celery_app import app


# 1. Basic shared_task with no configuration (SECURITY RISKS: no limits, default pickle serializer)
@shared_task
def send_email(user_id, subject, body):
    """Send email notification - NO rate limit, NO time limit, DEFAULT serializer (pickle = RCE)."""
    pass


# 2. Task with bind=True (task instance access)
@shared_task(bind=True)
def retry_task(self, data):
    """Task with self parameter for retry logic."""
    try:
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc


# 3. Task with JSON serializer (SAFE - no pickle RCE risk)
@shared_task(serializer='json')
def process_payment(user_id, amount, currency):
    """Payment processing with JSON serializer - SAFE from pickle attacks."""
    pass


# 4. Task with max_retries
@shared_task(max_retries=3)
def fetch_external_api(url):
    """Fetch data from external API with retry limit."""
    pass


# 5. Task with rate_limit (DoS protection)
@shared_task(rate_limit='10/m')
def send_sms(phone_number, message):
    """SMS sending with rate limit - 10 per minute."""
    pass


# 6. Task with time_limit (DoS protection)
@shared_task(time_limit=30)
def generate_report(report_id):
    """Report generation with 30-second timeout."""
    pass


# 7. Task with specific queue (privilege separation)
@shared_task(queue='high_priority')
def process_urgent_order(order_id):
    """Urgent order processing in dedicated queue."""
    pass


# 8. Task with all security configurations (BEST PRACTICE)
@shared_task(
    bind=True,
    serializer='json',
    max_retries=3,
    rate_limit='100/m',
    time_limit=60,
    queue='processing'
)
def comprehensive_task(self, user_id, action, data):
    """Comprehensive task with all security configurations."""
    pass


# 9. Task with many arguments (LARGE INJECTION SURFACE)
@shared_task
def complex_data_processing(user_id, source_file, dest_file, options, filters, transformations, metadata):
    """Task with 7 arguments - large injection surface if unvalidated."""
    pass


# 10. Task using @app.task decorator
@app.task
def cleanup_old_data(days_threshold):
    """Cleanup task using app.task decorator."""
    pass


# 11. Task with pickle serializer explicitly set (CRITICAL SECURITY RISK)
@shared_task(serializer='pickle')
def dangerous_task(untrusted_data):
    """Task with PICKLE serializer - CRITICAL RCE VULNERABILITY if data is untrusted."""
    pass


# 12. Task with NO arguments (minimal injection surface)
@shared_task
def scheduled_backup():
    """Scheduled backup with no arguments - minimal risk."""
    pass


# 13. Task with bind + comprehensive config
@shared_task(
    bind=True,
    serializer='json',
    max_retries=5,
    rate_limit='50/h',
    time_limit=120,
    queue='background'
)
def long_running_export(self, export_id, format, filters):
    """Long-running data export with comprehensive configuration."""
    pass


# 14. Task in shared 'default' queue (SECURITY RISK: privilege escalation)
@shared_task(queue='default')
def admin_action(action_type, target_id):
    """Admin action in default queue - may share resources with low-privilege tasks."""
    pass


# 15. Task with msgpack serializer (alternative safe serializer)
@shared_task(serializer='msgpack')
def process_metrics(metric_name, value, timestamp):
    """Process metrics with msgpack serializer."""
    pass


# Security Patterns Demonstrated:
# - dangerous_task: PICKLE serializer = RCE vulnerability
# - send_email, complex_data_processing: NO rate_limit = DoS risk
# - send_email: NO time_limit = infinite execution risk
# - admin_action: 'default' queue = privilege escalation risk
# - complex_data_processing: 7 arguments = large injection surface
# - comprehensive_task, long_running_export: BEST PRACTICE (bind, json, limits, dedicated queue)
# - process_payment, process_metrics: SAFE serializers (json, msgpack)
# - scheduled_backup: Minimal attack surface (no arguments)
