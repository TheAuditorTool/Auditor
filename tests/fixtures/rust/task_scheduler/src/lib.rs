//! Task Scheduler - A lightweight job scheduling library
//!
//! This library provides a flexible job scheduling system with:
//! - Cron-like scheduling expressions
//! - Multiple job handler types (closures, commands, custom handlers)
//! - Persistent job storage
//! - Builder pattern for job configuration
//!
//! # Example
//!
//! ```rust,no_run
//! use task_scheduler::{Scheduler, Job, job};
//!
//! fn main() -> task_scheduler::Result<()> {
//!     let mut scheduler = Scheduler::new("jobs.json")?;
//!
//!     // Using the job! macro
//!     let backup_job = job!("backup", "0 2 * * *", || {
//!         println!("Running backup...");
//!         Ok(())
//!     });
//!
//!     // Using the builder pattern
//!     let cleanup = Job::builder()
//!         .name("cleanup")
//!         .schedule("0 * * * *")
//!         .command("rm -rf /tmp/cache/*")
//!         .retries(3)
//!         .build()?;
//!
//!     scheduler.add(backup_job)?;
//!     scheduler.add(cleanup)?;
//!
//!     Ok(())
//! }
//! ```

pub mod job;
pub mod scheduler;
pub mod storage;
pub mod utils;

// Additional modules for testing extraction edge cases
pub mod ffi;           // FFI, unsafe blocks, extern functions
pub mod async_runtime; // async/await, futures
pub mod taint_flows;   // Source-to-sink data flow patterns

use thiserror::Error;

// Re-exports for convenience
pub use job::{Job, JobBuilder, JobId};
pub use job::handler::{JobHandler, CommandHandler, ClosureHandler, HandlerResult};
pub use job::state::{JobState, JobResult, ExecutionRecord};
pub use scheduler::{Scheduler, SchedulerConfig};
pub use storage::{Storage, JsonStorage};

/// Result type alias for scheduler operations
pub type Result<T> = std::result::Result<T, SchedulerError>;

/// Errors that can occur in the task scheduler
#[derive(Error, Debug)]
pub enum SchedulerError {
    /// Job not found
    #[error("job not found: {0}")]
    JobNotFound(JobId),

    /// Invalid cron expression
    #[error("invalid cron expression: {expression} - {reason}")]
    InvalidCron {
        expression: String,
        reason: &'static str,
    },

    /// Job validation failed
    #[error("job validation failed: {field} - {message}")]
    ValidationError {
        field: &'static str,
        message: String,
    },

    /// Storage error
    #[error("storage error: {0}")]
    StorageError(String),

    /// IO error
    #[error("io error: {0}")]
    IoError(#[from] std::io::Error),

    /// Serialization error
    #[error("serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    /// Handler execution failed
    #[error("handler execution failed: {0}")]
    ExecutionError(String),

    /// Job already exists
    #[error("job already exists: {0}")]
    DuplicateJob(String),

    /// Scheduler is shutting down
    #[error("scheduler is shutting down")]
    ShuttingDown,

    /// Maximum retries exceeded
    #[error("maximum retries exceeded for job {job_id} after {attempts} attempts")]
    MaxRetriesExceeded {
        job_id: JobId,
        attempts: u8,
    },
}

impl SchedulerError {
    /// Create a validation error
    pub fn validation(field: &'static str, message: impl Into<String>) -> Self {
        Self::ValidationError {
            field,
            message: message.into(),
        }
    }

    /// Create an invalid cron error
    pub fn invalid_cron(expression: impl Into<String>, reason: &'static str) -> Self {
        Self::InvalidCron {
            expression: expression.into(),
            reason,
        }
    }

    /// Check if error is retryable
    pub fn is_retryable(&self) -> bool {
        matches!(self, Self::IoError(_) | Self::StorageError(_))
    }
}

/// Macro for quickly defining a job with a closure handler
///
/// # Examples
///
/// ```rust
/// use task_scheduler::job;
///
/// // Simple job with closure
/// let j = job!("my_job", "* * * * *", || {
///     println!("Hello!");
///     Ok(())
/// });
///
/// // Job with name only (manual schedule later)
/// let j2 = job!("another_job");
/// ```
#[macro_export]
macro_rules! job {
    // Full form: name, schedule, handler
    ($name:expr, $schedule:expr, $handler:expr) => {{
        $crate::Job::builder()
            .name($name)
            .schedule($schedule)
            .handler($crate::ClosureHandler::new($handler))
            .build()
            .expect("job! macro: invalid job configuration")
    }};

    // Name only - returns builder for chaining
    ($name:expr) => {{
        $crate::Job::builder().name($name)
    }};

    // Name and schedule - returns builder for chaining
    ($name:expr, $schedule:expr) => {{
        $crate::Job::builder().name($name).schedule($schedule)
    }};
}

/// Macro for defining multiple jobs at once
///
/// # Example
///
/// ```rust
/// use task_scheduler::jobs;
///
/// let job_list = jobs! {
///     "backup" => "0 2 * * *" => || { println!("backup"); Ok(()) },
///     "cleanup" => "0 * * * *" => || { println!("cleanup"); Ok(()) },
/// };
/// ```
#[macro_export]
macro_rules! jobs {
    ($($name:expr => $schedule:expr => $handler:expr),+ $(,)?) => {{
        vec![
            $(
                $crate::job!($name, $schedule, $handler)
            ),+
        ]
    }};
}

/// Global version constant
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Default storage file
pub const DEFAULT_STORAGE_FILE: &str = "scheduler_jobs.json";

/// Maximum job name length
pub const MAX_JOB_NAME_LEN: usize = 128;

/// Maximum concurrent jobs
pub const MAX_CONCURRENT_JOBS: usize = 16;

/// Default retry count
pub const DEFAULT_RETRIES: u8 = 3;

/// Static configuration that can be modified at startup
pub static mut GLOBAL_CONFIG: Option<SchedulerConfig> = None;

/// Initialize global configuration (call once at startup)
///
/// # Safety
/// Must be called before any scheduler operations and only from main thread
pub unsafe fn init_global_config(config: SchedulerConfig) {
    GLOBAL_CONFIG = Some(config);
}

/// Get global configuration
pub fn global_config() -> &'static SchedulerConfig {
    // Safety: Only safe after init_global_config is called
    unsafe {
        GLOBAL_CONFIG.as_ref().unwrap_or_else(|| {
            static DEFAULT: SchedulerConfig = SchedulerConfig::default_const();
            &DEFAULT
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_is_retryable() {
        let io_err = SchedulerError::IoError(std::io::Error::new(
            std::io::ErrorKind::Other,
            "test",
        ));
        assert!(io_err.is_retryable());

        let not_found = SchedulerError::JobNotFound(JobId::new());
        assert!(!not_found.is_retryable());
    }

    #[test]
    fn test_validation_error() {
        let err = SchedulerError::validation("name", "cannot be empty");
        match err {
            SchedulerError::ValidationError { field, message } => {
                assert_eq!(field, "name");
                assert_eq!(message, "cannot be empty");
            }
            _ => panic!("wrong error type"),
        }
    }
}
