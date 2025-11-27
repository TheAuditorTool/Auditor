"""
Celery task orchestration patterns for testing extract_celery_task_calls().

Test fixture demonstrating:
- task.delay() - simple invocation
- task.apply_async() - advanced invocation with countdown, eta, queue
- chain() - sequential task execution
- group() - parallel task execution
- chord() - parallel with callback
- task.s() / task.si() - task signatures
"""

from celery import chain, chord, group
from tasks.celery_tasks import (
    cleanup_old_data,
    generate_report,
    process_payment,
    send_email,
    send_sms,
)


# 1. Simple .delay() invocation (SECURITY RISK: no validation of user_input)
def trigger_email_notification(user_id, subject, body):
    """Direct task invocation with user-controlled data."""
    send_email.delay(user_id, subject, body)  # 3 arguments


# 2. .apply_async() with countdown (scheduled execution)
def schedule_payment_processing(user_id, amount, currency):
    """Schedule payment processing 60 seconds in the future."""
    process_payment.apply_async(
        args=(user_id, amount, currency),
        countdown=60  # Execute after 60 seconds
    )


# 3. .apply_async() with eta (exact time execution)
def schedule_report_at_time(report_id, eta_datetime):
    """Schedule report generation at exact time."""
    generate_report.apply_async(
        args=(report_id,),
        eta=eta_datetime  # Execute at specific datetime
    )


# 4. .apply_async() with queue override (SECURITY RISK: bypassing rate limits)
def urgent_sms_bypass(phone_number, message):
    """Send SMS via high_priority queue, bypassing default rate limits."""
    send_sms.apply_async(
        args=(phone_number, message),
        queue='high_priority'  # Queue override - potential DoS if abused
    )


# 5. .apply_async() with ALL options (comprehensive invocation)
def comprehensive_task_invocation(order_id):
    """Demonstrate all apply_async options."""
    cleanup_old_data.apply_async(
        args=(order_id,),
        countdown=30,
        eta=None,
        queue='background',
        max_retries=5
    )


# 6. Task signature with .s() (partial application)
def create_task_signature(user_id):
    """Create task signature for later execution."""
    signature = send_email.s(user_id, 'Welcome', 'Hello!')  # Returns signature object
    return signature


# 7. Immutable signature with .si() (no argument modification)
def create_immutable_signature():
    """Create immutable task signature."""
    signature = generate_report.si(123)  # Immutable - args cannot be modified
    return signature


# 8. chain() - sequential task execution (Canvas primitive)
def execute_task_chain(user_id, payment_amount):
    """Execute tasks sequentially: payment -> email -> SMS."""
    task_chain = chain(
        process_payment.s(user_id, payment_amount, 'USD'),
        send_email.s(user_id, 'Payment Success', 'Your payment was processed'),
        send_sms.s('+1234567890', 'Payment complete')
    )
    task_chain.apply_async()


# 9. group() - parallel task execution (Canvas primitive)
def execute_task_group(report_ids):
    """Execute multiple reports in parallel."""
    task_group = group(
        generate_report.s(report_id) for report_id in report_ids
    )
    task_group.apply_async()


# 10. chord() - parallel with callback (Canvas primitive)
def execute_chord_pattern(user_ids):
    """Send emails to multiple users, then send summary SMS."""
    email_tasks = group(
        send_email.s(user_id, 'Newsletter', 'Content') for user_id in user_ids
    )
    callback = send_sms.s('+1234567890', 'All emails sent')

    task_chord = chord(email_tasks)(callback)  # Parallel + callback
    task_chord.apply_async()


# 11. Nested Canvas patterns (COMPLEX: chain of groups)
def complex_canvas_pattern(batch_data):
    """Demonstrate nested Canvas patterns."""
    workflow = chain(
        group(process_payment.s(item['user'], item['amount'], 'USD') for item in batch_data),
        send_sms.s('+1234567890', 'Batch complete')
    )
    workflow.apply_async()


# 12. Module-level task invocation (no function context)
send_email.delay(999, 'System', 'Startup notification')  # Invoked at module load


# 13. task.apply() synchronous execution (testing pattern)
def synchronous_task_execution(user_id):
    """Execute task synchronously for testing."""
    result = send_email.apply(args=(user_id, 'Test', 'Body'))  # Blocks until complete
    return result


# 14. Multiple .delay() calls in same function (INJECTION SURFACE)
def batch_email_sender(user_list):
    """Send emails to multiple users (potential injection if user_list is untrusted)."""
    for user in user_list:
        send_email.delay(user['id'], user['subject'], user['body'])  # Multiple calls
        send_sms.delay(user['phone'], f"Email sent to {user['name']}")


# 15. Mixed invocation types in single function
def mixed_invocation_patterns(user_id, urgent=False):
    """Demonstrate multiple invocation types in one function."""
    # Standard delay
    send_email.delay(user_id, 'Regular', 'Content')

    # Conditional apply_async with queue override
    if urgent:
        send_sms.apply_async(
            args=('+1234567890', 'URGENT'),
            queue='high_priority',
            countdown=0
        )

    # Task signature for deferred execution
    report_sig = generate_report.s(user_id)
    report_sig.apply_async(countdown=300)


# Security Patterns Demonstrated:
# - trigger_email_notification: User-controlled data passed directly to task (injection risk)
# - urgent_sms_bypass: Queue override bypasses rate limits (DoS risk)
# - batch_email_sender: Multiple task calls with untrusted data (amplification risk)
# - execute_task_chain: Chain of tasks can fail at any step (error handling risk)
# - execute_chord_pattern: Callback depends on all parallel tasks (denial of availability)
