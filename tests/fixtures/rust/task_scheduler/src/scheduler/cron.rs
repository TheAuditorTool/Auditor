//! Cron expression parser and scheduler
//!
//! Supports standard 5-field cron expressions:
//! ```text
//! ┌───────────── minute (0-59)
//! │ ┌───────────── hour (0-23)
//! │ │ ┌───────────── day of month (1-31)
//! │ │ │ ┌───────────── month (1-12)
//! │ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
//! │ │ │ │ │
//! * * * * *
//! ```
//!
//! Special characters:
//! - `*`: Any value
//! - `,`: Value list separator
//! - `-`: Range of values
//! - `/`: Step values

use crate::{Result, SchedulerError};
use chrono::{DateTime, Datelike, Timelike, Utc, Duration};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fmt;
use std::str::FromStr;

/// A parsed cron expression
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CronExpression {
    /// Original expression string
    expression: String,
    /// Allowed minutes (0-59)
    minutes: FieldValues,
    /// Allowed hours (0-23)
    hours: FieldValues,
    /// Allowed days of month (1-31)
    days_of_month: FieldValues,
    /// Allowed months (1-12)
    months: FieldValues,
    /// Allowed days of week (0-6)
    days_of_week: FieldValues,
}

/// Values allowed for a cron field
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FieldValues {
    /// Set of allowed values
    values: BTreeSet<u8>,
    /// Whether this is a wildcard (any value)
    is_wildcard: bool,
}

impl FieldValues {
    /// Create a wildcard field
    fn wildcard(min: u8, max: u8) -> Self {
        Self {
            values: (min..=max).collect(),
            is_wildcard: true,
        }
    }

    /// Create from specific values
    fn from_values(values: impl IntoIterator<Item = u8>) -> Self {
        Self {
            values: values.into_iter().collect(),
            is_wildcard: false,
        }
    }

    /// Check if a value is allowed
    fn contains(&self, value: u8) -> bool {
        self.values.contains(&value)
    }

    /// Get next valid value >= given value
    fn next_value(&self, current: u8) -> Option<u8> {
        self.values.range(current..).next().copied()
    }

    /// Get first valid value
    fn first(&self) -> Option<u8> {
        self.values.iter().next().copied()
    }

    /// Parse a field from string
    fn parse(s: &str, min: u8, max: u8) -> Result<Self> {
        let s = s.trim();

        if s == "*" {
            return Ok(Self::wildcard(min, max));
        }

        let mut values = BTreeSet::new();

        for part in s.split(',') {
            let part = part.trim();

            if part.contains('/') {
                // Step values: */5 or 1-10/2
                let parts: Vec<&str> = part.splitn(2, '/').collect();
                let step: u8 = parts[1]
                    .parse()
                    .map_err(|_| SchedulerError::invalid_cron(s, "invalid step value"))?;

                if step == 0 {
                    return Err(SchedulerError::invalid_cron(s, "step cannot be 0"));
                }

                let (range_start, range_end) = if parts[0] == "*" {
                    (min, max)
                } else if parts[0].contains('-') {
                    parse_range(parts[0], min, max)?
                } else {
                    let start: u8 = parts[0]
                        .parse()
                        .map_err(|_| SchedulerError::invalid_cron(s, "invalid value"))?;
                    (start, max)
                };

                for v in (range_start..=range_end).step_by(step as usize) {
                    values.insert(v);
                }
            } else if part.contains('-') {
                // Range: 1-5
                let (start, end) = parse_range(part, min, max)?;
                for v in start..=end {
                    values.insert(v);
                }
            } else {
                // Single value
                let value: u8 = part
                    .parse()
                    .map_err(|_| SchedulerError::invalid_cron(s, "invalid value"))?;

                if value < min || value > max {
                    return Err(SchedulerError::invalid_cron(
                        s,
                        "value out of range",
                    ));
                }

                values.insert(value);
            }
        }

        if values.is_empty() {
            return Err(SchedulerError::invalid_cron(s, "no valid values"));
        }

        Ok(Self::from_values(values))
    }
}

fn parse_range(s: &str, min: u8, max: u8) -> Result<(u8, u8)> {
    let parts: Vec<&str> = s.splitn(2, '-').collect();
    if parts.len() != 2 {
        return Err(SchedulerError::invalid_cron(s, "invalid range syntax"));
    }

    let start: u8 = parts[0]
        .trim()
        .parse()
        .map_err(|_| SchedulerError::invalid_cron(s, "invalid range start"))?;
    let end: u8 = parts[1]
        .trim()
        .parse()
        .map_err(|_| SchedulerError::invalid_cron(s, "invalid range end"))?;

    if start < min || end > max || start > end {
        return Err(SchedulerError::invalid_cron(s, "range out of bounds"));
    }

    Ok((start, end))
}

impl CronExpression {
    /// Parse a cron expression from string
    ///
    /// # Format
    ///
    /// Standard 5-field format: `minute hour day-of-month month day-of-week`
    ///
    /// # Examples
    ///
    /// ```rust
    /// use task_scheduler::scheduler::CronExpression;
    ///
    /// // Every minute
    /// let expr = CronExpression::parse("* * * * *").unwrap();
    ///
    /// // Every hour at minute 0
    /// let expr = CronExpression::parse("0 * * * *").unwrap();
    ///
    /// // Daily at 2:30 AM
    /// let expr = CronExpression::parse("30 2 * * *").unwrap();
    ///
    /// // Every 5 minutes
    /// let expr = CronExpression::parse("*/5 * * * *").unwrap();
    ///
    /// // Weekdays at 9 AM
    /// let expr = CronExpression::parse("0 9 * * 1-5").unwrap();
    /// ```
    pub fn parse(expression: &str) -> Result<Self> {
        let expression = expression.trim();
        let fields: Vec<&str> = expression.split_whitespace().collect();

        if fields.len() != 5 {
            return Err(SchedulerError::invalid_cron(
                expression,
                "expected 5 fields (minute hour day month weekday)",
            ));
        }

        Ok(Self {
            expression: expression.to_string(),
            minutes: FieldValues::parse(fields[0], 0, 59)?,
            hours: FieldValues::parse(fields[1], 0, 23)?,
            days_of_month: FieldValues::parse(fields[2], 1, 31)?,
            months: FieldValues::parse(fields[3], 1, 12)?,
            days_of_week: FieldValues::parse(fields[4], 0, 6)?,
        })
    }

    /// Get the original expression string
    pub fn expression(&self) -> &str {
        &self.expression
    }

    /// Check if a given time matches this cron expression
    pub fn matches(&self, dt: DateTime<Utc>) -> bool {
        self.minutes.contains(dt.minute() as u8)
            && self.hours.contains(dt.hour() as u8)
            && self.days_of_month.contains(dt.day() as u8)
            && self.months.contains(dt.month() as u8)
            && self.days_of_week.contains(dt.weekday().num_days_from_sunday() as u8)
    }

    /// Calculate the next occurrence after the given time
    ///
    /// Returns `None` if no valid time found within 4 years (handles edge cases)
    pub fn next_occurrence(&self, after: DateTime<Utc>) -> Option<DateTime<Utc>> {
        let mut dt = after + Duration::minutes(1);
        // Zero out seconds and nanoseconds
        dt = dt
            .with_second(0)?
            .with_nanosecond(0)?;

        let max_iterations = 366 * 24 * 60 * 4; // ~4 years of minutes
        let mut iterations = 0;

        while iterations < max_iterations {
            iterations += 1;

            // Check month
            if !self.months.contains(dt.month() as u8) {
                if let Some(next_month) = self.months.next_value(dt.month() as u8) {
                    // Advance to next valid month
                    dt = advance_to_month(dt, next_month as u32)?;
                } else {
                    // No valid month this year, go to first valid month next year
                    let first_month = self.months.first()?;
                    dt = dt
                        .with_year(dt.year() + 1)?
                        .with_month(first_month as u32)?
                        .with_day(1)?
                        .with_hour(0)?
                        .with_minute(0)?;
                }
                continue;
            }

            // Check day of month and day of week
            let day_matches = self.days_of_month.contains(dt.day() as u8);
            let dow_matches = self.days_of_week.contains(dt.weekday().num_days_from_sunday() as u8);

            // Both must match (unless one is wildcard)
            let day_ok = if self.days_of_month.is_wildcard || self.days_of_week.is_wildcard {
                day_matches || dow_matches
            } else {
                day_matches && dow_matches
            };

            if !day_ok {
                // Advance to next day
                dt = dt
                    .checked_add_signed(Duration::days(1))?
                    .with_hour(0)?
                    .with_minute(0)?;
                continue;
            }

            // Check hour
            if !self.hours.contains(dt.hour() as u8) {
                if let Some(next_hour) = self.hours.next_value(dt.hour() as u8) {
                    dt = dt.with_hour(next_hour as u32)?.with_minute(0)?;
                } else {
                    // No valid hour today, go to next day
                    dt = dt
                        .checked_add_signed(Duration::days(1))?
                        .with_hour(self.hours.first()? as u32)?
                        .with_minute(0)?;
                }
                continue;
            }

            // Check minute
            if !self.minutes.contains(dt.minute() as u8) {
                if let Some(next_minute) = self.minutes.next_value(dt.minute() as u8) {
                    dt = dt.with_minute(next_minute as u32)?;
                } else {
                    // No valid minute this hour, go to next hour
                    dt = dt
                        .checked_add_signed(Duration::hours(1))?
                        .with_minute(self.minutes.first()? as u32)?;
                }
                continue;
            }

            // All fields match
            return Some(dt);
        }

        None // No valid occurrence found within search limit
    }

    /// Calculate occurrences between two times
    pub fn occurrences_between(
        &self,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Vec<DateTime<Utc>> {
        let mut result = Vec::new();
        let mut current = start;

        while let Some(next) = self.next_occurrence(current) {
            if next > end {
                break;
            }
            result.push(next);
            current = next;
        }

        result
    }

    /// Get a human-readable description of the schedule
    pub fn describe(&self) -> String {
        // Simple description for common patterns
        match self.expression.as_str() {
            "* * * * *" => "every minute".to_string(),
            "0 * * * *" => "every hour".to_string(),
            "0 0 * * *" => "daily at midnight".to_string(),
            "0 0 * * 0" => "weekly on Sunday".to_string(),
            "0 0 1 * *" => "monthly on the 1st".to_string(),
            _ => format!("cron: {}", self.expression),
        }
    }
}

fn advance_to_month(dt: DateTime<Utc>, month: u32) -> Option<DateTime<Utc>> {
    let year = if month <= dt.month() {
        dt.year() + 1
    } else {
        dt.year()
    };

    dt.with_year(year)?
        .with_month(month)?
        .with_day(1)?
        .with_hour(0)?
        .with_minute(0)
}

impl FromStr for CronExpression {
    type Err = SchedulerError;

    fn from_str(s: &str) -> Result<Self> {
        Self::parse(s)
    }
}

impl fmt::Display for CronExpression {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.expression)
    }
}

/// Common cron presets
pub mod presets {
    use super::CronExpression;

    /// Every minute
    pub fn every_minute() -> CronExpression {
        CronExpression::parse("* * * * *").unwrap()
    }

    /// Every hour at minute 0
    pub fn hourly() -> CronExpression {
        CronExpression::parse("0 * * * *").unwrap()
    }

    /// Every day at midnight
    pub fn daily() -> CronExpression {
        CronExpression::parse("0 0 * * *").unwrap()
    }

    /// Every day at specified hour
    pub fn daily_at(hour: u8) -> CronExpression {
        CronExpression::parse(&format!("0 {} * * *", hour)).unwrap()
    }

    /// Every week on Sunday at midnight
    pub fn weekly() -> CronExpression {
        CronExpression::parse("0 0 * * 0").unwrap()
    }

    /// Every month on the 1st at midnight
    pub fn monthly() -> CronExpression {
        CronExpression::parse("0 0 1 * *").unwrap()
    }

    /// Weekdays at specified hour
    pub fn weekdays_at(hour: u8) -> CronExpression {
        CronExpression::parse(&format!("0 {} * * 1-5", hour)).unwrap()
    }

    /// Every N minutes
    pub fn every_n_minutes(n: u8) -> CronExpression {
        CronExpression::parse(&format!("*/{} * * * *", n)).unwrap()
    }

    /// Every N hours
    pub fn every_n_hours(n: u8) -> CronExpression {
        CronExpression::parse(&format!("0 */{} * * *", n)).unwrap()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn test_parse_every_minute() {
        let expr = CronExpression::parse("* * * * *").unwrap();
        assert!(expr.minutes.is_wildcard);
        assert!(expr.hours.is_wildcard);
    }

    #[test]
    fn test_parse_specific_time() {
        let expr = CronExpression::parse("30 2 * * *").unwrap();
        assert!(expr.minutes.contains(30));
        assert!(!expr.minutes.contains(0));
        assert!(expr.hours.contains(2));
        assert!(!expr.hours.contains(3));
    }

    #[test]
    fn test_parse_step_values() {
        let expr = CronExpression::parse("*/15 * * * *").unwrap();
        assert!(expr.minutes.contains(0));
        assert!(expr.minutes.contains(15));
        assert!(expr.minutes.contains(30));
        assert!(expr.minutes.contains(45));
        assert!(!expr.minutes.contains(5));
    }

    #[test]
    fn test_parse_range() {
        let expr = CronExpression::parse("0 9-17 * * *").unwrap();
        assert!(expr.hours.contains(9));
        assert!(expr.hours.contains(13));
        assert!(expr.hours.contains(17));
        assert!(!expr.hours.contains(8));
        assert!(!expr.hours.contains(18));
    }

    #[test]
    fn test_parse_list() {
        let expr = CronExpression::parse("0 0 * * 0,6").unwrap();
        assert!(expr.days_of_week.contains(0)); // Sunday
        assert!(expr.days_of_week.contains(6)); // Saturday
        assert!(!expr.days_of_week.contains(1)); // Monday
    }

    #[test]
    fn test_invalid_expression() {
        assert!(CronExpression::parse("* * *").is_err()); // Too few fields
        assert!(CronExpression::parse("60 * * * *").is_err()); // Invalid minute
        assert!(CronExpression::parse("* 25 * * *").is_err()); // Invalid hour
    }

    #[test]
    fn test_matches() {
        let expr = CronExpression::parse("30 14 * * *").unwrap();
        let dt = Utc.with_ymd_and_hms(2024, 1, 15, 14, 30, 0).unwrap();
        assert!(expr.matches(dt));

        let wrong_time = Utc.with_ymd_and_hms(2024, 1, 15, 14, 31, 0).unwrap();
        assert!(!expr.matches(wrong_time));
    }

    #[test]
    fn test_next_occurrence() {
        let expr = CronExpression::parse("0 * * * *").unwrap(); // Every hour
        let now = Utc.with_ymd_and_hms(2024, 1, 15, 14, 30, 0).unwrap();
        let next = expr.next_occurrence(now).unwrap();

        assert_eq!(next.hour(), 15);
        assert_eq!(next.minute(), 0);
    }

    #[test]
    fn test_presets() {
        assert_eq!(presets::every_minute().expression(), "* * * * *");
        assert_eq!(presets::daily().expression(), "0 0 * * *");
        assert_eq!(presets::every_n_minutes(5).expression(), "*/5 * * * *");
    }
}
