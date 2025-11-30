//! API response types and error handling.

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;

use crate::models::Page;
use crate::CalorieTrackerError;

/// Standard API response wrapper
#[derive(Serialize)]
pub struct ApiResponse<T: Serialize> {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<T>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<ErrorDetail>,
}

#[derive(Serialize)]
pub struct ErrorDetail {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub field: Option<String>,
}

impl<T: Serialize> ApiResponse<T> {
    pub fn success(data: T) -> Self {
        Self {
            success: true,
            data: Some(data),
            error: None,
        }
    }

    pub fn error(code: impl Into<String>, message: impl Into<String>) -> ApiResponse<()> {
        ApiResponse {
            success: false,
            data: None,
            error: Some(ErrorDetail {
                code: code.into(),
                message: message.into(),
                field: None,
            }),
        }
    }
}

/// Paginated response wrapper
#[derive(Serialize)]
pub struct PaginatedResponse<T: Serialize> {
    pub success: bool,
    pub data: Vec<T>,
    pub pagination: PaginationMeta,
}

#[derive(Serialize)]
pub struct PaginationMeta {
    pub page: usize,
    pub page_size: usize,
    pub total_items: usize,
    pub total_pages: usize,
    pub has_next: bool,
    pub has_prev: bool,
}

impl<T: Serialize> PaginatedResponse<T> {
    pub fn from_page(page: Page<T>) -> Self {
        Self {
            success: true,
            data: page.items,
            pagination: PaginationMeta {
                page: page.page,
                page_size: page.page_size,
                total_items: page.total,
                total_pages: page.total_pages(),
                has_next: page.has_next(),
                has_prev: page.has_prev(),
            },
        }
    }
}

/// API error type that implements IntoResponse
#[derive(Debug)]
pub struct ApiError {
    pub status: StatusCode,
    pub code: String,
    pub message: String,
    pub field: Option<String>,
}

impl ApiError {
    pub fn new(status: StatusCode, code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            status,
            code: code.into(),
            message: message.into(),
            field: None,
        }
    }

    pub fn with_field(mut self, field: impl Into<String>) -> Self {
        self.field = Some(field.into());
        self
    }

    // Convenience constructors

    pub fn bad_request(message: impl Into<String>) -> Self {
        Self::new(StatusCode::BAD_REQUEST, "BAD_REQUEST", message)
    }

    pub fn unauthorized(message: impl Into<String>) -> Self {
        Self::new(StatusCode::UNAUTHORIZED, "UNAUTHORIZED", message)
    }

    pub fn forbidden(message: impl Into<String>) -> Self {
        Self::new(StatusCode::FORBIDDEN, "FORBIDDEN", message)
    }

    pub fn not_found(resource: &str, id: impl Into<String>) -> Self {
        Self::new(
            StatusCode::NOT_FOUND,
            "NOT_FOUND",
            format!("{} not found: {}", resource, id.into()),
        )
    }

    pub fn conflict(message: impl Into<String>) -> Self {
        Self::new(StatusCode::CONFLICT, "CONFLICT", message)
    }

    pub fn internal(message: impl Into<String>) -> Self {
        Self::new(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", message)
    }

    pub fn rate_limited(retry_after_secs: u64) -> Self {
        Self::new(
            StatusCode::TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            format!("Rate limit exceeded. Retry after {} seconds.", retry_after_secs),
        )
    }

    pub fn validation(field: impl Into<String>, message: impl Into<String>) -> Self {
        Self::new(StatusCode::BAD_REQUEST, "VALIDATION_ERROR", message)
            .with_field(field)
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let body = ApiResponse::<()> {
            success: false,
            data: None,
            error: Some(ErrorDetail {
                code: self.code,
                message: self.message,
                field: self.field,
            }),
        };

        (self.status, Json(body)).into_response()
    }
}

impl From<CalorieTrackerError> for ApiError {
    fn from(err: CalorieTrackerError) -> Self {
        match err {
            CalorieTrackerError::NotFound { resource, id } => {
                Self::not_found(resource, id)
            }
            CalorieTrackerError::InvalidInput(msg) => {
                Self::bad_request(msg)
            }
            CalorieTrackerError::Validation { field, message } => {
                Self::validation(field, message)
            }
            CalorieTrackerError::AuthError(msg) => {
                Self::unauthorized(msg)
            }
            CalorieTrackerError::RateLimited { retry_after_secs } => {
                Self::rate_limited(retry_after_secs)
            }
            CalorieTrackerError::Database(e) => {
                tracing::error!("Database error: {}", e);
                Self::internal("Database error")
            }
            CalorieTrackerError::Io(e) => {
                tracing::error!("IO error: {}", e);
                Self::internal("IO error")
            }
            CalorieTrackerError::Config(msg) => {
                Self::internal(format!("Configuration error: {}", msg))
            }
            CalorieTrackerError::Serialization(e) => {
                tracing::error!("Serialization error: {}", e);
                Self::internal("Serialization error")
            }
            CalorieTrackerError::Internal(e) => {
                tracing::error!("Internal error: {}", e);
                Self::internal("Internal error")
            }
        }
    }
}

/// Result type alias for API handlers
pub type ApiResult<T> = Result<Json<ApiResponse<T>>, ApiError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_api_response_success() {
        let response = ApiResponse::success("hello");
        assert!(response.success);
        assert_eq!(response.data.unwrap(), "hello");
        assert!(response.error.is_none());
    }

    #[test]
    fn test_api_response_error() {
        let response = ApiResponse::<()>::error("TEST", "Test error");
        assert!(!response.success);
        assert!(response.data.is_none());
        assert_eq!(response.error.unwrap().code, "TEST");
    }

    #[test]
    fn test_api_error_status_codes() {
        assert_eq!(ApiError::bad_request("test").status, StatusCode::BAD_REQUEST);
        assert_eq!(ApiError::unauthorized("test").status, StatusCode::UNAUTHORIZED);
        assert_eq!(ApiError::not_found("User", "123").status, StatusCode::NOT_FOUND);
    }

    #[test]
    fn test_pagination_meta() {
        let page = Page::new(vec![1, 2, 3], 10, 0, 3);
        let response = PaginatedResponse::from_page(page);

        assert!(response.success);
        assert_eq!(response.pagination.total_items, 10);
        assert_eq!(response.pagination.total_pages, 4);
        assert!(response.pagination.has_next);
        assert!(!response.pagination.has_prev);
    }
}
