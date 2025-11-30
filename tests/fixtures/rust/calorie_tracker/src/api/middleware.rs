//! HTTP middleware for authentication, rate limiting, etc.

use axum::{
    extract::Request,
    http::{header, StatusCode},
    middleware::Next,
    response::Response,
};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, warn};

/// Simple in-memory rate limiter
pub struct RateLimiter {
    /// Map of IP -> (request count, window start)
    requests: RwLock<HashMap<String, (u32, Instant)>>,
    /// Maximum requests per window
    max_requests: u32,
    /// Window duration
    window: Duration,
}

impl RateLimiter {
    pub fn new(max_requests: u32, window_seconds: u64) -> Self {
        Self {
            requests: RwLock::new(HashMap::new()),
            max_requests,
            window: Duration::from_secs(window_seconds),
        }
    }

    /// Check if a request should be allowed
    pub async fn check(&self, key: &str) -> bool {
        let mut requests = self.requests.write().await;
        let now = Instant::now();

        match requests.get_mut(key) {
            Some((count, window_start)) => {
                if now.duration_since(*window_start) > self.window {
                    // Window expired, reset
                    *count = 1;
                    *window_start = now;
                    true
                } else if *count >= self.max_requests {
                    // Rate limited
                    false
                } else {
                    *count += 1;
                    true
                }
            }
            None => {
                requests.insert(key.to_string(), (1, now));
                true
            }
        }
    }

    /// Clean up expired entries
    pub async fn cleanup(&self) {
        let mut requests = self.requests.write().await;
        let now = Instant::now();

        requests.retain(|_, (_, window_start)| {
            now.duration_since(*window_start) <= self.window
        });
    }
}

/// Rate limiting middleware
pub async fn rate_limit_middleware(
    request: Request,
    next: Next,
    limiter: Arc<RateLimiter>,
) -> Result<Response, StatusCode> {
    // Get client IP from headers or connection
    let ip = request
        .headers()
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.split(',').next().unwrap_or("unknown"))
        .unwrap_or("unknown");

    if !limiter.check(ip).await {
        warn!("Rate limited request from: {}", ip);
        return Err(StatusCode::TOO_MANY_REQUESTS);
    }

    Ok(next.run(request).await)
}

/// Authentication token extractor
pub struct AuthToken(pub String);

/// Extract bearer token from Authorization header
pub fn extract_bearer_token(request: &Request) -> Option<String> {
    request
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|auth| {
            if auth.starts_with("Bearer ") {
                Some(auth[7..].to_string())
            } else {
                None
            }
        })
}

/// Logging middleware
pub async fn logging_middleware(request: Request, next: Next) -> Response {
    let method = request.method().clone();
    let uri = request.uri().clone();
    let start = Instant::now();

    let response = next.run(request).await;

    let duration = start.elapsed();
    let status = response.status();

    debug!(
        "{} {} -> {} ({:?})",
        method, uri, status.as_u16(), duration
    );

    response
}

/// Request ID middleware - adds a unique ID to each request
pub async fn request_id_middleware(mut request: Request, next: Next) -> Response {
    let request_id = uuid::Uuid::new_v4().to_string();

    // Add to request extensions
    request.extensions_mut().insert(RequestId(request_id.clone()));

    let mut response = next.run(request).await;

    // Add to response headers
    response.headers_mut().insert(
        "x-request-id",
        request_id.parse().unwrap(),
    );

    response
}

/// Request ID extension type
#[derive(Clone)]
pub struct RequestId(pub String);

/// CORS preflight handler
pub async fn cors_preflight() -> Response {
    Response::builder()
        .status(StatusCode::NO_CONTENT)
        .header("access-control-allow-origin", "*")
        .header("access-control-allow-methods", "GET, POST, PUT, DELETE, OPTIONS")
        .header("access-control-allow-headers", "content-type, authorization")
        .header("access-control-max-age", "86400")
        .body(axum::body::Body::empty())
        .unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_rate_limiter_allows_within_limit() {
        let limiter = RateLimiter::new(5, 60);

        for _ in 0..5 {
            assert!(limiter.check("test-ip").await);
        }
    }

    #[tokio::test]
    async fn test_rate_limiter_blocks_over_limit() {
        let limiter = RateLimiter::new(2, 60);

        assert!(limiter.check("test-ip").await);
        assert!(limiter.check("test-ip").await);
        assert!(!limiter.check("test-ip").await); // Should be blocked
    }

    #[tokio::test]
    async fn test_rate_limiter_separate_keys() {
        let limiter = RateLimiter::new(1, 60);

        assert!(limiter.check("ip1").await);
        assert!(limiter.check("ip2").await); // Different key, should pass
        assert!(!limiter.check("ip1").await); // Same key, blocked
    }
}
