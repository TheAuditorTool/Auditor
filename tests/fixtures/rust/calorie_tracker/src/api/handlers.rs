//! HTTP request handlers.

use axum::{
    extract::{Extension, Path, Query},
    http::StatusCode,
    Json,
};
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tracing::{debug, error, instrument};
use uuid::Uuid;

use crate::models::{Food, Meal, MealType, DailyGoal, User, NutritionInfo};
use crate::storage::Repository;
use crate::utils::{hash_password, verify_password, validate_email, validate_username};
use crate::{CalorieTrackerError, Result};

use super::AppState;
use super::responses::{ApiResponse, ApiError, PaginatedResponse};

// =============================================================================
// Health Check
// =============================================================================

/// Health check endpoint
#[instrument(skip_all)]
pub async fn health_check(
    Extension(state): Extension<Arc<AppState>>,
) -> Json<ApiResponse<HealthStatus>> {
    let health = state.repository.health_check().await;

    let status = HealthStatus {
        status: if health.healthy { "healthy" } else { "unhealthy" },
        database: health.healthy,
        latency_ms: health.latency_ms,
        version: env!("CARGO_PKG_VERSION"),
    };

    Json(ApiResponse::success(status))
}

#[derive(Serialize)]
pub struct HealthStatus {
    status: &'static str,
    database: bool,
    latency_ms: u64,
    version: &'static str,
}

// =============================================================================
// Food Handlers
// =============================================================================

#[derive(Deserialize)]
pub struct ListFoodsQuery {
    page: Option<usize>,
    page_size: Option<usize>,
}

/// List all foods with pagination
#[instrument(skip_all)]
pub async fn list_foods(
    Extension(state): Extension<Arc<AppState>>,
    Query(params): Query<ListFoodsQuery>,
) -> Result<Json<PaginatedResponse<Food>>, ApiError> {
    let page = params.page.unwrap_or(0);
    let page_size = params.page_size.unwrap_or(20).min(100);

    let result = state.repository.list_foods(page, page_size).await
        .map_err(ApiError::from)?;

    Ok(Json(PaginatedResponse::from_page(result)))
}

#[derive(Deserialize)]
pub struct SearchFoodsQuery {
    q: Option<String>,
    limit: Option<usize>,
}

/// Search foods by name
#[instrument(skip_all)]
pub async fn search_foods(
    Extension(state): Extension<Arc<AppState>>,
    Query(params): Query<SearchFoodsQuery>,
) -> Result<Json<ApiResponse<Vec<Food>>>, ApiError> {
    let limit = params.limit.unwrap_or(20).min(100);

    let foods = state.repository.search_foods(params.q.as_deref(), limit).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(foods)))
}

/// Get a single food by ID
#[instrument(skip_all)]
pub async fn get_food(
    Extension(state): Extension<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<ApiResponse<Food>>, ApiError> {
    let food = state.repository.get_food(id).await
        .map_err(ApiError::from)?
        .ok_or_else(|| ApiError::not_found("Food", id.to_string()))?;

    Ok(Json(ApiResponse::success(food)))
}

/// Get a food by barcode
#[instrument(skip_all)]
pub async fn get_food_by_barcode(
    Extension(state): Extension<Arc<AppState>>,
    Path(code): Path<String>,
) -> Result<Json<ApiResponse<Food>>, ApiError> {
    let food = state.repository.get_food_by_barcode(&code).await
        .map_err(ApiError::from)?
        .ok_or_else(|| ApiError::not_found("Food", code))?;

    Ok(Json(ApiResponse::success(food)))
}

#[derive(Deserialize)]
pub struct CreateFoodRequest {
    name: String,
    serving_size: String,
    calories: u32,
    protein: f32,
    carbs: f32,
    fat: f32,
    #[serde(default)]
    fiber: f32,
    #[serde(default)]
    sugar: f32,
    #[serde(default)]
    sodium: f32,
    brand: Option<String>,
    barcode: Option<String>,
}

/// Create a new food
#[instrument(skip_all)]
pub async fn create_food(
    Extension(state): Extension<Arc<AppState>>,
    Json(req): Json<CreateFoodRequest>,
) -> Result<(StatusCode, Json<ApiResponse<Food>>), ApiError> {
    let mut food = Food::new(
        req.name,
        req.calories,
        req.protein,
        req.carbs,
        req.fat,
        req.serving_size,
    );

    // Set additional fields
    food.nutrition.fiber = req.fiber;
    food.nutrition.sugar = req.sugar;
    food.nutrition.sodium = req.sodium;
    food.brand = req.brand;
    food.barcode = req.barcode;

    // Validate
    food.validate().map_err(ApiError::from)?;

    // Save
    let id = state.repository.save_food(&food).await
        .map_err(ApiError::from)?;

    food.id = id;
    debug!("Created food: {}", id);

    Ok((StatusCode::CREATED, Json(ApiResponse::success(food))))
}

/// Update an existing food
#[instrument(skip_all)]
pub async fn update_food(
    Extension(state): Extension<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(req): Json<CreateFoodRequest>,
) -> Result<Json<ApiResponse<Food>>, ApiError> {
    // Verify food exists
    let existing = state.repository.get_food(id).await
        .map_err(ApiError::from)?
        .ok_or_else(|| ApiError::not_found("Food", id.to_string()))?;

    let mut food = Food::new(
        req.name,
        req.calories,
        req.protein,
        req.carbs,
        req.fat,
        req.serving_size,
    );

    food.id = existing.id;
    food.created_at = existing.created_at;
    food.nutrition.fiber = req.fiber;
    food.nutrition.sugar = req.sugar;
    food.nutrition.sodium = req.sodium;
    food.brand = req.brand;
    food.barcode = req.barcode;

    food.validate().map_err(ApiError::from)?;

    state.repository.save_food(&food).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(food)))
}

/// Delete a food
#[instrument(skip_all)]
pub async fn delete_food(
    Extension(state): Extension<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, ApiError> {
    let deleted = state.repository.delete_food(id).await
        .map_err(ApiError::from)?;

    if deleted {
        Ok(StatusCode::NO_CONTENT)
    } else {
        Err(ApiError::not_found("Food", id.to_string()))
    }
}

// =============================================================================
// Meal Handlers
// =============================================================================

#[derive(Deserialize)]
pub struct ListMealsQuery {
    date: Option<String>,
    start_date: Option<String>,
    end_date: Option<String>,
}

/// List meals (optionally filtered by date)
#[instrument(skip_all)]
pub async fn list_meals(
    Extension(state): Extension<Arc<AppState>>,
    Query(params): Query<ListMealsQuery>,
) -> Result<Json<ApiResponse<Vec<Meal>>>, ApiError> {
    let meals = if let Some(date_str) = params.date {
        let date = parse_date(&date_str)?;
        state.repository.get_meals_for_date(date).await
            .map_err(ApiError::from)?
    } else if let (Some(start), Some(end)) = (params.start_date, params.end_date) {
        let start_date = parse_date(&start)?;
        let end_date = parse_date(&end)?;
        state.repository.get_meals_in_range(start_date, end_date).await
            .map_err(ApiError::from)?
    } else {
        // Default: today's meals
        let today = chrono::Local::now().date_naive();
        state.repository.get_meals_for_date(today).await
            .map_err(ApiError::from)?
    };

    Ok(Json(ApiResponse::success(meals)))
}

/// Get recent meals
#[instrument(skip_all)]
pub async fn recent_meals(
    Extension(state): Extension<Arc<AppState>>,
    Query(params): Query<LimitQuery>,
) -> Result<Json<ApiResponse<Vec<Meal>>>, ApiError> {
    let limit = params.limit.unwrap_or(10).min(50);

    let meals = state.repository.get_recent_meals(limit).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(meals)))
}

#[derive(Deserialize)]
pub struct LimitQuery {
    limit: Option<usize>,
}

/// Get a single meal
#[instrument(skip_all)]
pub async fn get_meal(
    Extension(state): Extension<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<ApiResponse<Meal>>, ApiError> {
    let meal = state.repository.get_meal(id).await
        .map_err(ApiError::from)?
        .ok_or_else(|| ApiError::not_found("Meal", id.to_string()))?;

    Ok(Json(ApiResponse::success(meal)))
}

#[derive(Deserialize)]
pub struct CreateMealRequest {
    meal_type: String,
    description: String,
    #[serde(default)]
    food_ids: Vec<Uuid>,
    date: Option<String>,
}

/// Create a new meal
#[instrument(skip_all)]
pub async fn create_meal(
    Extension(state): Extension<Arc<AppState>>,
    Json(req): Json<CreateMealRequest>,
) -> Result<(StatusCode, Json<ApiResponse<Meal>>), ApiError> {
    let meal_type = parse_meal_type(&req.meal_type)?;

    let mut meal = Meal::new(meal_type, req.description, req.food_ids);

    if let Some(date_str) = req.date {
        let date = parse_date(&date_str)?;
        meal = meal.with_date(date);
    }

    let id = state.repository.save_meal(&meal).await
        .map_err(ApiError::from)?;

    meal.id = id;

    Ok((StatusCode::CREATED, Json(ApiResponse::success(meal))))
}

/// Update a meal
#[instrument(skip_all)]
pub async fn update_meal(
    Extension(state): Extension<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(req): Json<CreateMealRequest>,
) -> Result<Json<ApiResponse<Meal>>, ApiError> {
    let existing = state.repository.get_meal(id).await
        .map_err(ApiError::from)?
        .ok_or_else(|| ApiError::not_found("Meal", id.to_string()))?;

    let meal_type = parse_meal_type(&req.meal_type)?;
    let mut meal = Meal::new(meal_type, req.description, req.food_ids);

    meal.id = existing.id;
    meal.created_at = existing.created_at;
    meal.user_id = existing.user_id;

    if let Some(date_str) = req.date {
        let date = parse_date(&date_str)?;
        meal = meal.with_date(date);
    }

    state.repository.save_meal(&meal).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(meal)))
}

/// Delete a meal
#[instrument(skip_all)]
pub async fn delete_meal(
    Extension(state): Extension<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, ApiError> {
    let deleted = state.repository.delete_meal(id).await
        .map_err(ApiError::from)?;

    if deleted {
        Ok(StatusCode::NO_CONTENT)
    } else {
        Err(ApiError::not_found("Meal", id.to_string()))
    }
}

// =============================================================================
// Summary Handlers
// =============================================================================

/// Get today's summary
#[instrument(skip_all)]
pub async fn today_summary(
    Extension(state): Extension<Arc<AppState>>,
) -> Result<Json<ApiResponse<crate::models::DailySummary>>, ApiError> {
    let today = chrono::Local::now().date_naive();
    let summary = state.repository.get_daily_summary(today).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(summary)))
}

/// Get summary for a specific date
#[instrument(skip_all)]
pub async fn daily_summary(
    Extension(state): Extension<Arc<AppState>>,
    Path(date_str): Path<String>,
) -> Result<Json<ApiResponse<crate::models::DailySummary>>, ApiError> {
    let date = parse_date(&date_str)?;
    let summary = state.repository.get_daily_summary(date).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(summary)))
}

#[derive(Deserialize)]
pub struct DateRangeQuery {
    start: String,
    end: String,
}

/// Get summaries for a date range
#[instrument(skip_all)]
pub async fn summary_range(
    Extension(state): Extension<Arc<AppState>>,
    Query(params): Query<DateRangeQuery>,
) -> Result<Json<ApiResponse<Vec<crate::models::DailySummary>>>, ApiError> {
    let start = parse_date(&params.start)?;
    let end = parse_date(&params.end)?;

    if end < start {
        return Err(ApiError::bad_request("End date must be after start date"));
    }

    // Limit range to 90 days
    let days = (end - start).num_days();
    if days > 90 {
        return Err(ApiError::bad_request("Date range cannot exceed 90 days"));
    }

    let summaries = state.repository.get_summaries_in_range(start, end).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(summaries)))
}

// =============================================================================
// Goal Handlers
// =============================================================================

/// Get current goals
#[instrument(skip_all)]
pub async fn get_goals(
    Extension(state): Extension<Arc<AppState>>,
) -> Result<Json<ApiResponse<Option<DailyGoal>>>, ApiError> {
    let goal = state.repository.get_current_goal().await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(goal)))
}

#[derive(Deserialize)]
pub struct SetGoalsRequest {
    calories: u32,
    protein: f32,
    carbs: f32,
    fat: f32,
    #[serde(default)]
    fiber: f32,
    #[serde(default)]
    water_ml: u32,
}

/// Set daily goals
#[instrument(skip_all)]
pub async fn set_goals(
    Extension(state): Extension<Arc<AppState>>,
    Json(req): Json<SetGoalsRequest>,
) -> Result<Json<ApiResponse<DailyGoal>>, ApiError> {
    let goal = DailyGoal {
        calories: req.calories,
        protein: req.protein,
        carbs: req.carbs,
        fat: req.fat,
        fiber: req.fiber,
        water_ml: req.water_ml,
    };

    state.repository.save_goal(&goal).await
        .map_err(ApiError::from)?;

    Ok(Json(ApiResponse::success(goal)))
}

// =============================================================================
// User Handlers
// =============================================================================

#[derive(Deserialize)]
pub struct RegisterRequest {
    username: String,
    email: String,
    password: String,
}

/// Register a new user
#[instrument(skip_all, fields(username = %req.username))]
pub async fn register_user(
    Extension(state): Extension<Arc<AppState>>,
    Json(req): Json<RegisterRequest>,
) -> Result<(StatusCode, Json<ApiResponse<UserResponse>>), ApiError> {
    // Validate inputs
    validate_username(&req.username).map_err(ApiError::from)?;
    validate_email(&req.email).map_err(ApiError::from)?;

    // Check if username already exists
    if state.repository.get_user_by_username(&req.username).await
        .map_err(ApiError::from)?
        .is_some()
    {
        return Err(ApiError::conflict("Username already taken"));
    }

    // Check if email already exists
    if state.repository.get_user_by_email(&req.email).await
        .map_err(ApiError::from)?
        .is_some()
    {
        return Err(ApiError::conflict("Email already registered"));
    }

    // Hash password
    let password_hash = hash_password(&req.password)
        .map_err(ApiError::from)?;

    // Create user
    let user = User::new(req.username, req.email, password_hash);
    let id = state.repository.save_user(&user).await
        .map_err(ApiError::from)?;

    debug!("Registered new user: {}", id);

    let response = UserResponse {
        id,
        username: user.username,
        email: user.email,
        display_name: user.display_name,
        email_verified: user.email_verified,
    };

    Ok((StatusCode::CREATED, Json(ApiResponse::success(response))))
}

#[derive(Deserialize)]
pub struct LoginRequest {
    username: String,
    password: String,
}

#[derive(Serialize)]
pub struct LoginResponse {
    user: UserResponse,
    token: String,
}

/// Login a user
#[instrument(skip_all, fields(username = %req.username))]
pub async fn login_user(
    Extension(state): Extension<Arc<AppState>>,
    Json(req): Json<LoginRequest>,
) -> Result<Json<ApiResponse<LoginResponse>>, ApiError> {
    // Find user
    let user = state.repository.get_user_by_username(&req.username).await
        .map_err(ApiError::from)?
        .ok_or_else(|| ApiError::unauthorized("Invalid credentials"))?;

    // Verify password
    let valid = verify_password(&req.password, &user.password_hash)
        .map_err(ApiError::from)?;

    if !valid {
        return Err(ApiError::unauthorized("Invalid credentials"));
    }

    // Check if account is active
    if !user.is_active {
        return Err(ApiError::forbidden("Account is disabled"));
    }

    // Record login
    state.repository.record_user_login(user.id).await
        .map_err(ApiError::from)?;

    // Generate token (in production, use JWT or similar)
    let token = crate::utils::generate_token(32);

    let response = LoginResponse {
        user: UserResponse {
            id: user.id,
            username: user.username,
            email: user.email,
            display_name: user.display_name,
            email_verified: user.email_verified,
        },
        token,
    };

    Ok(Json(ApiResponse::success(response)))
}

#[derive(Serialize)]
pub struct UserResponse {
    id: Uuid,
    username: String,
    email: String,
    display_name: Option<String>,
    email_verified: bool,
}

/// Get current user (requires auth - placeholder)
#[instrument(skip_all)]
pub async fn get_current_user(
    Extension(_state): Extension<Arc<AppState>>,
) -> Result<Json<ApiResponse<UserResponse>>, ApiError> {
    // In a real app, this would extract the user from the auth middleware
    Err(ApiError::unauthorized("Authentication required"))
}

// =============================================================================
// Helper Functions
// =============================================================================

fn parse_date(s: &str) -> Result<NaiveDate, ApiError> {
    if s == "today" {
        return Ok(chrono::Local::now().date_naive());
    }

    NaiveDate::parse_from_str(s, "%Y-%m-%d")
        .map_err(|_| ApiError::bad_request(format!(
            "Invalid date format: {}. Use YYYY-MM-DD or 'today'", s
        )))
}

fn parse_meal_type(s: &str) -> Result<MealType, ApiError> {
    match s.to_lowercase().as_str() {
        "breakfast" => Ok(MealType::Breakfast),
        "lunch" => Ok(MealType::Lunch),
        "dinner" => Ok(MealType::Dinner),
        "snack" => Ok(MealType::Snack),
        _ => Err(ApiError::bad_request(format!(
            "Invalid meal type: {}. Use breakfast, lunch, dinner, or snack", s
        ))),
    }
}
