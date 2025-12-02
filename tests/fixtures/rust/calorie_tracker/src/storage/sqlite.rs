//! SQLite implementation of the Repository trait.

use async_trait::async_trait;
use chrono::NaiveDate;
use sqlx::{sqlite::SqlitePoolOptions, Pool, Sqlite, Row};
use std::time::Instant;
use tracing::{debug, error, info, instrument};
use uuid::Uuid;

use crate::models::{Food, Meal, User, DailyGoal, DailySummary, NutritionInfo, Page};
use crate::{CalorieTrackerError, Result};

use super::{Repository, HealthCheck, PoolConfig};

/// SQLite-backed repository implementation
pub struct SqliteRepository {
    pool: Pool<Sqlite>,
    db_path: String,
}

impl SqliteRepository {
    /// Create a new SQLite repository
    #[instrument(skip_all)]
    pub async fn new(db_path: &str) -> Result<Self> {
        Self::with_config(db_path, PoolConfig::default()).await
    }

    /// Create with custom pool configuration
    pub async fn with_config(db_path: &str, config: PoolConfig) -> Result<Self> {
        let connection_string = if db_path == ":memory:" {
            "sqlite::memory:".to_string()
        } else {
            format!("sqlite:{}?mode=rwc", db_path)
        };

        info!("Connecting to SQLite database: {}", db_path);

        let pool = SqlitePoolOptions::new()
            .max_connections(config.max_connections)
            .min_connections(config.min_connections)
            .acquire_timeout(std::time::Duration::from_secs(config.connect_timeout_secs))
            .idle_timeout(std::time::Duration::from_secs(config.idle_timeout_secs))
            .connect(&connection_string)
            .await?;

        let repo = Self {
            pool,
            db_path: db_path.to_string(),
        };

        // Initialize schema
        repo.initialize().await?;

        Ok(repo)
    }

    /// Get a reference to the connection pool
    pub fn pool(&self) -> &Pool<Sqlite> {
        &self.pool
    }

    /// Execute raw SQL (for advanced queries)
    pub async fn execute_raw(&self, sql: &str) -> Result<u64> {
        let result = sqlx::query(sql)
            .execute(&self.pool)
            .await?;
        Ok(result.rows_affected())
    }
}

#[async_trait]
impl Repository for SqliteRepository {
    // =========================================================================
    // Food operations
    // =========================================================================

    #[instrument(skip(self, food))]
    async fn save_food(&self, food: &Food) -> Result<Uuid> {
        let id_str = food.id.to_string();
        let category = format!("{:?}", food.category);
        let created = food.created_at.to_rfc3339();
        let updated = food.updated_at.to_rfc3339();

        sqlx::query(
            r#"
            INSERT INTO foods (id, name, serving_size, calories, protein, carbs, fat,
                              fiber, sugar, sodium, category, brand, barcode, notes,
                              is_custom, created_at, updated_at)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                serving_size = excluded.serving_size,
                calories = excluded.calories,
                protein = excluded.protein,
                carbs = excluded.carbs,
                fat = excluded.fat,
                fiber = excluded.fiber,
                sugar = excluded.sugar,
                sodium = excluded.sodium,
                category = excluded.category,
                brand = excluded.brand,
                barcode = excluded.barcode,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            "#,
        )
        .bind(&id_str)
        .bind(&food.name)
        .bind(&food.serving_size)
        .bind(food.nutrition.calories as i64)
        .bind(food.nutrition.protein as f64)
        .bind(food.nutrition.carbs as f64)
        .bind(food.nutrition.fat as f64)
        .bind(food.nutrition.fiber as f64)
        .bind(food.nutrition.sugar as f64)
        .bind(food.nutrition.sodium as f64)
        .bind(&category)
        .bind(&food.brand)
        .bind(&food.barcode)
        .bind(&food.notes)
        .bind(food.is_custom)
        .bind(&created)
        .bind(&updated)
        .execute(&self.pool)
        .await?;

        debug!("Saved food: {} ({})", food.name, food.id);
        Ok(food.id)
    }

    #[instrument(skip(self))]
    async fn get_food(&self, id: Uuid) -> Result<Option<Food>> {
        let id_str = id.to_string();

        let row = sqlx::query(
            r#"
            SELECT id, name, serving_size, calories, protein, carbs, fat,
                   fiber, sugar, sodium, category, brand, barcode, notes,
                   is_custom, created_at, updated_at
            FROM foods WHERE id = ?1
            "#,
        )
        .bind(&id_str)
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(row) => Ok(Some(row_to_food(&row)?)),
            None => Ok(None),
        }
    }

    async fn get_foods(&self, ids: &[Uuid]) -> Result<Vec<Food>> {
        if ids.is_empty() {
            return Ok(Vec::new());
        }

        // Build placeholders for IN clause
        let placeholders: Vec<String> = ids.iter().map(|_| "?".to_string()).collect();
        let sql = format!(
            r#"
            SELECT id, name, serving_size, calories, protein, carbs, fat,
                   fiber, sugar, sodium, category, brand, barcode, notes,
                   is_custom, created_at, updated_at
            FROM foods WHERE id IN ({})
            "#,
            placeholders.join(", ")
        );

        let mut query = sqlx::query(&sql);
        for id in ids {
            query = query.bind(id.to_string());
        }

        let rows = query.fetch_all(&self.pool).await?;
        rows.into_iter().map(|row| row_to_food(&row)).collect()
    }

    #[instrument(skip(self))]
    async fn search_foods(&self, query: Option<&str>, limit: usize) -> Result<Vec<Food>> {
        let rows = match query {
            Some(q) => {
                let pattern = format!("%{}%", q);
                sqlx::query(
                    r#"
                    SELECT id, name, serving_size, calories, protein, carbs, fat,
                           fiber, sugar, sodium, category, brand, barcode, notes,
                           is_custom, created_at, updated_at
                    FROM foods
                    WHERE name LIKE ?1 OR brand LIKE ?1
                    ORDER BY name
                    LIMIT ?2
                    "#,
                )
                .bind(&pattern)
                .bind(limit as i64)
                .fetch_all(&self.pool)
                .await?
            }
            None => {
                sqlx::query(
                    r#"
                    SELECT id, name, serving_size, calories, protein, carbs, fat,
                           fiber, sugar, sodium, category, brand, barcode, notes,
                           is_custom, created_at, updated_at
                    FROM foods
                    ORDER BY name
                    LIMIT ?1
                    "#,
                )
                .bind(limit as i64)
                .fetch_all(&self.pool)
                .await?
            }
        };

        rows.into_iter().map(|row| row_to_food(&row)).collect()
    }

    async fn list_foods(&self, page: usize, page_size: usize) -> Result<Page<Food>> {
        let offset = page * page_size;

        // Get total count
        let count_row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM foods")
            .fetch_one(&self.pool)
            .await?;
        let total = count_row.0 as usize;

        // Get page of items
        let rows = sqlx::query(
            r#"
            SELECT id, name, serving_size, calories, protein, carbs, fat,
                   fiber, sugar, sodium, category, brand, barcode, notes,
                   is_custom, created_at, updated_at
            FROM foods
            ORDER BY name
            LIMIT ?1 OFFSET ?2
            "#,
        )
        .bind(page_size as i64)
        .bind(offset as i64)
        .fetch_all(&self.pool)
        .await?;

        let items: Result<Vec<Food>> = rows.into_iter().map(|row| row_to_food(&row)).collect();

        Ok(Page::new(items?, total, page, page_size))
    }

    async fn delete_food(&self, id: Uuid) -> Result<bool> {
        let result = sqlx::query("DELETE FROM foods WHERE id = ?1")
            .bind(id.to_string())
            .execute(&self.pool)
            .await?;

        Ok(result.rows_affected() > 0)
    }

    async fn get_food_by_barcode(&self, barcode: &str) -> Result<Option<Food>> {
        let row = sqlx::query(
            r#"
            SELECT id, name, serving_size, calories, protein, carbs, fat,
                   fiber, sugar, sodium, category, brand, barcode, notes,
                   is_custom, created_at, updated_at
            FROM foods WHERE barcode = ?1
            "#,
        )
        .bind(barcode)
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(row) => Ok(Some(row_to_food(&row)?)),
            None => Ok(None),
        }
    }

    // =========================================================================
    // Meal operations
    // =========================================================================

    async fn save_meal(&self, meal: &Meal) -> Result<Uuid> {
        let id_str = meal.id.to_string();
        let meal_type = format!("{:?}", meal.meal_type);
        let date = meal.date.to_string();
        let user_id = meal.user_id.map(|u| u.to_string());
        let entries_json = serde_json::to_string(&meal.entries)?;
        let nutrition_json = meal.total_nutrition.map(|n| serde_json::to_string(&n).ok()).flatten();
        let created = meal.created_at.to_rfc3339();
        let updated = meal.updated_at.to_rfc3339();

        sqlx::query(
            r#"
            INSERT INTO meals (id, meal_type, date, description, entries, total_nutrition,
                              user_id, created_at, updated_at)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
            ON CONFLICT(id) DO UPDATE SET
                meal_type = excluded.meal_type,
                description = excluded.description,
                entries = excluded.entries,
                total_nutrition = excluded.total_nutrition,
                updated_at = excluded.updated_at
            "#,
        )
        .bind(&id_str)
        .bind(&meal_type)
        .bind(&date)
        .bind(&meal.description)
        .bind(&entries_json)
        .bind(&nutrition_json)
        .bind(&user_id)
        .bind(&created)
        .bind(&updated)
        .execute(&self.pool)
        .await?;

        Ok(meal.id)
    }

    async fn get_meal(&self, id: Uuid) -> Result<Option<Meal>> {
        let row = sqlx::query(
            r#"
            SELECT id, meal_type, date, description, entries, total_nutrition,
                   user_id, created_at, updated_at
            FROM meals WHERE id = ?1
            "#,
        )
        .bind(id.to_string())
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(row) => Ok(Some(row_to_meal(&row)?)),
            None => Ok(None),
        }
    }

    async fn get_meals_for_date(&self, date: NaiveDate) -> Result<Vec<Meal>> {
        let rows = sqlx::query(
            r#"
            SELECT id, meal_type, date, description, entries, total_nutrition,
                   user_id, created_at, updated_at
            FROM meals WHERE date = ?1
            ORDER BY created_at
            "#,
        )
        .bind(date.to_string())
        .fetch_all(&self.pool)
        .await?;

        rows.into_iter().map(|row| row_to_meal(&row)).collect()
    }

    async fn get_meals_in_range(&self, start: NaiveDate, end: NaiveDate) -> Result<Vec<Meal>> {
        let rows = sqlx::query(
            r#"
            SELECT id, meal_type, date, description, entries, total_nutrition,
                   user_id, created_at, updated_at
            FROM meals WHERE date >= ?1 AND date <= ?2
            ORDER BY date, created_at
            "#,
        )
        .bind(start.to_string())
        .bind(end.to_string())
        .fetch_all(&self.pool)
        .await?;

        rows.into_iter().map(|row| row_to_meal(&row)).collect()
    }

    async fn delete_meal(&self, id: Uuid) -> Result<bool> {
        let result = sqlx::query("DELETE FROM meals WHERE id = ?1")
            .bind(id.to_string())
            .execute(&self.pool)
            .await?;

        Ok(result.rows_affected() > 0)
    }

    async fn get_recent_meals(&self, limit: usize) -> Result<Vec<Meal>> {
        let rows = sqlx::query(
            r#"
            SELECT id, meal_type, date, description, entries, total_nutrition,
                   user_id, created_at, updated_at
            FROM meals
            ORDER BY created_at DESC
            LIMIT ?1
            "#,
        )
        .bind(limit as i64)
        .fetch_all(&self.pool)
        .await?;

        rows.into_iter().map(|row| row_to_meal(&row)).collect()
    }

    // =========================================================================
    // User operations
    // =========================================================================

    async fn save_user(&self, user: &User) -> Result<Uuid> {
        let id_str = user.id.to_string();
        let prefs_json = serde_json::to_string(&user.preferences)?;
        let last_login = user.last_login.map(|t| t.to_rfc3339());
        let created = user.created_at.to_rfc3339();
        let updated = user.updated_at.to_rfc3339();

        sqlx::query(
            r#"
            INSERT INTO users (id, username, email, password_hash, display_name,
                              preferences, email_verified, is_active, last_login,
                              created_at, updated_at)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)
            ON CONFLICT(id) DO UPDATE SET
                email = excluded.email,
                display_name = excluded.display_name,
                preferences = excluded.preferences,
                email_verified = excluded.email_verified,
                is_active = excluded.is_active,
                last_login = excluded.last_login,
                updated_at = excluded.updated_at
            "#,
        )
        .bind(&id_str)
        .bind(&user.username)
        .bind(&user.email)
        .bind(&user.password_hash)
        .bind(&user.display_name)
        .bind(&prefs_json)
        .bind(user.email_verified)
        .bind(user.is_active)
        .bind(&last_login)
        .bind(&created)
        .bind(&updated)
        .execute(&self.pool)
        .await?;

        Ok(user.id)
    }

    async fn get_user(&self, id: Uuid) -> Result<Option<User>> {
        let row = sqlx::query(
            r#"
            SELECT id, username, email, password_hash, display_name, preferences,
                   email_verified, is_active, last_login, created_at, updated_at
            FROM users WHERE id = ?1
            "#,
        )
        .bind(id.to_string())
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(row) => Ok(Some(row_to_user(&row)?)),
            None => Ok(None),
        }
    }

    async fn get_user_by_username(&self, username: &str) -> Result<Option<User>> {
        let row = sqlx::query(
            r#"
            SELECT id, username, email, password_hash, display_name, preferences,
                   email_verified, is_active, last_login, created_at, updated_at
            FROM users WHERE username = ?1
            "#,
        )
        .bind(username)
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(row) => Ok(Some(row_to_user(&row)?)),
            None => Ok(None),
        }
    }

    async fn get_user_by_email(&self, email: &str) -> Result<Option<User>> {
        let row = sqlx::query(
            r#"
            SELECT id, username, email, password_hash, display_name, preferences,
                   email_verified, is_active, last_login, created_at, updated_at
            FROM users WHERE email = ?1
            "#,
        )
        .bind(email)
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(row) => Ok(Some(row_to_user(&row)?)),
            None => Ok(None),
        }
    }

    async fn delete_user(&self, id: Uuid) -> Result<bool> {
        let result = sqlx::query("DELETE FROM users WHERE id = ?1")
            .bind(id.to_string())
            .execute(&self.pool)
            .await?;

        Ok(result.rows_affected() > 0)
    }

    async fn record_user_login(&self, id: Uuid) -> Result<()> {
        let now = chrono::Utc::now().to_rfc3339();
        sqlx::query("UPDATE users SET last_login = ?1, updated_at = ?1 WHERE id = ?2")
            .bind(&now)
            .bind(id.to_string())
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    // =========================================================================
    // Goal operations
    // =========================================================================

    async fn save_goal(&self, goal: &DailyGoal) -> Result<()> {
        // Store as single row with fixed ID (user settings pattern)
        sqlx::query(
            r#"
            INSERT INTO goals (id, calories, protein, carbs, fat, fiber, water_ml)
            VALUES ('default', ?1, ?2, ?3, ?4, ?5, ?6)
            ON CONFLICT(id) DO UPDATE SET
                calories = excluded.calories,
                protein = excluded.protein,
                carbs = excluded.carbs,
                fat = excluded.fat,
                fiber = excluded.fiber,
                water_ml = excluded.water_ml
            "#,
        )
        .bind(goal.calories as i64)
        .bind(goal.protein as f64)
        .bind(goal.carbs as f64)
        .bind(goal.fat as f64)
        .bind(goal.fiber as f64)
        .bind(goal.water_ml as i64)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    async fn get_current_goal(&self) -> Result<Option<DailyGoal>> {
        let row = sqlx::query(
            "SELECT calories, protein, carbs, fat, fiber, water_ml FROM goals WHERE id = 'default'",
        )
        .fetch_optional(&self.pool)
        .await?;

        match row {
            Some(row) => Ok(Some(DailyGoal {
                calories: row.get::<i64, _>("calories") as u32,
                protein: row.get::<f64, _>("protein") as f32,
                carbs: row.get::<f64, _>("carbs") as f32,
                fat: row.get::<f64, _>("fat") as f32,
                fiber: row.get::<f64, _>("fiber") as f32,
                water_ml: row.get::<i64, _>("water_ml") as u32,
            })),
            None => Ok(None),
        }
    }

    // =========================================================================
    // Summary operations
    // =========================================================================

    async fn get_daily_summary(&self, date: NaiveDate) -> Result<DailySummary> {
        let meals = self.get_meals_for_date(date).await?;
        let goal = self.get_current_goal().await?;
        Ok(DailySummary::from_meals(date, meals, goal))
    }

    async fn get_summaries_in_range(
        &self,
        start: NaiveDate,
        end: NaiveDate,
    ) -> Result<Vec<DailySummary>> {
        let mut summaries = Vec::new();
        let mut current = start;
        while current <= end {
            summaries.push(self.get_daily_summary(current).await?);
            current += chrono::Duration::days(1);
        }
        Ok(summaries)
    }

    // =========================================================================
    // Database management
    // =========================================================================

    async fn initialize(&self) -> Result<()> {
        info!("Initializing database schema...");

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS foods (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                serving_size TEXT NOT NULL,
                calories INTEGER NOT NULL,
                protein REAL NOT NULL,
                carbs REAL NOT NULL,
                fat REAL NOT NULL,
                fiber REAL DEFAULT 0,
                sugar REAL DEFAULT 0,
                sodium REAL DEFAULT 0,
                category TEXT,
                brand TEXT,
                barcode TEXT,
                notes TEXT,
                is_custom INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_foods_name ON foods(name);
            CREATE INDEX IF NOT EXISTS idx_foods_barcode ON foods(barcode);

            CREATE TABLE IF NOT EXISTS meals (
                id TEXT PRIMARY KEY,
                meal_type TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                entries TEXT NOT NULL,
                total_nutrition TEXT,
                user_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(date);
            CREATE INDEX IF NOT EXISTS idx_meals_user ON meals(user_id);

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                preferences TEXT,
                email_verified INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                last_login TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                calories INTEGER NOT NULL,
                protein REAL NOT NULL,
                carbs REAL NOT NULL,
                fat REAL NOT NULL,
                fiber REAL DEFAULT 0,
                water_ml INTEGER DEFAULT 0
            );
            "#,
        )
        .execute(&self.pool)
        .await?;

        info!("Database schema initialized successfully");
        Ok(())
    }

    async fn migrate(&self) -> Result<()> {
        // For now, just ensure schema is up to date
        self.initialize().await
    }

    async fn health_check(&self) -> HealthCheck {
        let start = Instant::now();

        match sqlx::query("SELECT 1").fetch_one(&self.pool).await {
            Ok(_) => {
                let latency = start.elapsed().as_millis() as u64;
                let mut check = HealthCheck::healthy(latency);
                check.pool_size = self.pool.size();
                check.idle_connections = self.pool.num_idle() as u32;
                check
            }
            Err(e) => {
                error!("Health check failed: {}", e);
                HealthCheck::unhealthy(e.to_string())
            }
        }
    }

    async fn close(&self) -> Result<()> {
        self.pool.close().await;
        Ok(())
    }
}

// Helper functions to convert rows to models

fn row_to_food(row: &sqlx::sqlite::SqliteRow) -> Result<Food> {
    use crate::models::FoodCategory;

    let id_str: String = row.get("id");
    let id = Uuid::parse_str(&id_str)
        .map_err(|_| CalorieTrackerError::InvalidInput(format!("Invalid UUID: {}", id_str)))?;

    let category_str: Option<String> = row.get("category");
    let category = category_str
        .and_then(|s| match s.to_lowercase().as_str() {
            "protein" => Some(FoodCategory::Protein),
            "carbohydrate" => Some(FoodCategory::Carbohydrate),
            "vegetable" => Some(FoodCategory::Vegetable),
            "fruit" => Some(FoodCategory::Fruit),
            "dairy" => Some(FoodCategory::Dairy),
            "fat" => Some(FoodCategory::Fat),
            "beverage" => Some(FoodCategory::Beverage),
            "snack" => Some(FoodCategory::Snack),
            "condiment" => Some(FoodCategory::Condiment),
            _ => None,
        })
        .unwrap_or(FoodCategory::Other);

    let created_str: String = row.get("created_at");
    let updated_str: String = row.get("updated_at");

    Ok(Food {
        id,
        name: row.get("name"),
        serving_size: row.get("serving_size"),
        nutrition: NutritionInfo {
            calories: row.get::<i64, _>("calories") as u32,
            protein: row.get::<f64, _>("protein") as f32,
            carbs: row.get::<f64, _>("carbs") as f32,
            fat: row.get::<f64, _>("fat") as f32,
            fiber: row.get::<f64, _>("fiber") as f32,
            sugar: row.get::<f64, _>("sugar") as f32,
            sodium: row.get::<f64, _>("sodium") as f32,
        },
        category,
        brand: row.get("brand"),
        barcode: row.get("barcode"),
        notes: row.get("notes"),
        is_custom: row.get::<i64, _>("is_custom") != 0,
        created_at: chrono::DateTime::parse_from_rfc3339(&created_str)
            .map_err(|_| CalorieTrackerError::InvalidInput("Invalid date".into()))?
            .with_timezone(&chrono::Utc),
        updated_at: chrono::DateTime::parse_from_rfc3339(&updated_str)
            .map_err(|_| CalorieTrackerError::InvalidInput("Invalid date".into()))?
            .with_timezone(&chrono::Utc),
    })
}

fn row_to_meal(row: &sqlx::sqlite::SqliteRow) -> Result<Meal> {
    use crate::models::{MealEntry, MealType};

    let id_str: String = row.get("id");
    let id = Uuid::parse_str(&id_str)
        .map_err(|_| CalorieTrackerError::InvalidInput(format!("Invalid UUID: {}", id_str)))?;

    let meal_type_str: String = row.get("meal_type");
    let meal_type = match meal_type_str.to_lowercase().as_str() {
        "breakfast" => MealType::Breakfast,
        "lunch" => MealType::Lunch,
        "dinner" => MealType::Dinner,
        "snack" => MealType::Snack,
        _ => MealType::Snack,
    };

    let date_str: String = row.get("date");
    let date = NaiveDate::parse_from_str(&date_str, "%Y-%m-%d")
        .map_err(|_| CalorieTrackerError::InvalidInput("Invalid date".into()))?;

    let entries_json: String = row.get("entries");
    let entries: Vec<MealEntry> = serde_json::from_str(&entries_json)?;

    let nutrition_json: Option<String> = row.get("total_nutrition");
    let total_nutrition: Option<NutritionInfo> = nutrition_json
        .map(|s| serde_json::from_str(&s).ok())
        .flatten();

    let user_id_str: Option<String> = row.get("user_id");
    let user_id = user_id_str.and_then(|s| Uuid::parse_str(&s).ok());

    let created_str: String = row.get("created_at");
    let updated_str: String = row.get("updated_at");

    Ok(Meal {
        id,
        meal_type,
        date,
        description: row.get("description"),
        entries,
        total_nutrition,
        user_id,
        created_at: chrono::DateTime::parse_from_rfc3339(&created_str)
            .map_err(|_| CalorieTrackerError::InvalidInput("Invalid date".into()))?
            .with_timezone(&chrono::Utc),
        updated_at: chrono::DateTime::parse_from_rfc3339(&updated_str)
            .map_err(|_| CalorieTrackerError::InvalidInput("Invalid date".into()))?
            .with_timezone(&chrono::Utc),
    })
}

fn row_to_user(row: &sqlx::sqlite::SqliteRow) -> Result<User> {
    use crate::models::UserPreferences;

    let id_str: String = row.get("id");
    let id = Uuid::parse_str(&id_str)
        .map_err(|_| CalorieTrackerError::InvalidInput(format!("Invalid UUID: {}", id_str)))?;

    let prefs_json: Option<String> = row.get("preferences");
    let preferences: UserPreferences = prefs_json
        .map(|s| serde_json::from_str(&s).ok())
        .flatten()
        .unwrap_or_default();

    let last_login_str: Option<String> = row.get("last_login");
    let last_login = last_login_str
        .and_then(|s| chrono::DateTime::parse_from_rfc3339(&s).ok())
        .map(|t| t.with_timezone(&chrono::Utc));

    let created_str: String = row.get("created_at");
    let updated_str: String = row.get("updated_at");

    Ok(User {
        id,
        username: row.get("username"),
        email: row.get("email"),
        password_hash: row.get("password_hash"),
        display_name: row.get("display_name"),
        preferences,
        email_verified: row.get::<i64, _>("email_verified") != 0,
        is_active: row.get::<i64, _>("is_active") != 0,
        last_login,
        created_at: chrono::DateTime::parse_from_rfc3339(&created_str)
            .map_err(|_| CalorieTrackerError::InvalidInput("Invalid date".into()))?
            .with_timezone(&chrono::Utc),
        updated_at: chrono::DateTime::parse_from_rfc3339(&updated_str)
            .map_err(|_| CalorieTrackerError::InvalidInput("Invalid date".into()))?
            .with_timezone(&chrono::Utc),
    })
}
