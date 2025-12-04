//! Job handlers - different ways to execute jobs
//!
//! This module provides the `JobHandler` trait and various implementations:
//! - `CommandHandler`: Execute shell commands
//! - `ClosureHandler`: Execute Rust closures
//! - `ChainedHandler`: Execute multiple handlers in sequence
//!
//! # Trait Objects
//!
//! Handlers can be used as trait objects for heterogeneous job queues:
//!
//! ```rust
//! use task_scheduler::job::handler::{JobHandler, BoxedHandler};
//!
//! let handlers: Vec<BoxedHandler> = vec![
//!     Box::new(CommandHandler::new("echo hello")),
//!     Box::new(ClosureHandler::new(|| Ok(()))),
//! ];
//! ```

use crate::{Result, SchedulerError};
use super::state::JobResult;
use serde::{Deserialize, Serialize};
use std::fmt;
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// Result type for handler execution
pub type HandlerResult = Result<JobResult>;

/// Type alias for boxed handlers (trait objects)
pub type BoxedHandler = Box<dyn JobHandler + Send + Sync>;

/// Type alias for shared handlers (thread-safe reference counting)
pub type SharedHandler = Arc<dyn JobHandler + Send + Sync>;

/// Trait for job execution handlers
///
/// This trait uses associated types for maximum flexibility in implementations.
pub trait JobHandler: fmt::Debug {
    /// Configuration type for this handler
    type Config: Default + Clone;

    /// Context type passed during execution
    type Context;

    /// Execute the job handler
    fn execute(&self) -> HandlerResult;

    /// Execute with custom configuration
    fn execute_with_config(&self, _config: &Self::Config) -> HandlerResult {
        self.execute()
    }

    /// Execute with context (for dependency injection)
    fn execute_with_context(&self, _ctx: &Self::Context) -> HandlerResult
    where
        Self::Context: Sized,
    {
        self.execute()
    }

    /// Get handler type name for serialization
    fn handler_type(&self) -> &'static str;

    /// Get handler description
    fn description(&self) -> String {
        format!("{}::{}", self.handler_type(), "default")
    }

    /// Check if handler can be serialized for persistence
    fn is_serializable(&self) -> bool {
        false
    }

    /// Estimated execution time (for scheduling optimization)
    fn estimated_duration(&self) -> Option<Duration> {
        None
    }

    /// Clone into a boxed handler (for trait objects)
    fn clone_boxed(&self) -> BoxedHandler
    where
        Self: Clone + Sized + Send + Sync + 'static,
    {
        Box::new(self.clone())
    }
}

/// Shell command handler
///
/// Executes shell commands and captures output.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandHandler {
    /// Command to execute
    command: String,
    /// Arguments (separate from command for safety)
    args: Vec<String>,
    /// Working directory
    working_dir: Option<String>,
    /// Environment variables to set
    env: Vec<(String, String)>,
    /// Timeout in seconds
    timeout_secs: Option<u64>,
    /// Whether to capture output
    capture_output: bool,
}

/// Configuration for command handlers
#[derive(Debug, Clone, Default)]
pub struct CommandConfig {
    /// Additional environment variables
    pub extra_env: Vec<(String, String)>,
    /// Override working directory
    pub working_dir: Option<String>,
    /// Override timeout
    pub timeout: Option<Duration>,
}

impl CommandHandler {
    /// Create a new command handler
    pub fn new(command: impl Into<String>) -> Self {
        Self {
            command: command.into(),
            args: Vec::new(),
            working_dir: None,
            env: Vec::new(),
            timeout_secs: Some(300), // 5 min default
            capture_output: true,
        }
    }

    /// Add arguments
    pub fn args<I, S>(mut self, args: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.args.extend(args.into_iter().map(Into::into));
        self
    }

    /// Set working directory
    pub fn working_dir(mut self, dir: impl Into<String>) -> Self {
        self.working_dir = Some(dir.into());
        self
    }

    /// Add environment variable
    pub fn env(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.env.push((key.into(), value.into()));
        self
    }

    /// Set timeout
    pub fn timeout(mut self, secs: u64) -> Self {
        self.timeout_secs = Some(secs);
        self
    }

    /// Disable timeout
    pub fn no_timeout(mut self) -> Self {
        self.timeout_secs = None;
        self
    }

    /// Get the command string
    pub fn command(&self) -> &str {
        &self.command
    }

    /// Get full command line for display
    pub fn command_line(&self) -> String {
        if self.args.is_empty() {
            self.command.clone()
        } else {
            format!("{} {}", self.command, self.args.join(" "))
        }
    }
}

impl JobHandler for CommandHandler {
    type Config = CommandConfig;
    type Context = ();

    fn execute(&self) -> HandlerResult {
        let start = Instant::now();

        // Determine shell based on platform
        let (shell, shell_arg) = if cfg!(windows) {
            ("cmd", "/C")
        } else {
            ("sh", "-c")
        };

        let full_command = self.command_line();

        let mut cmd = Command::new(shell);
        cmd.arg(shell_arg).arg(&full_command);

        // Set working directory
        if let Some(ref dir) = self.working_dir {
            cmd.current_dir(dir);
        }

        // Set environment variables
        for (key, value) in &self.env {
            cmd.env(key, value);
        }

        // Configure output capture
        if self.capture_output {
            cmd.stdout(Stdio::piped());
            cmd.stderr(Stdio::piped());
        }

        // Execute
        let output = cmd
            .output()
            .map_err(|e| SchedulerError::ExecutionError(format!("failed to execute: {}", e)))?;

        let duration = start.elapsed();

        let result = JobResult {
            success: output.status.success(),
            exit_code: output.status.code(),
            stdout: String::from_utf8_lossy(&output.stdout)
                .to_string()
                .into(),
            stderr: String::from_utf8_lossy(&output.stderr)
                .to_string()
                .into(),
            data: None,
            duration_ms: duration.as_millis() as u64,
        };

        if result.success {
            Ok(result)
        } else {
            // Still return Ok with failure result - handler executed, job failed
            Ok(result)
        }
    }

    fn handler_type(&self) -> &'static str {
        "command"
    }

    fn description(&self) -> String {
        format!("command: {}", self.command_line())
    }

    fn is_serializable(&self) -> bool {
        true
    }

    fn estimated_duration(&self) -> Option<Duration> {
        // Default estimate: 10 seconds
        Some(Duration::from_secs(10))
    }
}

/// Closure-based handler
///
/// Wraps a Rust closure for execution. Note that closures cannot be serialized,
/// so these jobs must be re-registered on scheduler restart.
pub struct ClosureHandler<F>
where
    F: Fn() -> Result<()> + Send + Sync,
{
    /// The closure to execute
    closure: F,
    /// Description for display
    description: String,
    /// Estimated duration
    estimated_duration: Option<Duration>,
}

impl<F> ClosureHandler<F>
where
    F: Fn() -> Result<()> + Send + Sync,
{
    /// Create a new closure handler
    pub fn new(closure: F) -> Self {
        Self {
            closure,
            description: "closure".to_string(),
            estimated_duration: None,
        }
    }

    /// Set description
    pub fn with_description(mut self, desc: impl Into<String>) -> Self {
        self.description = desc.into();
        self
    }

    /// Set estimated duration
    pub fn with_estimated_duration(mut self, duration: Duration) -> Self {
        self.estimated_duration = Some(duration);
        self
    }
}

impl<F> fmt::Debug for ClosureHandler<F>
where
    F: Fn() -> Result<()> + Send + Sync,
{
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ClosureHandler")
            .field("description", &self.description)
            .finish()
    }
}

/// Empty config for closure handlers
#[derive(Debug, Clone, Default)]
pub struct ClosureConfig;

impl<F> JobHandler for ClosureHandler<F>
where
    F: Fn() -> Result<()> + Send + Sync,
{
    type Config = ClosureConfig;
    type Context = ();

    fn execute(&self) -> HandlerResult {
        let start = Instant::now();

        match (self.closure)() {
            Ok(()) => {
                let duration = start.elapsed();
                Ok(JobResult::success().with_duration(duration.as_millis() as u64))
            }
            Err(e) => {
                let duration = start.elapsed();
                Ok(JobResult::failure(e.to_string()).with_duration(duration.as_millis() as u64))
            }
        }
    }

    fn handler_type(&self) -> &'static str {
        "closure"
    }

    fn description(&self) -> String {
        self.description.clone()
    }

    fn is_serializable(&self) -> bool {
        false
    }

    fn estimated_duration(&self) -> Option<Duration> {
        self.estimated_duration
    }
}

/// Handler that chains multiple handlers together
///
/// Executes handlers in sequence, stopping on first failure.
#[derive(Debug)]
pub struct ChainedHandler {
    /// Handlers to execute in order
    handlers: Vec<BoxedHandler>,
    /// Whether to continue on failure
    continue_on_failure: bool,
    /// Description
    description: String,
}

impl ChainedHandler {
    /// Create a new chained handler
    pub fn new() -> Self {
        Self {
            handlers: Vec::new(),
            continue_on_failure: false,
            description: "chained".to_string(),
        }
    }

    /// Add a handler to the chain
    pub fn then<H>(mut self, handler: H) -> Self
    where
        H: JobHandler + Send + Sync + 'static,
    {
        self.handlers.push(Box::new(handler));
        self
    }

    /// Add a boxed handler
    pub fn then_boxed(mut self, handler: BoxedHandler) -> Self {
        self.handlers.push(handler);
        self
    }

    /// Continue executing even if a handler fails
    pub fn continue_on_failure(mut self) -> Self {
        self.continue_on_failure = true;
        self
    }

    /// Set description
    pub fn with_description(mut self, desc: impl Into<String>) -> Self {
        self.description = desc.into();
        self
    }
}

impl Default for ChainedHandler {
    fn default() -> Self {
        Self::new()
    }
}

/// Empty config for chained handlers
#[derive(Debug, Clone, Default)]
pub struct ChainedConfig;

impl JobHandler for ChainedHandler {
    type Config = ChainedConfig;
    type Context = ();

    fn execute(&self) -> HandlerResult {
        let start = Instant::now();
        let mut outputs = Vec::new();
        let mut all_success = true;

        for handler in &self.handlers {
            match handler.execute() {
                Ok(result) => {
                    if !result.success {
                        all_success = false;
                        if !self.continue_on_failure {
                            return Ok(result);
                        }
                    }
                    if let Some(stdout) = result.stdout {
                        outputs.push(stdout);
                    }
                }
                Err(e) => {
                    if !self.continue_on_failure {
                        return Err(e);
                    }
                    all_success = false;
                    outputs.push(format!("error: {}", e));
                }
            }
        }

        let duration = start.elapsed();
        let mut result = if all_success {
            JobResult::success()
        } else {
            JobResult::failure("one or more handlers failed")
        };

        result.stdout = Some(outputs.join("\n---\n"));
        result.duration_ms = duration.as_millis() as u64;

        Ok(result)
    }

    fn handler_type(&self) -> &'static str {
        "chained"
    }

    fn description(&self) -> String {
        format!(
            "{} ({} handlers)",
            self.description,
            self.handlers.len()
        )
    }

    fn is_serializable(&self) -> bool {
        self.handlers.iter().all(|h| h.is_serializable())
    }

    fn estimated_duration(&self) -> Option<Duration> {
        let total: Duration = self
            .handlers
            .iter()
            .filter_map(|h| h.estimated_duration())
            .sum();
        if total.is_zero() {
            None
        } else {
            Some(total)
        }
    }
}

/// Wrapper to make any handler serializable (stores command representation)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializableHandler {
    /// Handler type
    handler_type: String,
    /// Serialized configuration
    config: serde_json::Value,
}

impl SerializableHandler {
    /// Create from a command handler
    pub fn from_command(handler: &CommandHandler) -> Result<Self> {
        Ok(Self {
            handler_type: "command".to_string(),
            config: serde_json::to_value(handler)?,
        })
    }

    /// Reconstruct the handler
    pub fn into_handler(self) -> Result<BoxedHandler> {
        match self.handler_type.as_str() {
            "command" => {
                let handler: CommandHandler = serde_json::from_value(self.config)?;
                Ok(Box::new(handler))
            }
            _ => Err(SchedulerError::ExecutionError(format!(
                "unknown handler type: {}",
                self.handler_type
            ))),
        }
    }
}

/// Trait for handlers that can provide progress updates
pub trait ProgressHandler: JobHandler {
    /// Get current progress (0-100)
    fn progress(&self) -> u8;

    /// Get progress message
    fn progress_message(&self) -> Option<String> {
        None
    }
}

/// Trait for handlers that support cancellation
pub trait CancellableHandler: JobHandler {
    /// Request cancellation
    fn cancel(&self);

    /// Check if cancellation was requested
    fn is_cancelled(&self) -> bool;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_handler_simple() {
        let handler = CommandHandler::new("echo").args(["hello"]);
        let result = handler.execute().unwrap();
        assert!(result.success);
    }

    #[test]
    fn test_command_handler_with_env() {
        let handler = CommandHandler::new("echo")
            .args(["$TEST_VAR"])
            .env("TEST_VAR", "hello");

        assert_eq!(handler.handler_type(), "command");
        assert!(handler.is_serializable());
    }

    #[test]
    fn test_closure_handler() {
        let handler = ClosureHandler::new(|| Ok(()))
            .with_description("test closure");

        let result = handler.execute().unwrap();
        assert!(result.success);
        assert_eq!(handler.handler_type(), "closure");
        assert!(!handler.is_serializable());
    }

    #[test]
    fn test_chained_handler() {
        let handler = ChainedHandler::new()
            .then(CommandHandler::new("echo").args(["first"]))
            .then(CommandHandler::new("echo").args(["second"]))
            .with_description("test chain");

        assert_eq!(handler.handlers.len(), 2);
        assert_eq!(handler.handler_type(), "chained");
    }

    #[test]
    fn test_boxed_handler() {
        let handlers: Vec<BoxedHandler> = vec![
            Box::new(CommandHandler::new("echo hello")),
            Box::new(ClosureHandler::new(|| Ok(()))),
        ];

        assert_eq!(handlers.len(), 2);
    }
}
