//! Calorie Tracker Library
//!
//! A comprehensive nutrition tracking library for Rust applications.
//!
//! # Features
//!
//! - Track foods with full nutritional information
//! - Log meals by type (breakfast, lunch, dinner, snack)
//! - Set and monitor daily goals
//! - SQLite persistence with async support
//! - Optional HTTP API via axum
//!
//! # Example
//!
//! ```rust
//! use calorie_tracker::{models::Food, storage::SqliteRepository};
//!
//! #[tokio::main]
//! async fn main() -> calorie_tracker::Result<()> {
//!     let repo = SqliteRepository::new("calories.db").await?;
//!
//!     let food = Food::new("Apple", 95, 0.5, 25.0, 0.3, "1 medium");
//!     repo.save_food(&food).await?;
//!
//!     Ok(())
//! }
//! ```

pub mod models;
pub mod storage;
pub mod utils;

#[cfg(feature = "api")]
pub mod api;

use thiserror::Error;

/// Result type alias for calorie tracker operations
pub type Result<T> = std::result::Result<T, CalorieTrackerError>;

/// Errors that can occur in the calorie tracker
#[derive(Error, Debug)]
pub enum CalorieTrackerError {
    /// Database operation failed
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),

    /// Invalid user input
    #[error("Invalid input: {0}")]
    InvalidInput(String),

    /// Resource not found
    #[error("{resource} not found: {id}")]
    NotFound {
        resource: &'static str,
        id: String,
    },

    /// Authentication failed
    #[error("Authentication failed: {0}")]
    AuthError(String),

    /// Configuration error
    #[error("Configuration error: {0}")]
    Config(String),

    /// IO error
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// Serialization error
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Validation error with details
    #[error("Validation failed: {field} - {message}")]
    Validation {
        field: String,
        message: String,
    },

    /// Rate limit exceeded
    #[error("Rate limit exceeded, retry after {retry_after_secs} seconds")]
    RateLimited {
        retry_after_secs: u64,
    },

    /// Internal error (should not expose details to users)
    #[error("Internal error")]
    Internal(#[source] Box<dyn std::error::Error + Send + Sync>),
}

impl CalorieTrackerError {
    /// Create a not found error for a food item
    pub fn food_not_found(id: impl Into<String>) -> Self {
        Self::NotFound {
            resource: "Food",
            id: id.into(),
        }
    }

    /// Create a not found error for a meal
    pub fn meal_not_found(id: impl Into<String>) -> Self {
        Self::NotFound {
            resource: "Meal",
            id: id.into(),
        }
    }

    /// Create a not found error for a user
    pub fn user_not_found(id: impl Into<String>) -> Self {
        Self::NotFound {
            resource: "User",
            id: id.into(),
        }
    }

    /// Wrap an error as internal (hides details from users)
    pub fn internal<E>(error: E) -> Self
    where
        E: std::error::Error + Send + Sync + 'static,
    {
        Self::Internal(Box::new(error))
    }

    /// Check if this is a transient error that could be retried
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            Self::Database(_) | Self::RateLimited { .. } | Self::Io(_)
        )
    }

    /// Get HTTP status code for this error
    pub fn status_code(&self) -> u16 {
        match self {
            Self::NotFound { .. } => 404,
            Self::InvalidInput(_) | Self::Validation { .. } => 400,
            Self::AuthError(_) => 401,
            Self::RateLimited { .. } => 429,
            Self::Config(_) => 500,
            Self::Database(_) | Self::Io(_) | Self::Serialization(_) | Self::Internal(_) => 500,
        }
    }
}

// Re-export commonly used types for convenience
pub use models::{Food, Meal, MealType, User, DailyGoal, DailySummary};
pub use storage::{Repository, SqliteRepository};

/// Library version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Default database filename
pub const DEFAULT_DB_FILE: &str = "calories.db";

/// Maximum calories per food item (sanity check)
pub const MAX_CALORIES_PER_ITEM: u32 = 10_000;

/// Maximum protein per food item in grams
pub const MAX_PROTEIN_PER_ITEM: f32 = 500.0;

/// Validate that nutritional values are within reasonable bounds
pub fn validate_nutrition(calories: u32, protein: f32, carbs: f32, fat: f32) -> Result<()> {
    if calories > MAX_CALORIES_PER_ITEM {
        return Err(CalorieTrackerError::Validation {
            field: "calories".into(),
            message: format!("Cannot exceed {} kcal per item", MAX_CALORIES_PER_ITEM),
        });
    }

    if protein > MAX_PROTEIN_PER_ITEM || protein < 0.0 {
        return Err(CalorieTrackerError::Validation {
            field: "protein".into(),
            message: "Protein must be between 0 and 500g".into(),
        });
    }

    if carbs < 0.0 || carbs > 1000.0 {
        return Err(CalorieTrackerError::Validation {
            field: "carbs".into(),
            message: "Carbs must be between 0 and 1000g".into(),
        });
    }

    if fat < 0.0 || fat > 500.0 {
        return Err(CalorieTrackerError::Validation {
            field: "fat".into(),
            message: "Fat must be between 0 and 500g".into(),
        });
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_nutrition_valid() {
        assert!(validate_nutrition(500, 30.0, 50.0, 20.0).is_ok());
    }

    #[test]
    fn test_validate_nutrition_excessive_calories() {
        assert!(validate_nutrition(15000, 30.0, 50.0, 20.0).is_err());
    }

    #[test]
    fn test_validate_nutrition_negative_protein() {
        assert!(validate_nutrition(500, -5.0, 50.0, 20.0).is_err());
    }

    #[test]
    fn test_error_status_codes() {
        assert_eq!(CalorieTrackerError::food_not_found("123").status_code(), 404);
        assert_eq!(CalorieTrackerError::InvalidInput("bad".into()).status_code(), 400);
        assert_eq!(CalorieTrackerError::AuthError("denied".into()).status_code(), 401);
    }

    #[test]
    fn test_error_retryable() {
        assert!(CalorieTrackerError::RateLimited { retry_after_secs: 60 }.is_retryable());
        assert!(!CalorieTrackerError::InvalidInput("bad".into()).is_retryable());
    }
}
