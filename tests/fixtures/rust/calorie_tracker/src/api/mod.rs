//! HTTP API module using axum.
//!
//! Provides RESTful endpoints for the calorie tracker.

mod handlers;
mod middleware;
mod responses;

use axum::{
    Router,
    routing::{get, post, put, delete},
    Extension,
};
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing::info;

use crate::storage::SqliteRepository;
use crate::Result;

pub use handlers::*;
pub use responses::*;

/// Application state shared across handlers
pub struct AppState {
    pub repository: SqliteRepository,
}

impl AppState {
    pub fn new(repository: SqliteRepository) -> Self {
        Self { repository }
    }
}

/// Create the API router with all routes
pub fn create_router(state: Arc<AppState>) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        // Health check
        .route("/health", get(handlers::health_check))

        // Food endpoints
        .route("/api/v1/foods", get(handlers::list_foods))
        .route("/api/v1/foods", post(handlers::create_food))
        .route("/api/v1/foods/search", get(handlers::search_foods))
        .route("/api/v1/foods/:id", get(handlers::get_food))
        .route("/api/v1/foods/:id", put(handlers::update_food))
        .route("/api/v1/foods/:id", delete(handlers::delete_food))
        .route("/api/v1/foods/barcode/:code", get(handlers::get_food_by_barcode))

        // Meal endpoints
        .route("/api/v1/meals", get(handlers::list_meals))
        .route("/api/v1/meals", post(handlers::create_meal))
        .route("/api/v1/meals/:id", get(handlers::get_meal))
        .route("/api/v1/meals/:id", put(handlers::update_meal))
        .route("/api/v1/meals/:id", delete(handlers::delete_meal))
        .route("/api/v1/meals/recent", get(handlers::recent_meals))

        // Summary endpoints
        .route("/api/v1/summary/today", get(handlers::today_summary))
        .route("/api/v1/summary/:date", get(handlers::daily_summary))
        .route("/api/v1/summary/range", get(handlers::summary_range))

        // Goal endpoints
        .route("/api/v1/goals", get(handlers::get_goals))
        .route("/api/v1/goals", post(handlers::set_goals))

        // User endpoints (if auth enabled)
        .route("/api/v1/users/register", post(handlers::register_user))
        .route("/api/v1/users/login", post(handlers::login_user))
        .route("/api/v1/users/me", get(handlers::get_current_user))

        // Add middleware
        .layer(Extension(state))
        .layer(TraceLayer::new_for_http())
        .layer(cors)
}

/// Start the HTTP server
pub async fn serve(host: &str, port: u16, repository: SqliteRepository) -> Result<()> {
    let state = Arc::new(AppState::new(repository));
    let app = create_router(state);

    let addr = format!("{}:{}", host, port);
    let listener = tokio::net::TcpListener::bind(&addr).await?;

    info!("API server listening on http://{}", addr);

    axum::serve(listener, app)
        .await
        .map_err(|e| crate::CalorieTrackerError::internal(e))?;

    Ok(())
}
