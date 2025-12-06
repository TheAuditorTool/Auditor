//! Job state machine and execution records
//!
//! This module defines the state transitions for jobs and tracks
//! execution history.

use chrono::{DateTime, Utc, Duration};
use serde::{Deserialize, Serialize};
use std::fmt;

/// Unique identifier for an execution run
pub type RunId = uuid::Uuid;

/// Job execution state machine
///
/// State transitions:
/// ```text
///                    ┌─────────────┐
///                    │   Pending   │
///                    └──────┬──────┘
///                           │ schedule triggers
///                           ▼
///                    ┌─────────────┐
///              ┌─────│   Queued    │─────┐
///              │     └──────┬──────┘     │
///              │            │ executor   │ cancelled
///              │            │ picks up   │
///              │            ▼            ▼
///              │     ┌─────────────┐  ┌─────────────┐
///              │     │   Running   │  │  Cancelled  │
///              │     └──────┬──────┘  └─────────────┘
///              │            │
///         retry│    ┌───────┴───────┐
///              │    │               │
///              │    ▼               ▼
///              │ ┌─────────────┐ ┌─────────────┐
///              └─│   Failed    │ │  Completed  │
///                └─────────────┘ └─────────────┘
/// ```
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum JobState {
    /// Job is registered but not yet scheduled
    Pending,

    /// Job is queued for execution
    Queued {
        /// When the job was queued
        queued_at: DateTime<Utc>,
        /// Position in queue (if tracked)
        position: Option<u32>,
    },

    /// Job is currently executing
    Running {
        /// When execution started
        started_at: DateTime<Utc>,
        /// Unique run identifier
        run_id: RunId,
        /// Process ID if running external command
        pid: Option<u32>,
        /// Progress percentage (0-100) if reported
        progress: Option<u8>,
    },

    /// Job completed successfully
    Completed {
        /// When execution finished
        finished_at: DateTime<Utc>,
        /// Run identifier
        run_id: RunId,
        /// Execution duration
        duration_ms: u64,
        /// Optional output/result
        output: Option<String>,
    },

    /// Job execution failed
    Failed {
        /// When failure occurred
        failed_at: DateTime<Utc>,
        /// Run identifier
        run_id: RunId,
        /// Error message
        error: String,
        /// Number of retry attempts made
        retry_count: u8,
        /// Whether job will be retried
        will_retry: bool,
    },

    /// Job was cancelled before completion
    Cancelled {
        /// When cancellation occurred
        cancelled_at: DateTime<Utc>,
        /// Reason for cancellation
        reason: CancelReason,
        /// Run ID if cancelled during execution
        run_id: Option<RunId>,
    },

    /// Job is paused (can be resumed)
    Paused {
        /// When job was paused
        paused_at: DateTime<Utc>,
        /// State before pause (for resumption)
        previous_state: Box<JobState>,
    },
}

impl JobState {
    /// Create a new pending state
    pub fn pending() -> Self {
        Self::Pending
    }

    /// Create a queued state
    pub fn queued() -> Self {
        Self::Queued {
            queued_at: Utc::now(),
            position: None,
        }
    }

    /// Create a running state with new run ID
    pub fn running() -> Self {
        Self::Running {
            started_at: Utc::now(),
            run_id: RunId::new_v4(),
            pid: None,
            progress: None,
        }
    }

    /// Transition to completed state
    pub fn complete(self, output: Option<String>) -> Self {
        let (run_id, started_at) = match self {
            Self::Running { run_id, started_at, .. } => (run_id, started_at),
            _ => (RunId::new_v4(), Utc::now()),
        };

        let now = Utc::now();
        let duration = now.signed_duration_since(started_at);

        Self::Completed {
            finished_at: now,
            run_id,
            duration_ms: duration.num_milliseconds().max(0) as u64,
            output,
        }
    }

    /// Transition to failed state
    pub fn fail(self, error: impl Into<String>, retry_count: u8, max_retries: u8) -> Self {
        let run_id = match self {
            Self::Running { run_id, .. } => run_id,
            _ => RunId::new_v4(),
        };

        Self::Failed {
            failed_at: Utc::now(),
            run_id,
            error: error.into(),
            retry_count,
            will_retry: retry_count < max_retries,
        }
    }

    /// Check if job is in a terminal state
    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            Self::Completed { .. } | Self::Failed { will_retry: false, .. } | Self::Cancelled { .. }
        )
    }

    /// Check if job is currently active
    pub fn is_active(&self) -> bool {
        matches!(self, Self::Running { .. } | Self::Queued { .. })
    }

    /// Check if job can be cancelled
    pub fn is_cancellable(&self) -> bool {
        matches!(
            self,
            Self::Pending | Self::Queued { .. } | Self::Running { .. } | Self::Paused { .. }
        )
    }

    /// Get the run ID if available
    pub fn run_id(&self) -> Option<RunId> {
        match self {
            Self::Running { run_id, .. }
            | Self::Completed { run_id, .. }
            | Self::Failed { run_id, .. } => Some(*run_id),
            Self::Cancelled { run_id, .. } => *run_id,
            _ => None,
        }
    }

    /// Get state name for display
    pub fn name(&self) -> &'static str {
        match self {
            Self::Pending => "pending",
            Self::Queued { .. } => "queued",
            Self::Running { .. } => "running",
            Self::Completed { .. } => "completed",
            Self::Failed { .. } => "failed",
            Self::Cancelled { .. } => "cancelled",
            Self::Paused { .. } => "paused",
        }
    }
}

impl Default for JobState {
    fn default() -> Self {
        Self::Pending
    }
}

impl fmt::Display for JobState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Pending => write!(f, "Pending"),
            Self::Queued { queued_at, .. } => write!(f, "Queued since {}", queued_at),
            Self::Running { started_at, progress, .. } => {
                if let Some(p) = progress {
                    write!(f, "Running ({}%) since {}", p, started_at)
                } else {
                    write!(f, "Running since {}", started_at)
                }
            }
            Self::Completed { duration_ms, .. } => {
                write!(f, "Completed in {}ms", duration_ms)
            }
            Self::Failed { error, retry_count, .. } => {
                write!(f, "Failed: {} (retries: {})", error, retry_count)
            }
            Self::Cancelled { reason, .. } => write!(f, "Cancelled: {}", reason),
            Self::Paused { .. } => write!(f, "Paused"),
        }
    }
}

/// Reasons for job cancellation
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CancelReason {
    /// User requested cancellation
    UserRequested,
    /// Timeout exceeded
    Timeout,
    /// Scheduler shutdown
    Shutdown,
    /// Dependency failed
    DependencyFailed {
        /// ID of the failed dependency
        dependency_id: String,
    },
    /// Superseded by newer run
    Superseded,
    /// Custom reason
    Other(String),
}

impl fmt::Display for CancelReason {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UserRequested => write!(f, "user requested"),
            Self::Timeout => write!(f, "timeout exceeded"),
            Self::Shutdown => write!(f, "scheduler shutdown"),
            Self::DependencyFailed { dependency_id } => {
                write!(f, "dependency {} failed", dependency_id)
            }
            Self::Superseded => write!(f, "superseded by newer run"),
            Self::Other(reason) => write!(f, "{}", reason),
        }
    }
}

/// Result of a job execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobResult {
    /// Whether execution succeeded
    pub success: bool,
    /// Exit code (for command handlers)
    pub exit_code: Option<i32>,
    /// Standard output
    pub stdout: Option<String>,
    /// Standard error
    pub stderr: Option<String>,
    /// Structured output (for programmatic handlers)
    pub data: Option<serde_json::Value>,
    /// Execution duration in milliseconds
    pub duration_ms: u64,
}

impl JobResult {
    /// Create a successful result
    pub fn success() -> Self {
        Self {
            success: true,
            exit_code: Some(0),
            stdout: None,
            stderr: None,
            data: None,
            duration_ms: 0,
        }
    }

    /// Create a failure result
    pub fn failure(error: impl Into<String>) -> Self {
        Self {
            success: false,
            exit_code: Some(1),
            stdout: None,
            stderr: Some(error.into()),
            data: None,
            duration_ms: 0,
        }
    }

    /// Set output
    pub fn with_output(mut self, stdout: impl Into<String>) -> Self {
        self.stdout = Some(stdout.into());
        self
    }

    /// Set structured data
    pub fn with_data(mut self, data: serde_json::Value) -> Self {
        self.data = Some(data);
        self
    }

    /// Set duration
    pub fn with_duration(mut self, ms: u64) -> Self {
        self.duration_ms = ms;
        self
    }
}

impl Default for JobResult {
    fn default() -> Self {
        Self::success()
    }
}

/// Record of a single job execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionRecord {
    /// Unique run identifier
    pub run_id: RunId,
    /// Job ID this execution belongs to
    pub job_id: super::JobId,
    /// When execution started
    pub started_at: DateTime<Utc>,
    /// When execution finished
    pub finished_at: Option<DateTime<Utc>>,
    /// Final state
    pub final_state: JobState,
    /// Execution result
    pub result: Option<JobResult>,
    /// Trigger that caused this execution
    pub trigger: ExecutionTrigger,
    /// Worker that executed the job
    pub worker_id: Option<String>,
}

impl ExecutionRecord {
    /// Create a new execution record
    pub fn new(job_id: super::JobId, trigger: ExecutionTrigger) -> Self {
        Self {
            run_id: RunId::new_v4(),
            job_id,
            started_at: Utc::now(),
            finished_at: None,
            final_state: JobState::running(),
            result: None,
            trigger,
            worker_id: None,
        }
    }

    /// Mark execution as complete
    pub fn complete(&mut self, result: JobResult) {
        self.finished_at = Some(Utc::now());
        let output = result.stdout.clone();
        self.result = Some(result);
        self.final_state = self.final_state.clone().complete(output);
    }

    /// Mark execution as failed
    pub fn fail(&mut self, error: String, retry_count: u8, max_retries: u8) {
        self.finished_at = Some(Utc::now());
        self.result = Some(JobResult::failure(&error));
        self.final_state = self.final_state.clone().fail(error, retry_count, max_retries);
    }

    /// Calculate execution duration
    pub fn duration(&self) -> Option<Duration> {
        self.finished_at
            .map(|end| end.signed_duration_since(self.started_at))
    }
}

/// What triggered a job execution
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionTrigger {
    /// Scheduled execution (cron)
    Scheduled,
    /// Manual trigger via CLI or API
    Manual,
    /// Triggered by another job completion
    Dependency {
        parent_job_id: String,
    },
    /// Retry after failure
    Retry {
        attempt: u8,
    },
    /// Webhook trigger
    Webhook {
        source: String,
    },
}

impl Default for ExecutionTrigger {
    fn default() -> Self {
        Self::Manual
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_state_transitions() {
        let state = JobState::pending();
        assert!(!state.is_terminal());
        assert!(!state.is_active());

        let state = JobState::running();
        assert!(state.is_active());
        assert!(state.is_cancellable());

        let completed = state.complete(Some("done".into()));
        assert!(completed.is_terminal());
        assert!(!completed.is_active());
    }

    #[test]
    fn test_fail_with_retry() {
        let running = JobState::running();
        let failed = running.fail("connection timeout", 1, 3);

        match failed {
            JobState::Failed { will_retry, retry_count, .. } => {
                assert!(will_retry);
                assert_eq!(retry_count, 1);
            }
            _ => panic!("expected Failed state"),
        }
    }

    #[test]
    fn test_fail_no_retry() {
        let running = JobState::running();
        let failed = running.fail("permanent error", 3, 3);

        match failed {
            JobState::Failed { will_retry, .. } => {
                assert!(!will_retry);
            }
            _ => panic!("expected Failed state"),
        }
    }

    #[test]
    fn test_job_result_builder() {
        let result = JobResult::success()
            .with_output("hello world")
            .with_duration(150);

        assert!(result.success);
        assert_eq!(result.stdout, Some("hello world".into()));
        assert_eq!(result.duration_ms, 150);
    }
}
