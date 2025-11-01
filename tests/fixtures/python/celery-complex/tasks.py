"""Complex Celery tasks with chains, groups, chords, and advanced patterns."""

from celery import Celery, Task, group, chain, chord, signature
from celery.utils.log import get_task_logger
from celery.exceptions import Retry, MaxRetriesExceededError
from celery.result import AsyncResult, GroupResult
from celery.signals import (
    task_prerun, task_postrun, task_failure, task_success,
    task_retry, task_revoked, before_task_publish
)
from kombu import Queue, Exchange
from datetime import datetime, timedelta
import time
import random
import requests
from typing import List, Dict, Any, Optional
import redis
import json
from functools import wraps

logger = get_task_logger(__name__)

# Celery app configuration
app = Celery('complex_tasks')
app.config_from_object('celeryconfig')

# Custom exchanges and queues
default_exchange = Exchange('default', type='direct')
priority_exchange = Exchange('priority', type='topic')
dlx_exchange = Exchange('dlx', type='fanout')

app.conf.task_routes = {
    'tasks.critical_task': {'queue': 'critical', 'routing_key': 'critical'},
    'tasks.data_pipeline_*': {'queue': 'pipeline', 'routing_key': 'pipeline.*'},
    'tasks.ml_*': {'queue': 'ml', 'routing_key': 'ml.*'},
    'tasks.io_*': {'queue': 'io', 'routing_key': 'io.*'}
}

app.conf.task_queues = (
    Queue('default', exchange=default_exchange, routing_key='default'),
    Queue('critical', exchange=priority_exchange, routing_key='critical', priority=10),
    Queue('pipeline', exchange=priority_exchange, routing_key='pipeline.*'),
    Queue('ml', exchange=priority_exchange, routing_key='ml.*'),
    Queue('io', exchange=default_exchange, routing_key='io'),
    Queue('dlq', exchange=dlx_exchange, routing_key='failed'),
)

# Redis client for distributed locking
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)


# Custom task base class with advanced features
class BaseTaskWithRetry(Task):
    """Base task with automatic retry and monitoring."""

    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    track_started = True
    acks_late = True
    reject_on_worker_lost = True

    def before_start(self, task_id, args, kwargs):
        """Called before task execution starts."""
        logger.info(f"Starting task {self.name} with ID {task_id}")
        # Store task metadata in Redis
        redis_client.hset(
            f"task:{task_id}",
            mapping={
                'name': self.name,
                'started_at': datetime.now().isoformat(),
                'args': json.dumps(args),
                'kwargs': json.dumps(kwargs)
            }
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Called on successful task completion."""
        logger.info(f"Task {self.name} completed successfully")
        # Update task metadata
        redis_client.hset(
            f"task:{task_id}",
            'completed_at', datetime.now().isoformat()
        )
        redis_client.expire(f"task:{task_id}", 3600)  # Keep for 1 hour

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        logger.error(f"Task {self.name} failed: {exc}")
        # Send to dead letter queue
        send_to_dlq.delay(task_id, self.name, str(exc))

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Retrying task {self.name} due to {exc}")


# Decorator for distributed locking
def with_lock(lock_name, timeout=30):
    """Ensure only one instance of task runs at a time."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            lock_key = f"lock:{lock_name}"
            lock = redis_client.set(
                lock_key, "1",
                nx=True,  # Only set if doesn't exist
                ex=timeout  # Expire after timeout
            )
            if not lock:
                raise Retry(f"Could not acquire lock for {lock_name}", countdown=5)
            try:
                return func(*args, **kwargs)
            finally:
                redis_client.delete(lock_key)
        return wrapper
    return decorator


# Decorator for rate limiting
def rate_limit(key, limit, window=60):
    """Rate limit task execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            pipe = redis_client.pipeline()
            now = time.time()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.zcount(key, now - window, now)
            pipe.expire(key, window + 1)
            results = pipe.execute()

            current_count = results[2]
            if current_count > limit:
                raise Retry(f"Rate limit exceeded for {key}", countdown=window)

            return func(*args, **kwargs)
        return wrapper
    return decorator


# Critical task with monitoring
@app.task(base=BaseTaskWithRetry, bind=True, name='tasks.critical_task')
@with_lock('critical_task')
def critical_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Critical task that must not fail."""
    try:
        # Simulate critical processing
        logger.info(f"Processing critical data: {data}")
        time.sleep(2)

        if random.random() < 0.1:  # 10% chance of transient failure
            raise Exception("Transient error occurred")

        result = {
            'status': 'success',
            'processed_at': datetime.now().isoformat(),
            'task_id': self.request.id
        }
        return result

    except Exception as exc:
        logger.error(f"Critical task failed: {exc}")
        raise self.retry(exc=exc, countdown=2**self.request.retries)


# Data pipeline tasks
@app.task(name='tasks.data_pipeline_extract')
@rate_limit('pipeline:extract', limit=100, window=60)
def data_pipeline_extract(source: str, batch_size: int = 1000) -> List[Dict]:
    """Extract data from source."""
    logger.info(f"Extracting from {source} with batch size {batch_size}")

    # Simulate data extraction
    data = []
    for i in range(batch_size):
        data.append({
            'id': i,
            'source': source,
            'timestamp': datetime.now().isoformat(),
            'value': random.random() * 100
        })

    time.sleep(1)  # Simulate IO
    return data


@app.task(name='tasks.data_pipeline_transform')
def data_pipeline_transform(data: List[Dict]) -> List[Dict]:
    """Transform extracted data."""
    logger.info(f"Transforming {len(data)} records")

    transformed = []
    for record in data:
        # Complex transformation logic
        transformed_record = {
            **record,
            'normalized_value': record['value'] / 100,
            'category': 'high' if record['value'] > 50 else 'low',
            'processed': True
        }
        transformed.append(transformed_record)

    time.sleep(0.5)  # Simulate processing
    return transformed


@app.task(name='tasks.data_pipeline_validate')
def data_pipeline_validate(data: List[Dict]) -> tuple:
    """Validate transformed data."""
    logger.info(f"Validating {len(data)} records")

    valid = []
    invalid = []

    for record in data:
        if record.get('normalized_value') is not None:
            valid.append(record)
        else:
            invalid.append(record)

    if invalid:
        logger.warning(f"Found {len(invalid)} invalid records")

    return valid, invalid


@app.task(name='tasks.data_pipeline_load')
def data_pipeline_load(data: List[Dict], destination: str) -> Dict:
    """Load data to destination."""
    logger.info(f"Loading {len(data)} records to {destination}")

    # Simulate database write
    time.sleep(2)

    return {
        'destination': destination,
        'records_loaded': len(data),
        'timestamp': datetime.now().isoformat()
    }


@app.task(name='tasks.data_pipeline_orchestrator')
def data_pipeline_orchestrator(sources: List[str], destination: str) -> Dict:
    """Orchestrate entire data pipeline with parallel processing."""

    # Create workflow with groups and chains
    workflows = []

    for source in sources:
        # Chain for each source: extract -> transform -> validate
        workflow = chain(
            data_pipeline_extract.s(source),
            data_pipeline_transform.s(),
            data_pipeline_validate.s(),
            data_pipeline_load.s(destination)
        )
        workflows.append(workflow)

    # Run all source workflows in parallel
    job = group(*workflows)()

    # Wait for completion (with timeout)
    results = job.get(timeout=300)

    return {
        'sources_processed': len(sources),
        'results': results,
        'completed_at': datetime.now().isoformat()
    }


# Machine learning tasks with chord pattern
@app.task(name='tasks.ml_preprocess')
def ml_preprocess(data_id: str) -> np.ndarray:
    """Preprocess data for ML model."""
    logger.info(f"Preprocessing data {data_id}")

    # Simulate data loading and preprocessing
    import numpy as np
    data = np.random.rand(1000, 50)  # 1000 samples, 50 features

    # Normalization
    mean = data.mean(axis=0)
    std = data.std(axis=0)
    normalized = (data - mean) / std

    return normalized.tolist()


@app.task(name='tasks.ml_train_model')
def ml_train_model(data: List, model_type: str) -> Dict:
    """Train ML model on preprocessed data."""
    logger.info(f"Training {model_type} model")

    import numpy as np
    data = np.array(data)

    # Simulate model training
    time.sleep(5)  # Training time

    model_metrics = {
        'accuracy': random.uniform(0.7, 0.95),
        'precision': random.uniform(0.7, 0.95),
        'recall': random.uniform(0.7, 0.95),
        'f1_score': random.uniform(0.7, 0.95)
    }

    return {
        'model_type': model_type,
        'metrics': model_metrics,
        'training_samples': len(data)
    }


@app.task(name='tasks.ml_evaluate')
def ml_evaluate(model_results: List[Dict]) -> Dict:
    """Evaluate and select best model."""
    logger.info(f"Evaluating {len(model_results)} models")

    # Select best model based on F1 score
    best_model = max(model_results, key=lambda x: x['metrics']['f1_score'])

    return {
        'best_model': best_model['model_type'],
        'metrics': best_model['metrics'],
        'all_results': model_results
    }


@app.task(name='tasks.ml_pipeline')
def ml_pipeline(data_id: str, model_types: List[str]) -> Dict:
    """Complete ML pipeline with chord pattern."""

    # Preprocess data
    preprocessing = ml_preprocess.s(data_id)

    # Train multiple models in parallel
    training_tasks = [
        ml_train_model.s(model_type=model_type)
        for model_type in model_types
    ]

    # Use chord: parallel training followed by evaluation
    workflow = chord(
        preprocessing | group(*training_tasks)
    )(ml_evaluate.s())

    result = workflow.get(timeout=300)
    return result


# Periodic task with beat scheduler
@app.task(name='tasks.cleanup_old_records')
def cleanup_old_records() -> Dict:
    """Periodic cleanup task."""
    cutoff_date = datetime.now() - timedelta(days=30)
    logger.info(f"Cleaning records older than {cutoff_date}")

    # Simulate cleanup
    deleted_count = random.randint(100, 1000)

    return {
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.isoformat()
    }


# Beat schedule configuration
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-old-records': {
        'task': 'tasks.cleanup_old_records',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'options': {'queue': 'maintenance'}
    },
    'hourly-health-check': {
        'task': 'tasks.health_check',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'expires': 300}  # Expire after 5 minutes
    },
    'generate-daily-report': {
        'task': 'tasks.generate_report',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday 9 AM
        'args': ('weekly',),
        'kwargs': {'recipients': ['admin@example.com']}
    }
}


# Complex workflow with error handling
@app.task(bind=True, name='tasks.complex_workflow')
def complex_workflow(self, order_id: str) -> Dict:
    """Complex workflow with conditional logic and error handling."""

    try:
        # Step 1: Validate order
        validation = validate_order.apply_async(
            args=[order_id],
            queue='critical',
            priority=10
        )

        if not validation.get(timeout=30):
            raise ValueError(f"Order {order_id} validation failed")

        # Step 2: Parallel processing
        parallel_tasks = group(
            check_inventory.s(order_id),
            calculate_shipping.s(order_id),
            apply_discounts.s(order_id)
        ).apply_async()

        results = parallel_tasks.get(timeout=60)

        # Step 3: Conditional logic based on results
        inventory_status = results[0]
        if not inventory_status['available']:
            # Trigger backorder workflow
            backorder_workflow = chain(
                notify_customer.s(order_id, 'backorder'),
                create_backorder.s(order_id),
                schedule_restock.s(inventory_status['missing_items'])
            ).apply_async()
            return {
                'status': 'backordered',
                'order_id': order_id,
                'backorder_task': backorder_workflow.id
            }

        # Step 4: Process payment
        payment_result = process_payment.apply_async(
            args=[order_id],
            queue='critical',
            retry_policy={
                'max_retries': 5,
                'interval_start': 1,
                'interval_step': 2,
                'interval_max': 30
            }
        ).get(timeout=120)

        if not payment_result['success']:
            # Handle payment failure
            handle_payment_failure.delay(order_id, payment_result['error'])
            return {
                'status': 'payment_failed',
                'order_id': order_id,
                'error': payment_result['error']
            }

        # Step 5: Finalize order
        finalization = chain(
            generate_invoice.s(order_id),
            send_confirmation_email.s(order_id),
            trigger_fulfillment.s(order_id)
        ).apply_async()

        return {
            'status': 'completed',
            'order_id': order_id,
            'finalization_task': finalization.id,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"Complex workflow failed for order {order_id}: {exc}")
        # Compensating transaction
        rollback_order.delay(order_id)
        raise self.retry(exc=exc, countdown=60)


# Helper tasks for complex workflow
@app.task(name='tasks.validate_order')
def validate_order(order_id: str) -> bool:
    """Validate order details."""
    # Validation logic
    return True


@app.task(name='tasks.check_inventory')
def check_inventory(order_id: str) -> Dict:
    """Check inventory availability."""
    return {
        'available': random.choice([True, False]),
        'missing_items': ['item1', 'item2'] if random.choice([True, False]) else []
    }


@app.task(name='tasks.calculate_shipping')
def calculate_shipping(order_id: str) -> Dict:
    """Calculate shipping costs."""
    return {
        'cost': random.uniform(5, 50),
        'estimated_days': random.randint(2, 7)
    }


@app.task(name='tasks.apply_discounts')
def apply_discounts(order_id: str) -> Dict:
    """Apply applicable discounts."""
    return {
        'discount_amount': random.uniform(0, 20),
        'discount_codes': ['SAVE10']
    }


@app.task(name='tasks.process_payment')
def process_payment(order_id: str) -> Dict:
    """Process payment."""
    success = random.choice([True, True, True, False])  # 75% success rate
    return {
        'success': success,
        'transaction_id': f"txn_{order_id}_{int(time.time())}",
        'error': None if success else "Insufficient funds"
    }


# Task for dead letter queue
@app.task(name='tasks.send_to_dlq')
def send_to_dlq(task_id: str, task_name: str, error: str) -> None:
    """Send failed task to dead letter queue."""
    dlq_message = {
        'task_id': task_id,
        'task_name': task_name,
        'error': error,
        'timestamp': datetime.now().isoformat()
    }

    # Store in Redis DLQ
    redis_client.lpush('dlq:tasks', json.dumps(dlq_message))
    redis_client.expire('dlq:tasks', 86400 * 7)  # Keep for 7 days


# Signal handlers for monitoring
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kw):
    """Log task start."""
    logger.info(f"Task {task.name} starting with ID {task_id}")


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Log task success."""
    logger.info(f"Task {sender.name} completed successfully with result: {result}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Handle task failure."""
    logger.error(f"Task {sender.name} failed with exception: {exception}")
    # Send alert
    send_alert.delay(f"Task {sender.name} failed", str(exception))


@app.task(name='tasks.send_alert')
def send_alert(subject: str, message: str) -> None:
    """Send alert notification."""
    logger.warning(f"ALERT: {subject} - {message}")
    # Would send actual notification (email, Slack, etc.)


# Canvas patterns examples
def create_map_reduce_workflow(data_chunks: List[List], reducer_func):
    """Create map-reduce pattern with Celery canvas."""

    # Map phase: process each chunk in parallel
    map_tasks = group(
        process_chunk.s(chunk) for chunk in data_chunks
    )

    # Reduce phase: combine results
    reduce_task = reducer_func.s()

    # Create workflow
    workflow = chain(map_tasks, reduce_task)
    return workflow


@app.task
def process_chunk(chunk: List) -> Any:
    """Process a single data chunk."""
    return sum(chunk)  # Example processing


@app.task
def combine_results(results: List) -> Any:
    """Combine results from map phase."""
    return sum(results)  # Example reduction


# Priority queue task
@app.task(name='tasks.priority_task', queue='critical', priority=10)
def priority_task(data: Dict) -> Dict:
    """High priority task."""
    logger.info(f"Processing priority task with data: {data}")
    return {'status': 'completed', 'priority': 'high'}