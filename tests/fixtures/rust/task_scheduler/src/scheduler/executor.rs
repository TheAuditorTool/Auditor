//! Job executor - handles job execution and lifecycle
//!
//! The executor is responsible for:
//! - Running job handlers
//! - Managing retries
//! - Tracking execution state
//! - Timeout handling

use crate::job::{Job, JobId, JobHandler, JobState, JobResult, ExecutionRecord, ExecutionTrigger};
use crate::{Result, SchedulerError, MAX_CONCURRENT_JOBS};
use chrono::{DateTime, Utc, Duration};
use std::collections::{HashMap, VecDeque};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::time::Instant;

/// Statistics for the executor
#[derive(Debug, Default)]
pub struct ExecutorStats {
    /// Total jobs executed
    pub total_executed: AtomicUsize,
    /// Successful executions
    pub successful: AtomicUsize,
    /// Failed executions
    pub failed: AtomicUsize,
    /// Retried executions
    pub retried: AtomicUsize,
    /// Currently running jobs
    pub running: AtomicUsize,
    /// Jobs in queue
    pub queued: AtomicUsize,
}

impl ExecutorStats {
    /// Create new stats
    pub fn new() -> Self {
        Self::default()
    }

    /// Record a successful execution
    pub fn record_success(&self) {
        self.total_executed.fetch_add(1, Ordering::Relaxed);
        self.successful.fetch_add(1, Ordering::Relaxed);
    }

    /// Record a failed execution
    pub fn record_failure(&self) {
        self.total_executed.fetch_add(1, Ordering::Relaxed);
        self.failed.fetch_add(1, Ordering::Relaxed);
    }

    /// Record a retry
    pub fn record_retry(&self) {
        self.retried.fetch_add(1, Ordering::Relaxed);
    }

    /// Increment running count
    pub fn start_running(&self) {
        self.running.fetch_add(1, Ordering::Relaxed);
    }

    /// Decrement running count
    pub fn stop_running(&self) {
        self.running.fetch_sub(1, Ordering::Relaxed);
    }

    /// Get success rate
    pub fn success_rate(&self) -> f64 {
        let total = self.total_executed.load(Ordering::Relaxed);
        if total == 0 {
            return 1.0;
        }
        self.successful.load(Ordering::Relaxed) as f64 / total as f64
    }

    /// Get snapshot of current stats
    pub fn snapshot(&self) -> StatsSnapshot {
        StatsSnapshot {
            total_executed: self.total_executed.load(Ordering::Relaxed),
            successful: self.successful.load(Ordering::Relaxed),
            failed: self.failed.load(Ordering::Relaxed),
            retried: self.retried.load(Ordering::Relaxed),
            running: self.running.load(Ordering::Relaxed),
            queued: self.queued.load(Ordering::Relaxed),
        }
    }
}

/// Immutable snapshot of executor stats
#[derive(Debug, Clone)]
pub struct StatsSnapshot {
    pub total_executed: usize,
    pub successful: usize,
    pub failed: usize,
    pub retried: usize,
    pub running: usize,
    pub queued: usize,
}

/// Configuration for the executor
#[derive(Debug, Clone)]
pub struct ExecutorConfig {
    /// Maximum concurrent job executions
    pub max_concurrent: usize,
    /// Default timeout in seconds
    pub default_timeout_secs: u64,
    /// Whether to retry on failure
    pub retry_enabled: bool,
    /// Delay between retries in seconds
    pub retry_delay_secs: u64,
    /// Exponential backoff multiplier for retries
    pub retry_backoff_multiplier: f64,
    /// Maximum retry delay in seconds
    pub max_retry_delay_secs: u64,
}

impl Default for ExecutorConfig {
    fn default() -> Self {
        Self {
            max_concurrent: MAX_CONCURRENT_JOBS,
            default_timeout_secs: 300,
            retry_enabled: true,
            retry_delay_secs: 5,
            retry_backoff_multiplier: 2.0,
            max_retry_delay_secs: 3600,
        }
    }
}

impl ExecutorConfig {
    /// Calculate retry delay for given attempt number
    pub fn retry_delay(&self, attempt: u8) -> Duration {
        if attempt == 0 {
            return Duration::seconds(self.retry_delay_secs as i64);
        }

        let delay = self.retry_delay_secs as f64
            * self.retry_backoff_multiplier.powi(attempt as i32);
        let delay = delay.min(self.max_retry_delay_secs as f64);

        Duration::seconds(delay as i64)
    }
}

/// Pending execution in the queue
#[derive(Debug)]
struct PendingExecution {
    job_id: JobId,
    trigger: ExecutionTrigger,
    scheduled_at: DateTime<Utc>,
    attempt: u8,
}

/// Job executor
///
/// Manages the execution of jobs, including queuing, concurrency control,
/// and retry logic.
pub struct Executor {
    /// Configuration
    config: ExecutorConfig,
    /// Execution statistics
    stats: Arc<ExecutorStats>,
    /// Currently running jobs
    running: RwLock<HashMap<JobId, RunningJob>>,
    /// Execution queue
    queue: Mutex<VecDeque<PendingExecution>>,
    /// Shutdown flag
    shutdown: AtomicBool,
}

/// Information about a currently running job
#[derive(Debug)]
struct RunningJob {
    job_id: JobId,
    started_at: Instant,
    record: ExecutionRecord,
}

impl Executor {
    /// Create a new executor with default config
    pub fn new() -> Self {
        Self::with_config(ExecutorConfig::default())
    }

    /// Create executor with custom config
    pub fn with_config(config: ExecutorConfig) -> Self {
        Self {
            config,
            stats: Arc::new(ExecutorStats::new()),
            running: RwLock::new(HashMap::new()),
            queue: Mutex::new(VecDeque::new()),
            shutdown: AtomicBool::new(false),
        }
    }

    /// Get executor statistics
    pub fn stats(&self) -> &ExecutorStats {
        &self.stats
    }

    /// Get configuration
    pub fn config(&self) -> &ExecutorConfig {
        &self.config
    }

    /// Check if executor is shutting down
    pub fn is_shutting_down(&self) -> bool {
        self.shutdown.load(Ordering::Relaxed)
    }

    /// Signal shutdown
    pub fn shutdown(&self) {
        self.shutdown.store(true, Ordering::Relaxed);
    }

    /// Get number of currently running jobs
    pub fn running_count(&self) -> usize {
        self.running.read().unwrap().len()
    }

    /// Get number of queued jobs
    pub fn queue_len(&self) -> usize {
        self.queue.lock().unwrap().len()
    }

    /// Check if executor can accept more jobs
    pub fn can_accept(&self) -> bool {
        !self.is_shutting_down() && self.running_count() < self.config.max_concurrent
    }

    /// Queue a job for execution
    pub fn enqueue(&self, job_id: JobId, trigger: ExecutionTrigger) -> Result<()> {
        if self.is_shutting_down() {
            return Err(SchedulerError::ShuttingDown);
        }

        let pending = PendingExecution {
            job_id,
            trigger,
            scheduled_at: Utc::now(),
            attempt: 0,
        };

        self.queue.lock().unwrap().push_back(pending);
        self.stats.queued.fetch_add(1, Ordering::Relaxed);

        Ok(())
    }

    /// Queue a retry
    pub fn enqueue_retry(&self, job_id: JobId, attempt: u8) -> Result<()> {
        if self.is_shutting_down() {
            return Err(SchedulerError::ShuttingDown);
        }

        let pending = PendingExecution {
            job_id,
            trigger: ExecutionTrigger::Retry { attempt },
            scheduled_at: Utc::now() + self.config.retry_delay(attempt),
            attempt,
        };

        self.queue.lock().unwrap().push_back(pending);
        self.stats.queued.fetch_add(1, Ordering::Relaxed);
        self.stats.record_retry();

        Ok(())
    }

    /// Get next job ready for execution
    pub fn next_ready(&self) -> Option<(JobId, ExecutionTrigger)> {
        let mut queue = self.queue.lock().unwrap();
        let now = Utc::now();

        // Find first job that's ready (scheduled time has passed)
        if let Some(pos) = queue.iter().position(|p| p.scheduled_at <= now) {
            let pending = queue.remove(pos).unwrap();
            self.stats.queued.fetch_sub(1, Ordering::Relaxed);
            return Some((pending.job_id, pending.trigger));
        }

        None
    }

    /// Execute a job synchronously
    ///
    /// This method handles:
    /// - State transitions
    /// - Handler execution
    /// - Result recording
    /// - Error handling
    pub fn execute(&self, job: &mut Job) -> Result<ExecutionRecord> {
        if self.is_shutting_down() {
            return Err(SchedulerError::ShuttingDown);
        }

        let trigger = ExecutionTrigger::Manual;
        self.execute_with_trigger(job, trigger)
    }

    /// Execute a job with specific trigger
    pub fn execute_with_trigger(
        &self,
        job: &mut Job,
        trigger: ExecutionTrigger,
    ) -> Result<ExecutionRecord> {
        // Check if we can run
        if !job.is_enabled() {
            return Err(SchedulerError::validation("enabled", "job is disabled"));
        }

        // Get handler
        let handler = job.handler().ok_or_else(|| {
            SchedulerError::ExecutionError("job has no handler".to_string())
        })?;

        // Start execution
        let mut record = job.start_execution(trigger);
        self.stats.start_running();

        // Track running job
        {
            let running_job = RunningJob {
                job_id: job.id(),
                started_at: Instant::now(),
                record: record.clone(),
            };
            self.running.write().unwrap().insert(job.id(), running_job);
        }

        // Execute handler
        let result = handler.execute();

        // Remove from running
        self.running.write().unwrap().remove(&job.id());
        self.stats.stop_running();

        // Process result
        match result {
            Ok(job_result) => {
                if job_result.success {
                    record.complete(job_result);
                    job.complete_execution(&record);
                    self.stats.record_success();
                } else {
                    let error = job_result
                        .stderr
                        .clone()
                        .unwrap_or_else(|| "handler returned failure".to_string());
                    let retry_count = job.retry_count() + 1;
                    record.fail(error.clone(), retry_count, job.max_retries());
                    job.fail_execution(&error, retry_count);
                    self.stats.record_failure();

                    // Queue retry if applicable
                    if self.config.retry_enabled && job.can_retry() {
                        self.enqueue_retry(job.id(), retry_count)?;
                    }
                }
            }
            Err(e) => {
                let retry_count = job.retry_count() + 1;
                record.fail(e.to_string(), retry_count, job.max_retries());
                job.fail_execution(&e.to_string(), retry_count);
                self.stats.record_failure();

                // Queue retry if applicable
                if self.config.retry_enabled && job.can_retry() {
                    self.enqueue_retry(job.id(), retry_count)?;
                }
            }
        }

        Ok(record)
    }

    /// Cancel a running job
    pub fn cancel(&self, job_id: JobId) -> bool {
        // Note: In a real implementation, this would signal the handler to stop
        // For now, we just remove it from tracking
        self.running.write().unwrap().remove(&job_id).is_some()
    }

    /// Clear the execution queue
    pub fn clear_queue(&self) {
        let mut queue = self.queue.lock().unwrap();
        let count = queue.len();
        queue.clear();
        self.stats.queued.fetch_sub(count, Ordering::Relaxed);
    }

    /// Get IDs of currently running jobs
    pub fn running_jobs(&self) -> Vec<JobId> {
        self.running.read().unwrap().keys().copied().collect()
    }

    /// Check if a specific job is running
    pub fn is_running(&self, job_id: JobId) -> bool {
        self.running.read().unwrap().contains_key(&job_id)
    }
}

impl Default for Executor {
    fn default() -> Self {
        Self::new()
    }
}

/// Trait for custom execution hooks
pub trait ExecutionHook: Send + Sync {
    /// Called before job execution starts
    fn before_execute(&self, job: &Job) {}

    /// Called after job execution completes
    fn after_execute(&self, job: &Job, record: &ExecutionRecord) {}

    /// Called when execution fails
    fn on_failure(&self, job: &Job, error: &SchedulerError) {}

    /// Called when retry is scheduled
    fn on_retry(&self, job: &Job, attempt: u8) {}
}

/// No-op hook implementation
#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpHook;

impl ExecutionHook for NoOpHook {}

/// Logging hook that prints execution events
#[derive(Debug, Clone, Copy, Default)]
pub struct LoggingHook;

impl ExecutionHook for LoggingHook {
    fn before_execute(&self, job: &Job) {
        println!("[EXECUTOR] Starting job: {} ({})", job.name(), job.id());
    }

    fn after_execute(&self, job: &Job, record: &ExecutionRecord) {
        let status = if record.result.as_ref().map(|r| r.success).unwrap_or(false) {
            "SUCCESS"
        } else {
            "FAILURE"
        };
        println!(
            "[EXECUTOR] Finished job: {} ({}) - {}",
            job.name(),
            job.id(),
            status
        );
    }

    fn on_failure(&self, job: &Job, error: &SchedulerError) {
        println!(
            "[EXECUTOR] Job failed: {} ({}) - {}",
            job.name(),
            job.id(),
            error
        );
    }

    fn on_retry(&self, job: &Job, attempt: u8) {
        println!(
            "[EXECUTOR] Scheduling retry {} for job: {} ({})",
            attempt,
            job.name(),
            job.id()
        );
    }
}

/// Builder for creating executors with hooks
pub struct ExecutorBuilder<H: ExecutionHook = NoOpHook> {
    config: ExecutorConfig,
    hook: H,
}

impl ExecutorBuilder<NoOpHook> {
    /// Create a new builder
    pub fn new() -> Self {
        Self {
            config: ExecutorConfig::default(),
            hook: NoOpHook,
        }
    }
}

impl<H: ExecutionHook> ExecutorBuilder<H> {
    /// Set configuration
    pub fn config(mut self, config: ExecutorConfig) -> Self {
        self.config = config;
        self
    }

    /// Set max concurrent jobs
    pub fn max_concurrent(mut self, max: usize) -> Self {
        self.config.max_concurrent = max;
        self
    }

    /// Set default timeout
    pub fn timeout(mut self, secs: u64) -> Self {
        self.config.default_timeout_secs = secs;
        self
    }

    /// Enable or disable retries
    pub fn retries(mut self, enabled: bool) -> Self {
        self.config.retry_enabled = enabled;
        self
    }

    /// Set execution hook
    pub fn with_hook<NH: ExecutionHook>(self, hook: NH) -> ExecutorBuilder<NH> {
        ExecutorBuilder {
            config: self.config,
            hook,
        }
    }

    /// Build the executor
    pub fn build(self) -> Executor {
        Executor::with_config(self.config)
    }
}

impl Default for ExecutorBuilder<NoOpHook> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::job::{Job, CommandHandler};

    #[test]
    fn test_executor_stats() {
        let stats = ExecutorStats::new();
        stats.record_success();
        stats.record_success();
        stats.record_failure();

        assert_eq!(stats.total_executed.load(Ordering::Relaxed), 3);
        assert_eq!(stats.successful.load(Ordering::Relaxed), 2);
        assert_eq!(stats.failed.load(Ordering::Relaxed), 1);
        assert!((stats.success_rate() - 0.666).abs() < 0.01);
    }

    #[test]
    fn test_executor_config_retry_delay() {
        let config = ExecutorConfig {
            retry_delay_secs: 5,
            retry_backoff_multiplier: 2.0,
            max_retry_delay_secs: 60,
            ..Default::default()
        };

        assert_eq!(config.retry_delay(0).num_seconds(), 5);
        assert_eq!(config.retry_delay(1).num_seconds(), 10);
        assert_eq!(config.retry_delay(2).num_seconds(), 20);
        assert_eq!(config.retry_delay(3).num_seconds(), 40);
        assert_eq!(config.retry_delay(4).num_seconds(), 60); // Capped
    }

    #[test]
    fn test_executor_queue() {
        let executor = Executor::new();
        let job_id = JobId::new();

        executor.enqueue(job_id, ExecutionTrigger::Manual).unwrap();
        assert_eq!(executor.queue_len(), 1);

        let (dequeued_id, _) = executor.next_ready().unwrap();
        assert_eq!(dequeued_id, job_id);
        assert_eq!(executor.queue_len(), 0);
    }

    #[test]
    fn test_executor_shutdown() {
        let executor = Executor::new();

        assert!(!executor.is_shutting_down());
        executor.shutdown();
        assert!(executor.is_shutting_down());

        // Should reject new jobs
        let result = executor.enqueue(JobId::new(), ExecutionTrigger::Manual);
        assert!(result.is_err());
    }

    #[test]
    fn test_executor_builder() {
        let executor = ExecutorBuilder::new()
            .max_concurrent(4)
            .timeout(60)
            .retries(false)
            .build();

        assert_eq!(executor.config.max_concurrent, 4);
        assert_eq!(executor.config.default_timeout_secs, 60);
        assert!(!executor.config.retry_enabled);
    }
}
