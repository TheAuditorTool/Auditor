//! Scheduler module - orchestrates job execution
//!
//! The scheduler is the main entry point for managing jobs. It handles:
//! - Job registration and management
//! - Schedule evaluation
//! - Execution coordination
//! - Persistence

pub mod cron;
pub mod executor;

pub use cron::{CronExpression, presets};
pub use executor::{Executor, ExecutorConfig, ExecutorStats, ExecutionHook};

use crate::job::{Job, JobId, JobFilter, Schedule, ExecutionTrigger, Priority};
use crate::storage::{Storage, JsonStorage};
use crate::{Result, SchedulerError, DEFAULT_STORAGE_FILE};
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::path::Path;

/// Scheduler configuration
#[derive(Debug, Clone)]
pub struct SchedulerConfig {
    /// Storage file path
    pub storage_path: String,
    /// Executor configuration
    pub executor: ExecutorConfig,
    /// Whether to auto-save after changes
    pub auto_save: bool,
    /// Whether to load jobs on startup
    pub load_on_startup: bool,
    /// Maximum jobs to keep in memory
    pub max_jobs: usize,
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            storage_path: DEFAULT_STORAGE_FILE.to_string(),
            executor: ExecutorConfig::default(),
            auto_save: true,
            load_on_startup: true,
            max_jobs: 10000,
        }
    }
}

impl SchedulerConfig {
    /// Create a const default (for static initialization)
    pub const fn default_const() -> Self {
        Self {
            storage_path: String::new(), // Will use DEFAULT_STORAGE_FILE
            executor: ExecutorConfig {
                max_concurrent: 16,
                default_timeout_secs: 300,
                retry_enabled: true,
                retry_delay_secs: 5,
                retry_backoff_multiplier: 2.0,
                max_retry_delay_secs: 3600,
            },
            auto_save: true,
            load_on_startup: true,
            max_jobs: 10000,
        }
    }
}

/// The main scheduler
///
/// Manages jobs and coordinates their execution.
///
/// # Example
///
/// ```rust,no_run
/// use task_scheduler::{Scheduler, Job};
///
/// fn main() -> task_scheduler::Result<()> {
///     let mut scheduler = Scheduler::new("jobs.json")?;
///
///     let job = Job::builder()
///         .name("backup")
///         .schedule("0 2 * * *")
///         .command("backup.sh")
///         .build()?;
///
///     scheduler.add(job)?;
///     scheduler.run_pending()?;
///
///     Ok(())
/// }
/// ```
pub struct Scheduler<S = JsonStorage>
where
    S: Storage,
{
    /// Job storage backend
    storage: S,
    /// In-memory job cache
    jobs: HashMap<JobId, Job>,
    /// Job name to ID index
    name_index: HashMap<String, JobId>,
    /// Executor for running jobs
    executor: Executor,
    /// Configuration
    config: SchedulerConfig,
    /// Whether jobs have been modified since last save
    dirty: bool,
}

impl Scheduler<JsonStorage> {
    /// Create a new scheduler with JSON file storage
    pub fn new(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let storage = JsonStorage::new(path)?;

        Self::with_storage(storage)
    }

    /// Create with default storage path
    pub fn default_path() -> Result<Self> {
        Self::new(DEFAULT_STORAGE_FILE)
    }
}

impl<S> Scheduler<S>
where
    S: Storage,
{
    /// Create scheduler with custom storage backend
    pub fn with_storage(storage: S) -> Result<Self> {
        Self::with_storage_and_config(storage, SchedulerConfig::default())
    }

    /// Create scheduler with custom storage and config
    pub fn with_storage_and_config(storage: S, config: SchedulerConfig) -> Result<Self> {
        let executor = Executor::with_config(config.executor.clone());

        let mut scheduler = Self {
            storage,
            jobs: HashMap::new(),
            name_index: HashMap::new(),
            executor,
            config,
            dirty: false,
        };

        if scheduler.config.load_on_startup {
            scheduler.load()?;
        }

        Ok(scheduler)
    }

    /// Get scheduler configuration
    pub fn config(&self) -> &SchedulerConfig {
        &self.config
    }

    /// Get executor reference
    pub fn executor(&self) -> &Executor {
        &self.executor
    }

    /// Get executor stats
    pub fn stats(&self) -> &ExecutorStats {
        self.executor.stats()
    }

    /// Load jobs from storage
    pub fn load(&mut self) -> Result<usize> {
        let jobs = self.storage.load()?;
        let count = jobs.len();

        self.jobs.clear();
        self.name_index.clear();

        for job in jobs {
            self.name_index.insert(job.name().to_string(), job.id());
            self.jobs.insert(job.id(), job);
        }

        self.dirty = false;
        Ok(count)
    }

    /// Save jobs to storage
    pub fn save(&mut self) -> Result<()> {
        let jobs: Vec<&Job> = self.jobs.values().collect();
        self.storage.save(&jobs)?;
        self.dirty = false;
        Ok(())
    }

    /// Auto-save if enabled and dirty
    fn auto_save(&mut self) -> Result<()> {
        if self.config.auto_save && self.dirty {
            self.save()?;
        }
        Ok(())
    }

    /// Add a new job
    pub fn add(&mut self, job: Job) -> Result<JobId> {
        // Check for duplicate name
        if self.name_index.contains_key(job.name()) {
            return Err(SchedulerError::DuplicateJob(job.name().to_string()));
        }

        // Check capacity
        if self.jobs.len() >= self.config.max_jobs {
            return Err(SchedulerError::validation(
                "capacity",
                format!("maximum {} jobs exceeded", self.config.max_jobs),
            ));
        }

        let id = job.id();
        self.name_index.insert(job.name().to_string(), id);
        self.jobs.insert(id, job);
        self.dirty = true;

        self.auto_save()?;
        Ok(id)
    }

    /// Remove a job by ID
    pub fn remove(&mut self, id: JobId) -> Result<Job> {
        let job = self.jobs.remove(&id).ok_or(SchedulerError::JobNotFound(id))?;
        self.name_index.remove(job.name());
        self.dirty = true;

        self.auto_save()?;
        Ok(job)
    }

    /// Remove a job by name
    pub fn remove_by_name(&mut self, name: &str) -> Result<Job> {
        let id = self.name_index.get(name).copied()
            .ok_or_else(|| SchedulerError::validation("name", format!("job not found: {}", name)))?;
        self.remove(id)
    }

    /// Get a job by ID
    pub fn get(&self, id: JobId) -> Option<&Job> {
        self.jobs.get(&id)
    }

    /// Get a mutable job by ID
    pub fn get_mut(&mut self, id: JobId) -> Option<&mut Job> {
        self.dirty = true;
        self.jobs.get_mut(&id)
    }

    /// Get a job by name
    pub fn get_by_name(&self, name: &str) -> Option<&Job> {
        self.name_index.get(name).and_then(|id| self.jobs.get(id))
    }

    /// Get a mutable job by name
    pub fn get_by_name_mut(&mut self, name: &str) -> Option<&mut Job> {
        self.dirty = true;
        self.name_index.get(name).and_then(|id| self.jobs.get_mut(id))
    }

    /// Check if a job exists
    pub fn contains(&self, id: JobId) -> bool {
        self.jobs.contains_key(&id)
    }

    /// Check if a job with name exists
    pub fn contains_name(&self, name: &str) -> bool {
        self.name_index.contains_key(name)
    }

    /// Get all jobs
    pub fn jobs(&self) -> impl Iterator<Item = &Job> {
        self.jobs.values()
    }

    /// Get all job IDs
    pub fn job_ids(&self) -> impl Iterator<Item = JobId> + '_ {
        self.jobs.keys().copied()
    }

    /// Get job count
    pub fn len(&self) -> usize {
        self.jobs.len()
    }

    /// Check if scheduler is empty
    pub fn is_empty(&self) -> bool {
        self.jobs.is_empty()
    }

    /// Filter jobs
    pub fn filter<'a>(&'a self, filter: &'a JobFilter<'a>) -> impl Iterator<Item = &'a Job> {
        self.jobs.values().filter(move |job| filter.matches(job))
    }

    /// Get jobs by priority
    pub fn by_priority(&self, priority: Priority) -> impl Iterator<Item = &Job> {
        self.jobs.values().filter(move |job| job.priority() == priority)
    }

    /// Get jobs by tag
    pub fn by_tag(&self, tag: &str) -> impl Iterator<Item = &Job> {
        self.jobs.values().filter(move |job| job.tags().contains(tag))
    }

    /// Get enabled jobs
    pub fn enabled(&self) -> impl Iterator<Item = &Job> {
        self.jobs.values().filter(|job| job.is_enabled())
    }

    /// Get pending jobs (ready to run)
    pub fn pending(&self) -> impl Iterator<Item = &Job> {
        self.jobs.values().filter(|job| job.is_ready() && job.is_due())
    }

    /// Run a specific job by ID
    pub fn run(&mut self, id: JobId) -> Result<()> {
        let job = self.jobs.get_mut(&id).ok_or(SchedulerError::JobNotFound(id))?;
        self.executor.execute(job)?;
        self.dirty = true;
        self.auto_save()?;
        Ok(())
    }

    /// Run a job by name
    pub fn run_by_name(&mut self, name: &str) -> Result<()> {
        let id = self.name_index.get(name).copied()
            .ok_or_else(|| SchedulerError::validation("name", format!("job not found: {}", name)))?;
        self.run(id)
    }

    /// Run all pending jobs
    pub fn run_pending(&mut self) -> Result<Vec<JobId>> {
        let pending_ids: Vec<JobId> = self.jobs
            .values()
            .filter(|job| job.is_ready() && job.is_due())
            .map(|job| job.id())
            .collect();

        let mut executed = Vec::new();

        for id in pending_ids {
            if let Some(job) = self.jobs.get_mut(&id) {
                if self.executor.execute(job).is_ok() {
                    executed.push(id);
                }
            }
        }

        if !executed.is_empty() {
            self.dirty = true;
            self.auto_save()?;
        }

        Ok(executed)
    }

    /// Update next run times for all scheduled jobs
    pub fn update_schedules(&mut self) {
        let now = Utc::now();

        for job in self.jobs.values_mut() {
            if !job.is_enabled() {
                continue;
            }

            match job.schedule() {
                Schedule::Cron { expression } => {
                    if let Ok(cron) = CronExpression::parse(expression) {
                        // Update next_run would require mutable access to internal field
                        // This is a simplified version - real impl would set next_run
                        let _ = cron.next_occurrence(now);
                    }
                }
                Schedule::Interval { seconds } => {
                    let _ = seconds; // Would calculate next run based on last_run + interval
                }
                _ => {}
            }
        }
    }

    /// Cancel a running job
    pub fn cancel(&mut self, id: JobId) -> Result<bool> {
        if !self.executor.is_running(id) {
            return Ok(false);
        }

        let cancelled = self.executor.cancel(id);
        if cancelled {
            if let Some(job) = self.jobs.get_mut(&id) {
                job.set_state(crate::job::JobState::Cancelled {
                    cancelled_at: Utc::now(),
                    reason: crate::job::state::CancelReason::UserRequested,
                    run_id: None,
                });
            }
            self.dirty = true;
            self.auto_save()?;
        }

        Ok(cancelled)
    }

    /// Enable a job
    pub fn enable(&mut self, id: JobId) -> Result<()> {
        let job = self.jobs.get_mut(&id).ok_or(SchedulerError::JobNotFound(id))?;
        job.enable();
        self.dirty = true;
        self.auto_save()
    }

    /// Disable a job
    pub fn disable(&mut self, id: JobId) -> Result<()> {
        let job = self.jobs.get_mut(&id).ok_or(SchedulerError::JobNotFound(id))?;
        job.disable();
        self.dirty = true;
        self.auto_save()
    }

    /// Shutdown the scheduler
    pub fn shutdown(&mut self) -> Result<()> {
        self.executor.shutdown();
        self.save()
    }

    /// Get scheduler status summary
    pub fn status(&self) -> SchedulerStatus {
        let stats = self.executor.stats().snapshot();

        SchedulerStatus {
            total_jobs: self.jobs.len(),
            enabled_jobs: self.jobs.values().filter(|j| j.is_enabled()).count(),
            running_jobs: stats.running,
            queued_jobs: stats.queued,
            total_executed: stats.total_executed,
            success_rate: self.executor.stats().success_rate(),
        }
    }
}

/// Scheduler status summary
#[derive(Debug, Clone)]
pub struct SchedulerStatus {
    /// Total number of jobs
    pub total_jobs: usize,
    /// Number of enabled jobs
    pub enabled_jobs: usize,
    /// Currently running jobs
    pub running_jobs: usize,
    /// Jobs in queue
    pub queued_jobs: usize,
    /// Total jobs executed
    pub total_executed: usize,
    /// Success rate (0.0 - 1.0)
    pub success_rate: f64,
}

impl std::fmt::Display for SchedulerStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "Scheduler Status:")?;
        writeln!(f, "  Jobs: {} total, {} enabled", self.total_jobs, self.enabled_jobs)?;
        writeln!(f, "  Running: {}, Queued: {}", self.running_jobs, self.queued_jobs)?;
        writeln!(f, "  Executed: {}, Success Rate: {:.1}%",
            self.total_executed, self.success_rate * 100.0)
    }
}

/// Builder for creating schedulers
pub struct SchedulerBuilder<S: Storage = JsonStorage> {
    storage: Option<S>,
    config: SchedulerConfig,
}

impl SchedulerBuilder<JsonStorage> {
    /// Create a new builder
    pub fn new() -> Self {
        Self {
            storage: None,
            config: SchedulerConfig::default(),
        }
    }

    /// Set storage file path
    pub fn path(mut self, path: impl AsRef<Path>) -> Result<Self> {
        self.storage = Some(JsonStorage::new(path)?);
        Ok(self)
    }
}

impl<S: Storage> SchedulerBuilder<S> {
    /// Use custom storage backend
    pub fn with_storage<NS: Storage>(self, storage: NS) -> SchedulerBuilder<NS> {
        SchedulerBuilder {
            storage: Some(storage),
            config: self.config,
        }
    }

    /// Set configuration
    pub fn config(mut self, config: SchedulerConfig) -> Self {
        self.config = config;
        self
    }

    /// Set auto-save behavior
    pub fn auto_save(mut self, enabled: bool) -> Self {
        self.config.auto_save = enabled;
        self
    }

    /// Set whether to load on startup
    pub fn load_on_startup(mut self, enabled: bool) -> Self {
        self.config.load_on_startup = enabled;
        self
    }

    /// Set maximum jobs
    pub fn max_jobs(mut self, max: usize) -> Self {
        self.config.max_jobs = max;
        self
    }

    /// Build the scheduler
    pub fn build(self) -> Result<Scheduler<S>> {
        let storage = self.storage.ok_or_else(|| {
            SchedulerError::validation("storage", "storage backend not configured")
        })?;

        Scheduler::with_storage_and_config(storage, self.config)
    }
}

impl Default for SchedulerBuilder<JsonStorage> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::storage::MemoryStorage;

    fn test_scheduler() -> Scheduler<MemoryStorage> {
        Scheduler::with_storage(MemoryStorage::new()).unwrap()
    }

    #[test]
    fn test_add_and_get_job() {
        let mut scheduler = test_scheduler();

        let job = Job::builder()
            .name("test-job")
            .manual()
            .build()
            .unwrap();

        let id = scheduler.add(job).unwrap();

        assert!(scheduler.contains(id));
        assert!(scheduler.contains_name("test-job"));
        assert_eq!(scheduler.len(), 1);
    }

    #[test]
    fn test_duplicate_name_rejected() {
        let mut scheduler = test_scheduler();

        let job1 = Job::builder().name("duplicate").manual().build().unwrap();
        let job2 = Job::builder().name("duplicate").manual().build().unwrap();

        scheduler.add(job1).unwrap();
        let result = scheduler.add(job2);

        assert!(result.is_err());
    }

    #[test]
    fn test_remove_job() {
        let mut scheduler = test_scheduler();

        let job = Job::builder().name("to-remove").manual().build().unwrap();
        let id = scheduler.add(job).unwrap();

        let removed = scheduler.remove(id).unwrap();
        assert_eq!(removed.name(), "to-remove");
        assert!(!scheduler.contains(id));
        assert!(scheduler.is_empty());
    }

    #[test]
    fn test_filter_jobs() {
        let mut scheduler = test_scheduler();

        scheduler.add(Job::builder().name("job1").tag("important").build().unwrap()).unwrap();
        scheduler.add(Job::builder().name("job2").tag("routine").build().unwrap()).unwrap();
        scheduler.add(Job::builder().name("job3").tag("important").build().unwrap()).unwrap();

        let important: Vec<_> = scheduler.by_tag("important").collect();
        assert_eq!(important.len(), 2);
    }

    #[test]
    fn test_scheduler_status() {
        let scheduler = test_scheduler();
        let status = scheduler.status();

        assert_eq!(status.total_jobs, 0);
        assert_eq!(status.enabled_jobs, 0);
    }
}
