//! Job module - core job definitions and builder
//!
//! This module contains:
//! - `Job`: The main job struct
//! - `JobBuilder`: Builder pattern for job construction
//! - `JobId`: Type-safe job identifier

pub mod handler;
pub mod state;

pub use handler::{JobHandler, CommandHandler, ClosureHandler, ChainedHandler, BoxedHandler};
pub use state::{JobState, JobResult, ExecutionRecord, ExecutionTrigger};

use crate::{Result, SchedulerError, MAX_JOB_NAME_LEN, DEFAULT_RETRIES};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::fmt;
use std::hash::{Hash, Hasher};
use uuid::Uuid;

/// Type-safe job identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct JobId(Uuid);

impl JobId {
    /// Create a new random job ID
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }

    /// Create from a UUID
    pub fn from_uuid(uuid: Uuid) -> Self {
        Self(uuid)
    }

    /// Parse from string
    pub fn parse(s: &str) -> Result<Self> {
        Uuid::parse_str(s)
            .map(Self)
            .map_err(|_| SchedulerError::validation("id", format!("invalid UUID: {}", s)))
    }

    /// Get the underlying UUID
    pub fn as_uuid(&self) -> &Uuid {
        &self.0
    }

    /// Convert to string
    pub fn to_string(&self) -> String {
        self.0.to_string()
    }
}

impl Default for JobId {
    fn default() -> Self {
        Self::new()
    }
}

impl fmt::Display for JobId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl From<Uuid> for JobId {
    fn from(uuid: Uuid) -> Self {
        Self(uuid)
    }
}

impl AsRef<Uuid> for JobId {
    fn as_ref(&self) -> &Uuid {
        &self.0
    }
}

/// Job priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Priority {
    Low = 0,
    Normal = 1,
    High = 2,
    Critical = 3,
}

impl Default for Priority {
    fn default() -> Self {
        Self::Normal
    }
}

impl fmt::Display for Priority {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Low => write!(f, "low"),
            Self::Normal => write!(f, "normal"),
            Self::High => write!(f, "high"),
            Self::Critical => write!(f, "critical"),
        }
    }
}

/// Job schedule type
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Schedule {
    /// One-time execution at specific time
    Once {
        at: DateTime<Utc>,
    },
    /// Recurring with cron expression
    Cron {
        expression: String,
    },
    /// Fixed interval
    Interval {
        seconds: u64,
    },
    /// Manual trigger only
    Manual,
}

impl Schedule {
    /// Create a one-time schedule
    pub fn once(at: DateTime<Utc>) -> Self {
        Self::Once { at }
    }

    /// Create a cron schedule
    pub fn cron(expression: impl Into<String>) -> Self {
        Self::Cron {
            expression: expression.into(),
        }
    }

    /// Create an interval schedule
    pub fn interval(seconds: u64) -> Self {
        Self::Interval { seconds }
    }

    /// Create a manual schedule
    pub fn manual() -> Self {
        Self::Manual
    }

    /// Check if this is a recurring schedule
    pub fn is_recurring(&self) -> bool {
        matches!(self, Self::Cron { .. } | Self::Interval { .. })
    }
}

impl Default for Schedule {
    fn default() -> Self {
        Self::Manual
    }
}

/// Tags for categorizing jobs
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Tags(Vec<String>);

impl Tags {
    /// Create empty tags
    pub fn new() -> Self {
        Self(Vec::new())
    }

    /// Create from iterator
    pub fn from_iter<I, S>(iter: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        Self(iter.into_iter().map(Into::into).collect())
    }

    /// Add a tag
    pub fn add(&mut self, tag: impl Into<String>) {
        let tag = tag.into();
        if !self.0.contains(&tag) {
            self.0.push(tag);
        }
    }

    /// Check if tag exists
    pub fn contains(&self, tag: &str) -> bool {
        self.0.iter().any(|t| t == tag)
    }

    /// Get all tags
    pub fn as_slice(&self) -> &[String] {
        &self.0
    }

    /// Check if empty
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// Get count
    pub fn len(&self) -> usize {
        self.0.len()
    }
}

impl<'a> IntoIterator for &'a Tags {
    type Item = &'a String;
    type IntoIter = std::slice::Iter<'a, String>;

    fn into_iter(self) -> Self::IntoIter {
        self.0.iter()
    }
}

/// Main job struct
///
/// Jobs are the core unit of work in the scheduler. Each job has:
/// - A unique identifier
/// - A human-readable name
/// - A schedule (when to run)
/// - A handler (what to run)
/// - State tracking
/// - Configuration options
#[derive(Debug, Serialize, Deserialize)]
pub struct Job {
    /// Unique identifier
    id: JobId,
    /// Human-readable name
    name: String,
    /// Optional description
    description: Option<String>,
    /// Schedule configuration
    schedule: Schedule,
    /// Current state
    #[serde(default)]
    state: JobState,
    /// Priority level
    #[serde(default)]
    priority: Priority,
    /// Maximum retry attempts
    #[serde(default = "default_retries")]
    max_retries: u8,
    /// Timeout in seconds
    timeout_secs: Option<u64>,
    /// Tags for categorization
    #[serde(default)]
    tags: Tags,
    /// Whether job is enabled
    #[serde(default = "default_enabled")]
    enabled: bool,
    /// Creation timestamp
    created_at: DateTime<Utc>,
    /// Last update timestamp
    updated_at: DateTime<Utc>,
    /// Last execution timestamp
    last_run: Option<DateTime<Utc>>,
    /// Next scheduled execution
    next_run: Option<DateTime<Utc>>,
    /// Execution history (recent runs)
    #[serde(default)]
    history: Vec<ExecutionRecord>,
    /// Handler configuration (for command handlers)
    #[serde(skip_serializing_if = "Option::is_none")]
    handler_config: Option<handler::SerializableHandler>,
    /// The actual handler (not serialized)
    #[serde(skip)]
    handler: Option<BoxedHandler>,
}

fn default_retries() -> u8 {
    DEFAULT_RETRIES
}

fn default_enabled() -> bool {
    true
}

// First impl block: constructors and factory methods
impl Job {
    /// Create a new job with default settings
    pub fn new(name: impl Into<String>, schedule: Schedule) -> Self {
        let now = Utc::now();
        Self {
            id: JobId::new(),
            name: name.into(),
            description: None,
            schedule,
            state: JobState::Pending,
            priority: Priority::Normal,
            max_retries: DEFAULT_RETRIES,
            timeout_secs: None,
            tags: Tags::new(),
            enabled: true,
            created_at: now,
            updated_at: now,
            last_run: None,
            next_run: None,
            history: Vec::new(),
            handler_config: None,
            handler: None,
        }
    }

    /// Start building a new job
    pub fn builder() -> JobBuilder {
        JobBuilder::new()
    }

    /// Create a one-time job
    pub fn once(name: impl Into<String>, at: DateTime<Utc>) -> Self {
        Self::new(name, Schedule::once(at))
    }

    /// Create a recurring cron job
    pub fn cron(name: impl Into<String>, expression: impl Into<String>) -> Self {
        Self::new(name, Schedule::cron(expression))
    }

    /// Create an interval job
    pub fn every(name: impl Into<String>, seconds: u64) -> Self {
        Self::new(name, Schedule::interval(seconds))
    }
}

// Second impl block: getters
impl Job {
    /// Get job ID
    pub fn id(&self) -> JobId {
        self.id
    }

    /// Get job name
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Get description
    pub fn description(&self) -> Option<&str> {
        self.description.as_deref()
    }

    /// Get schedule
    pub fn schedule(&self) -> &Schedule {
        &self.schedule
    }

    /// Get current state
    pub fn state(&self) -> &JobState {
        &self.state
    }

    /// Get priority
    pub fn priority(&self) -> Priority {
        self.priority
    }

    /// Get max retries
    pub fn max_retries(&self) -> u8 {
        self.max_retries
    }

    /// Get timeout
    pub fn timeout_secs(&self) -> Option<u64> {
        self.timeout_secs
    }

    /// Get tags
    pub fn tags(&self) -> &Tags {
        &self.tags
    }

    /// Check if enabled
    pub fn is_enabled(&self) -> bool {
        self.enabled
    }

    /// Get creation time
    pub fn created_at(&self) -> DateTime<Utc> {
        self.created_at
    }

    /// Get last update time
    pub fn updated_at(&self) -> DateTime<Utc> {
        self.updated_at
    }

    /// Get last run time
    pub fn last_run(&self) -> Option<DateTime<Utc>> {
        self.last_run
    }

    /// Get next scheduled run
    pub fn next_run(&self) -> Option<DateTime<Utc>> {
        self.next_run
    }

    /// Get execution history
    pub fn history(&self) -> &[ExecutionRecord] {
        &self.history
    }

    /// Get handler reference
    pub fn handler(&self) -> Option<&BoxedHandler> {
        self.handler.as_ref()
    }
}

// Third impl block: setters and mutators
impl Job {
    /// Set description
    pub fn set_description(&mut self, desc: impl Into<String>) {
        self.description = Some(desc.into());
        self.touch();
    }

    /// Set schedule
    pub fn set_schedule(&mut self, schedule: Schedule) {
        self.schedule = schedule;
        self.touch();
    }

    /// Set priority
    pub fn set_priority(&mut self, priority: Priority) {
        self.priority = priority;
        self.touch();
    }

    /// Set max retries
    pub fn set_max_retries(&mut self, retries: u8) {
        self.max_retries = retries;
        self.touch();
    }

    /// Set timeout
    pub fn set_timeout(&mut self, secs: u64) {
        self.timeout_secs = Some(secs);
        self.touch();
    }

    /// Enable the job
    pub fn enable(&mut self) {
        self.enabled = true;
        self.touch();
    }

    /// Disable the job
    pub fn disable(&mut self) {
        self.enabled = false;
        self.touch();
    }

    /// Add a tag
    pub fn add_tag(&mut self, tag: impl Into<String>) {
        self.tags.add(tag);
        self.touch();
    }

    /// Set handler
    pub fn set_handler<H>(&mut self, handler: H)
    where
        H: JobHandler + Send + Sync + 'static,
    {
        self.handler = Some(Box::new(handler));
        self.touch();
    }

    /// Set command handler (serializable)
    pub fn set_command(&mut self, cmd: CommandHandler) {
        if let Ok(config) = handler::SerializableHandler::from_command(&cmd) {
            self.handler_config = Some(config);
        }
        self.handler = Some(Box::new(cmd));
        self.touch();
    }

    /// Update state
    pub fn set_state(&mut self, state: JobState) {
        self.state = state;
        self.touch();
    }

    /// Record execution start
    pub fn start_execution(&mut self, trigger: ExecutionTrigger) -> ExecutionRecord {
        self.state = JobState::running();
        self.touch();
        ExecutionRecord::new(self.id, trigger)
    }

    /// Record execution completion
    pub fn complete_execution(&mut self, record: &ExecutionRecord) {
        self.last_run = Some(Utc::now());
        if let Some(output) = record.result.as_ref().and_then(|r| r.stdout.clone()) {
            self.state = self.state.clone().complete(Some(output));
        } else {
            self.state = self.state.clone().complete(None);
        }
        self.add_history(record.clone());
        self.touch();
    }

    /// Record execution failure
    pub fn fail_execution(&mut self, error: impl Into<String>, retry_count: u8) {
        self.state = self.state.clone().fail(error, retry_count, self.max_retries);
        self.touch();
    }

    /// Add to history (keeps last 10)
    fn add_history(&mut self, record: ExecutionRecord) {
        self.history.push(record);
        if self.history.len() > 10 {
            self.history.remove(0);
        }
    }

    /// Update the updated_at timestamp
    fn touch(&mut self) {
        self.updated_at = Utc::now();
    }
}

// Fourth impl block: query methods
impl Job {
    /// Check if job is ready to run
    pub fn is_ready(&self) -> bool {
        self.enabled && matches!(self.state, JobState::Pending | JobState::Queued { .. })
    }

    /// Check if job is currently running
    pub fn is_running(&self) -> bool {
        matches!(self.state, JobState::Running { .. })
    }

    /// Check if job has failed
    pub fn is_failed(&self) -> bool {
        matches!(self.state, JobState::Failed { .. })
    }

    /// Check if job can be retried
    pub fn can_retry(&self) -> bool {
        match &self.state {
            JobState::Failed { retry_count, will_retry, .. } => {
                *will_retry && *retry_count < self.max_retries
            }
            _ => false,
        }
    }

    /// Check if job is due to run
    pub fn is_due(&self) -> bool {
        if !self.enabled {
            return false;
        }
        match &self.schedule {
            Schedule::Once { at } => *at <= Utc::now(),
            Schedule::Manual => false,
            _ => self.next_run.map(|t| t <= Utc::now()).unwrap_or(false),
        }
    }

    /// Get current retry count
    pub fn retry_count(&self) -> u8 {
        match &self.state {
            JobState::Failed { retry_count, .. } => *retry_count,
            _ => 0,
        }
    }

    /// Get success rate from history
    pub fn success_rate(&self) -> Option<f64> {
        if self.history.is_empty() {
            return None;
        }
        let successes = self.history.iter().filter(|r| {
            matches!(r.final_state, JobState::Completed { .. })
        }).count();
        Some(successes as f64 / self.history.len() as f64)
    }
}

impl PartialEq for Job {
    fn eq(&self, other: &Self) -> bool {
        self.id == other.id
    }
}

impl Eq for Job {}

impl Hash for Job {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.id.hash(state);
    }
}

impl fmt::Display for Job {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "Job[{}] {} ({}) - {}",
            self.id,
            self.name,
            self.priority,
            self.state.name()
        )
    }
}

/// Builder for constructing jobs
///
/// Provides a fluent API for job creation with validation.
///
/// # Example
///
/// ```rust
/// use task_scheduler::{Job, Priority};
///
/// let job = Job::builder()
///     .name("backup")
///     .description("Daily database backup")
///     .schedule("0 2 * * *")
///     .priority(Priority::High)
///     .retries(5)
///     .timeout(3600)
///     .tags(["maintenance", "critical"])
///     .build()
///     .unwrap();
/// ```
#[derive(Debug, Default)]
pub struct JobBuilder {
    name: Option<String>,
    description: Option<String>,
    schedule: Option<Schedule>,
    priority: Priority,
    max_retries: u8,
    timeout_secs: Option<u64>,
    tags: Tags,
    enabled: bool,
    handler: Option<BoxedHandler>,
    command: Option<CommandHandler>,
}

impl JobBuilder {
    /// Create a new builder
    pub fn new() -> Self {
        Self {
            name: None,
            description: None,
            schedule: None,
            priority: Priority::Normal,
            max_retries: DEFAULT_RETRIES,
            timeout_secs: None,
            tags: Tags::new(),
            enabled: true,
            handler: None,
            command: None,
        }
    }

    /// Set the job name (required)
    pub fn name(mut self, name: impl Into<String>) -> Self {
        self.name = Some(name.into());
        self
    }

    /// Set description
    pub fn description(mut self, desc: impl Into<String>) -> Self {
        self.description = Some(desc.into());
        self
    }

    /// Set schedule from cron expression
    pub fn schedule(mut self, cron: impl Into<String>) -> Self {
        self.schedule = Some(Schedule::cron(cron));
        self
    }

    /// Set as one-time job
    pub fn once_at(mut self, at: DateTime<Utc>) -> Self {
        self.schedule = Some(Schedule::once(at));
        self
    }

    /// Set as interval job
    pub fn every_secs(mut self, seconds: u64) -> Self {
        self.schedule = Some(Schedule::interval(seconds));
        self
    }

    /// Set as manual trigger only
    pub fn manual(mut self) -> Self {
        self.schedule = Some(Schedule::manual());
        self
    }

    /// Set priority
    pub fn priority(mut self, priority: Priority) -> Self {
        self.priority = priority;
        self
    }

    /// Set max retries
    pub fn retries(mut self, count: u8) -> Self {
        self.max_retries = count;
        self
    }

    /// Set timeout in seconds
    pub fn timeout(mut self, secs: u64) -> Self {
        self.timeout_secs = Some(secs);
        self
    }

    /// Add tags
    pub fn tags<I, S>(mut self, tags: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        for tag in tags {
            self.tags.add(tag);
        }
        self
    }

    /// Add a single tag
    pub fn tag(mut self, tag: impl Into<String>) -> Self {
        self.tags.add(tag);
        self
    }

    /// Set enabled state
    pub fn enabled(mut self, enabled: bool) -> Self {
        self.enabled = enabled;
        self
    }

    /// Start disabled
    pub fn disabled(mut self) -> Self {
        self.enabled = false;
        self
    }

    /// Set a custom handler
    pub fn handler<H>(mut self, handler: H) -> Self
    where
        H: JobHandler + Send + Sync + 'static,
    {
        self.handler = Some(Box::new(handler));
        self
    }

    /// Set a command handler
    pub fn command(mut self, cmd: impl Into<String>) -> Self {
        self.command = Some(CommandHandler::new(cmd));
        self
    }

    /// Set command with arguments
    pub fn command_with_args<I, S>(mut self, cmd: impl Into<String>, args: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.command = Some(CommandHandler::new(cmd).args(args));
        self
    }

    /// Validate and build the job
    pub fn build(self) -> Result<Job> {
        // Validate name
        let name = self.name.ok_or_else(|| {
            SchedulerError::validation("name", "job name is required")
        })?;

        if name.is_empty() {
            return Err(SchedulerError::validation("name", "job name cannot be empty"));
        }

        if name.len() > MAX_JOB_NAME_LEN {
            return Err(SchedulerError::validation(
                "name",
                format!("job name exceeds {} characters", MAX_JOB_NAME_LEN),
            ));
        }

        // Validate name format (alphanumeric, underscores, hyphens)
        if !name.chars().all(|c| c.is_alphanumeric() || c == '_' || c == '-') {
            return Err(SchedulerError::validation(
                "name",
                "job name must contain only alphanumeric characters, underscores, and hyphens",
            ));
        }

        let schedule = self.schedule.unwrap_or(Schedule::Manual);

        let now = Utc::now();
        let mut job = Job {
            id: JobId::new(),
            name,
            description: self.description,
            schedule,
            state: JobState::Pending,
            priority: self.priority,
            max_retries: self.max_retries,
            timeout_secs: self.timeout_secs,
            tags: self.tags,
            enabled: self.enabled,
            created_at: now,
            updated_at: now,
            last_run: None,
            next_run: None,
            history: Vec::new(),
            handler_config: None,
            handler: self.handler,
        };

        // Set command handler if provided
        if let Some(cmd) = self.command {
            job.set_command(cmd);
        }

        Ok(job)
    }
}

/// Type alias for a collection of jobs
pub type JobList = Vec<Job>;

/// Filter for querying jobs
#[derive(Debug, Clone, Default)]
pub struct JobFilter<'a> {
    /// Filter by name pattern
    pub name_pattern: Option<&'a str>,
    /// Filter by state
    pub state: Option<&'a str>,
    /// Filter by priority
    pub priority: Option<Priority>,
    /// Filter by tag
    pub tag: Option<&'a str>,
    /// Filter by enabled status
    pub enabled: Option<bool>,
}

impl<'a> JobFilter<'a> {
    /// Create a new empty filter
    pub fn new() -> Self {
        Self::default()
    }

    /// Filter by name pattern
    pub fn name(mut self, pattern: &'a str) -> Self {
        self.name_pattern = Some(pattern);
        self
    }

    /// Filter by state
    pub fn state(mut self, state: &'a str) -> Self {
        self.state = Some(state);
        self
    }

    /// Filter by priority
    pub fn priority(mut self, priority: Priority) -> Self {
        self.priority = Some(priority);
        self
    }

    /// Filter by tag
    pub fn tag(mut self, tag: &'a str) -> Self {
        self.tag = Some(tag);
        self
    }

    /// Filter by enabled status
    pub fn enabled(mut self, enabled: bool) -> Self {
        self.enabled = Some(enabled);
        self
    }

    /// Check if a job matches this filter
    pub fn matches(&self, job: &Job) -> bool {
        if let Some(pattern) = self.name_pattern {
            if !job.name.contains(pattern) {
                return false;
            }
        }

        if let Some(state) = self.state {
            if job.state.name() != state {
                return false;
            }
        }

        if let Some(priority) = self.priority {
            if job.priority != priority {
                return false;
            }
        }

        if let Some(tag) = self.tag {
            if !job.tags.contains(tag) {
                return false;
            }
        }

        if let Some(enabled) = self.enabled {
            if job.enabled != enabled {
                return false;
            }
        }

        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_job_builder_valid() {
        let job = Job::builder()
            .name("test-job")
            .description("A test job")
            .schedule("* * * * *")
            .priority(Priority::High)
            .retries(5)
            .tag("test")
            .build()
            .unwrap();

        assert_eq!(job.name(), "test-job");
        assert_eq!(job.description(), Some("A test job"));
        assert_eq!(job.priority(), Priority::High);
        assert_eq!(job.max_retries(), 5);
        assert!(job.tags().contains("test"));
    }

    #[test]
    fn test_job_builder_missing_name() {
        let result = Job::builder()
            .schedule("* * * * *")
            .build();

        assert!(result.is_err());
    }

    #[test]
    fn test_job_builder_invalid_name() {
        let result = Job::builder()
            .name("invalid name with spaces")
            .build();

        assert!(result.is_err());
    }

    #[test]
    fn test_job_state_transitions() {
        let mut job = Job::builder()
            .name("test")
            .manual()
            .build()
            .unwrap();

        assert!(job.is_ready());
        assert!(!job.is_running());

        let record = job.start_execution(ExecutionTrigger::Manual);
        assert!(job.is_running());

        job.complete_execution(&record);
        assert!(!job.is_running());
    }

    #[test]
    fn test_job_filter() {
        let job = Job::builder()
            .name("backup-job")
            .priority(Priority::High)
            .tag("maintenance")
            .build()
            .unwrap();

        let filter = JobFilter::new()
            .name("backup")
            .priority(Priority::High);

        assert!(filter.matches(&job));

        let non_matching = JobFilter::new().name("restore");
        assert!(!non_matching.matches(&job));
    }

    #[test]
    fn test_job_id() {
        let id1 = JobId::new();
        let id2 = JobId::new();
        assert_ne!(id1, id2);

        let id_str = id1.to_string();
        let parsed = JobId::parse(&id_str).unwrap();
        assert_eq!(id1, parsed);
    }

    #[test]
    fn test_tags() {
        let mut tags = Tags::new();
        tags.add("foo");
        tags.add("bar");
        tags.add("foo"); // Duplicate

        assert_eq!(tags.len(), 2);
        assert!(tags.contains("foo"));
        assert!(tags.contains("bar"));
        assert!(!tags.contains("baz"));
    }
}
