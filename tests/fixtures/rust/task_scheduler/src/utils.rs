//! Utility functions and helpers
//!
//! Common functionality used across the library.

use chrono::{DateTime, Duration, Utc};
use std::time::Instant;

/// Format a duration in human-readable form
///
/// # Examples
///
/// ```rust
/// use task_scheduler::utils::format_duration;
/// use chrono::Duration;
///
/// assert_eq!(format_duration(Duration::seconds(45)), "45s");
/// assert_eq!(format_duration(Duration::minutes(5)), "5m 0s");
/// assert_eq!(format_duration(Duration::hours(2)), "2h 0m");
/// ```
pub fn format_duration(duration: Duration) -> String {
    let total_secs = duration.num_seconds();

    if total_secs < 0 {
        return format!("-{}", format_duration(Duration::seconds(-total_secs)));
    }

    if total_secs < 60 {
        return format!("{}s", total_secs);
    }

    let minutes = total_secs / 60;
    let secs = total_secs % 60;

    if minutes < 60 {
        return format!("{}m {}s", minutes, secs);
    }

    let hours = minutes / 60;
    let mins = minutes % 60;

    if hours < 24 {
        return format!("{}h {}m", hours, mins);
    }

    let days = hours / 24;
    let hrs = hours % 24;

    format!("{}d {}h", days, hrs)
}

/// Format a timestamp relative to now
///
/// # Examples
///
/// ```rust
/// use task_scheduler::utils::format_relative_time;
/// use chrono::Utc;
///
/// let now = Utc::now();
/// assert_eq!(format_relative_time(now), "just now");
/// ```
pub fn format_relative_time(dt: DateTime<Utc>) -> String {
    let now = Utc::now();
    let diff = now.signed_duration_since(dt);

    if diff.num_seconds().abs() < 5 {
        return "just now".to_string();
    }

    let (duration, suffix) = if diff.num_seconds() > 0 {
        (diff, "ago")
    } else {
        (-diff, "from now")
    };

    format!("{} {}", format_duration(duration), suffix)
}

/// Parse a duration string
///
/// Supports formats like:
/// - "30s" (30 seconds)
/// - "5m" (5 minutes)
/// - "2h" (2 hours)
/// - "1d" (1 day)
/// - "1h30m" (1 hour 30 minutes)
pub fn parse_duration(s: &str) -> Option<Duration> {
    let s = s.trim().to_lowercase();

    if s.is_empty() {
        return None;
    }

    let mut total_secs: i64 = 0;
    let mut current_num = String::new();

    for c in s.chars() {
        if c.is_ascii_digit() {
            current_num.push(c);
        } else if !current_num.is_empty() {
            let num: i64 = current_num.parse().ok()?;
            current_num.clear();

            let multiplier = match c {
                's' => 1,
                'm' => 60,
                'h' => 3600,
                'd' => 86400,
                'w' => 604800,
                _ => return None,
            };

            total_secs += num * multiplier;
        }
    }

    // Handle bare number (assume seconds)
    if !current_num.is_empty() {
        total_secs += current_num.parse::<i64>().ok()?;
    }

    if total_secs > 0 {
        Some(Duration::seconds(total_secs))
    } else {
        None
    }
}

/// Simple timer for measuring elapsed time
#[derive(Debug)]
pub struct Timer {
    start: Instant,
    label: String,
}

impl Timer {
    /// Start a new timer
    pub fn start(label: impl Into<String>) -> Self {
        Self {
            start: Instant::now(),
            label: label.into(),
        }
    }

    /// Get elapsed duration
    pub fn elapsed(&self) -> std::time::Duration {
        self.start.elapsed()
    }

    /// Get elapsed milliseconds
    pub fn elapsed_ms(&self) -> u64 {
        self.elapsed().as_millis() as u64
    }

    /// Stop and print elapsed time
    pub fn stop(self) {
        println!("[{}] completed in {:?}", self.label, self.elapsed());
    }

    /// Stop and return elapsed milliseconds
    pub fn stop_ms(self) -> u64 {
        self.elapsed_ms()
    }
}

/// Truncate a string to maximum length with ellipsis
pub fn truncate(s: &str, max_len: usize) -> String {
    if s.len() <= max_len {
        s.to_string()
    } else if max_len <= 3 {
        s[..max_len].to_string()
    } else {
        format!("{}...", &s[..max_len - 3])
    }
}

/// Slugify a string (lowercase, replace spaces with hyphens)
pub fn slugify(s: &str) -> String {
    s.trim()
        .to_lowercase()
        .chars()
        .map(|c| {
            if c.is_alphanumeric() {
                c
            } else if c.is_whitespace() || c == '_' {
                '-'
            } else {
                '-'
            }
        })
        .collect::<String>()
        .split('-')
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join("-")
}

/// Validate a job name
pub fn is_valid_job_name(name: &str) -> bool {
    if name.is_empty() || name.len() > crate::MAX_JOB_NAME_LEN {
        return false;
    }

    name.chars()
        .all(|c| c.is_alphanumeric() || c == '_' || c == '-')
}

/// Extension trait for Option to provide or_try functionality
pub trait OptionExt<T> {
    /// Try to get value or compute with fallible function
    fn or_try<E, F>(self, f: F) -> Result<T, E>
    where
        F: FnOnce() -> Result<T, E>;
}

impl<T> OptionExt<T> for Option<T> {
    fn or_try<E, F>(self, f: F) -> Result<T, E>
    where
        F: FnOnce() -> Result<T, E>,
    {
        match self {
            Some(v) => Ok(v),
            None => f(),
        }
    }
}

/// Extension trait for Result to add context
pub trait ResultExt<T, E> {
    /// Add context to an error
    fn context(self, ctx: impl Into<String>) -> Result<T, String>
    where
        E: std::fmt::Display;
}

impl<T, E: std::fmt::Display> ResultExt<T, E> for Result<T, E> {
    fn context(self, ctx: impl Into<String>) -> Result<T, String> {
        self.map_err(|e| format!("{}: {}", ctx.into(), e))
    }
}

/// Retry a fallible operation with exponential backoff
pub fn retry<T, E, F>(mut attempts: u8, mut f: F) -> Result<T, E>
where
    F: FnMut() -> Result<T, E>,
{
    loop {
        match f() {
            Ok(v) => return Ok(v),
            Err(e) if attempts > 1 => {
                attempts -= 1;
                std::thread::sleep(std::time::Duration::from_millis(100 * (4 - attempts) as u64));
            }
            Err(e) => return Err(e),
        }
    }
}

/// Generate a random alphanumeric string
pub fn random_string(len: usize) -> String {
    use std::time::{SystemTime, UNIX_EPOCH};

    // Simple pseudo-random using system time
    let seed = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();

    let chars: Vec<char> = "abcdefghijklmnopqrstuvwxyz0123456789".chars().collect();
    let mut result = String::with_capacity(len);
    let mut state = seed as u64;

    for _ in 0..len {
        // Simple LCG
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        let idx = (state >> 32) as usize % chars.len();
        result.push(chars[idx]);
    }

    result
}

/// Environment helpers
pub mod env {
    use std::env;
    use std::path::PathBuf;

    /// Get config directory
    pub fn config_dir() -> Option<PathBuf> {
        if let Ok(dir) = env::var("TASKCTL_CONFIG_DIR") {
            return Some(PathBuf::from(dir));
        }

        dirs_next::config_dir().map(|d| d.join("taskctl"))
    }

    /// Get data directory
    pub fn data_dir() -> Option<PathBuf> {
        if let Ok(dir) = env::var("TASKCTL_DATA_DIR") {
            return Some(PathBuf::from(dir));
        }

        dirs_next::data_dir().map(|d| d.join("taskctl"))
    }

    /// Get a boolean environment variable
    pub fn get_bool(name: &str, default: bool) -> bool {
        env::var(name)
            .map(|v| matches!(v.to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
            .unwrap_or(default)
    }

    /// Get a numeric environment variable
    pub fn get_u64(name: &str, default: u64) -> u64 {
        env::var(name)
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(default)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_duration() {
        assert_eq!(format_duration(Duration::seconds(45)), "45s");
        assert_eq!(format_duration(Duration::seconds(90)), "1m 30s");
        assert_eq!(format_duration(Duration::minutes(65)), "1h 5m");
        assert_eq!(format_duration(Duration::hours(25)), "1d 1h");
    }

    #[test]
    fn test_parse_duration() {
        assert_eq!(parse_duration("30s"), Some(Duration::seconds(30)));
        assert_eq!(parse_duration("5m"), Some(Duration::minutes(5)));
        assert_eq!(parse_duration("2h"), Some(Duration::hours(2)));
        assert_eq!(parse_duration("1d"), Some(Duration::days(1)));
        assert_eq!(parse_duration("1h30m"), Some(Duration::seconds(5400)));
        assert_eq!(parse_duration(""), None);
        assert_eq!(parse_duration("invalid"), None);
    }

    #[test]
    fn test_truncate() {
        assert_eq!(truncate("hello", 10), "hello");
        assert_eq!(truncate("hello world", 8), "hello...");
        assert_eq!(truncate("ab", 2), "ab");
    }

    #[test]
    fn test_slugify() {
        assert_eq!(slugify("Hello World"), "hello-world");
        assert_eq!(slugify("  My  Job  "), "my-job");
        assert_eq!(slugify("job_name"), "job-name");
        assert_eq!(slugify("Job123"), "job123");
    }

    #[test]
    fn test_is_valid_job_name() {
        assert!(is_valid_job_name("my-job"));
        assert!(is_valid_job_name("job_123"));
        assert!(is_valid_job_name("backup"));
        assert!(!is_valid_job_name(""));
        assert!(!is_valid_job_name("my job")); // spaces not allowed
        assert!(!is_valid_job_name("job@123")); // special chars not allowed
    }

    #[test]
    fn test_option_ext() {
        let some: Option<i32> = Some(5);
        let none: Option<i32> = None;

        assert_eq!(some.or_try(|| Ok::<_, ()>(10)), Ok(5));
        assert_eq!(none.or_try(|| Ok::<_, ()>(10)), Ok(10));
        assert_eq!(none.or_try(|| Err::<i32, _>("error")), Err("error"));
    }

    #[test]
    fn test_result_ext() {
        let ok: Result<i32, &str> = Ok(5);
        let err: Result<i32, &str> = Err("failed");

        assert_eq!(ok.context("operation"), Ok(5));
        assert_eq!(err.context("operation"), Err("operation: failed".to_string()));
    }

    #[test]
    fn test_random_string() {
        let s1 = random_string(8);
        let s2 = random_string(8);

        assert_eq!(s1.len(), 8);
        assert_eq!(s2.len(), 8);
        // Note: These might be the same if called in same nanosecond
        // In practice this is fine for non-crypto use
    }

    #[test]
    fn test_timer() {
        let timer = Timer::start("test");
        std::thread::sleep(std::time::Duration::from_millis(10));
        let elapsed = timer.elapsed_ms();
        assert!(elapsed >= 10);
    }
}
