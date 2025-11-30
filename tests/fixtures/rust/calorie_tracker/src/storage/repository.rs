//! Repository trait defining the storage interface.

use async_trait::async_trait;
use chrono::NaiveDate;
use uuid::Uuid;

use crate::models::{Food, Meal, User, DailyGoal, DailySummary, Page};
use crate::Result;

use super::HealthCheck;

/// Main repository trait for data access.
///
/// This trait defines the interface for all data operations. Implementations
/// can use different backends (SQLite, PostgreSQL, in-memory, etc).
#[async_trait]
pub trait Repository: Send + Sync {
    // =========================================================================
    // Food operations
    // =========================================================================

    /// Save a food item (insert or update)
    async fn save_food(&self, food: &Food) -> Result<Uuid>;

    /// Get a food by ID
    async fn get_food(&self, id: Uuid) -> Result<Option<Food>>;

    /// Get multiple foods by IDs
    async fn get_foods(&self, ids: &[Uuid]) -> Result<Vec<Food>>;

    /// Search foods by name
    async fn search_foods(&self, query: Option<&str>, limit: usize) -> Result<Vec<Food>>;

    /// Get foods with pagination
    async fn list_foods(&self, page: usize, page_size: usize) -> Result<Page<Food>>;

    /// Delete a food by ID
    async fn delete_food(&self, id: Uuid) -> Result<bool>;

    /// Get food by barcode
    async fn get_food_by_barcode(&self, barcode: &str) -> Result<Option<Food>>;

    // =========================================================================
    // Meal operations
    // =========================================================================

    /// Save a meal (insert or update)
    async fn save_meal(&self, meal: &Meal) -> Result<Uuid>;

    /// Get a meal by ID
    async fn get_meal(&self, id: Uuid) -> Result<Option<Meal>>;

    /// Get meals for a specific date
    async fn get_meals_for_date(&self, date: NaiveDate) -> Result<Vec<Meal>>;

    /// Get meals for a date range
    async fn get_meals_in_range(
        &self,
        start: NaiveDate,
        end: NaiveDate,
    ) -> Result<Vec<Meal>>;

    /// Delete a meal by ID
    async fn delete_meal(&self, id: Uuid) -> Result<bool>;

    /// Get recent meals (for quick logging)
    async fn get_recent_meals(&self, limit: usize) -> Result<Vec<Meal>>;

    // =========================================================================
    // User operations
    // =========================================================================

    /// Save a user (insert or update)
    async fn save_user(&self, user: &User) -> Result<Uuid>;

    /// Get a user by ID
    async fn get_user(&self, id: Uuid) -> Result<Option<User>>;

    /// Get a user by username
    async fn get_user_by_username(&self, username: &str) -> Result<Option<User>>;

    /// Get a user by email
    async fn get_user_by_email(&self, email: &str) -> Result<Option<User>>;

    /// Delete a user by ID
    async fn delete_user(&self, id: Uuid) -> Result<bool>;

    /// Update user's last login time
    async fn record_user_login(&self, id: Uuid) -> Result<()>;

    // =========================================================================
    // Goal operations
    // =========================================================================

    /// Save daily goals
    async fn save_goal(&self, goal: &DailyGoal) -> Result<()>;

    /// Get current daily goal
    async fn get_current_goal(&self) -> Result<Option<DailyGoal>>;

    // =========================================================================
    // Summary operations
    // =========================================================================

    /// Get daily summary for a date
    async fn get_daily_summary(&self, date: NaiveDate) -> Result<DailySummary>;

    /// Get summaries for a date range
    async fn get_summaries_in_range(
        &self,
        start: NaiveDate,
        end: NaiveDate,
    ) -> Result<Vec<DailySummary>>;

    // =========================================================================
    // Database management
    // =========================================================================

    /// Initialize database schema
    async fn initialize(&self) -> Result<()>;

    /// Run database migrations
    async fn migrate(&self) -> Result<()>;

    /// Check database health
    async fn health_check(&self) -> HealthCheck;

    /// Close database connections
    async fn close(&self) -> Result<()>;
}

/// Extension trait for repository with utility methods
#[async_trait]
pub trait RepositoryExt: Repository {
    /// Get or create a food by name
    async fn get_or_create_food(&self, food: Food) -> Result<Food> {
        // Search for existing food with same name
        let existing = self.search_foods(Some(&food.name), 1).await?;

        if let Some(found) = existing.into_iter().next() {
            Ok(found)
        } else {
            let id = self.save_food(&food).await?;
            Ok(Food { id, ..food })
        }
    }

    /// Log a quick meal
    async fn quick_log(&self, meal: Meal) -> Result<Uuid> {
        self.save_meal(&meal).await
    }

    /// Get today's summary
    async fn get_today_summary(&self) -> Result<DailySummary> {
        let today = chrono::Local::now().date_naive();
        self.get_daily_summary(today).await
    }

    /// Get this week's summaries
    async fn get_week_summaries(&self) -> Result<Vec<DailySummary>> {
        let today = chrono::Local::now().date_naive();
        let week_ago = today - chrono::Duration::days(7);
        self.get_summaries_in_range(week_ago, today).await
    }
}

// Blanket implementation for all Repository implementations
impl<T: Repository> RepositoryExt for T {}

/// Mock repository for testing
#[cfg(test)]
pub mod mock {
    use super::*;
    use std::collections::HashMap;
    use std::sync::RwLock;

    pub struct MockRepository {
        foods: RwLock<HashMap<Uuid, Food>>,
        meals: RwLock<HashMap<Uuid, Meal>>,
        users: RwLock<HashMap<Uuid, User>>,
        goal: RwLock<Option<DailyGoal>>,
    }

    impl MockRepository {
        pub fn new() -> Self {
            Self {
                foods: RwLock::new(HashMap::new()),
                meals: RwLock::new(HashMap::new()),
                users: RwLock::new(HashMap::new()),
                goal: RwLock::new(None),
            }
        }
    }

    #[async_trait]
    impl Repository for MockRepository {
        async fn save_food(&self, food: &Food) -> Result<Uuid> {
            let mut foods = self.foods.write().unwrap();
            foods.insert(food.id, food.clone());
            Ok(food.id)
        }

        async fn get_food(&self, id: Uuid) -> Result<Option<Food>> {
            let foods = self.foods.read().unwrap();
            Ok(foods.get(&id).cloned())
        }

        async fn get_foods(&self, ids: &[Uuid]) -> Result<Vec<Food>> {
            let foods = self.foods.read().unwrap();
            Ok(ids.iter().filter_map(|id| foods.get(id).cloned()).collect())
        }

        async fn search_foods(&self, query: Option<&str>, limit: usize) -> Result<Vec<Food>> {
            let foods = self.foods.read().unwrap();
            let results: Vec<Food> = foods
                .values()
                .filter(|f| {
                    query.map_or(true, |q| {
                        f.name.to_lowercase().contains(&q.to_lowercase())
                    })
                })
                .take(limit)
                .cloned()
                .collect();
            Ok(results)
        }

        async fn list_foods(&self, page: usize, page_size: usize) -> Result<Page<Food>> {
            let foods = self.foods.read().unwrap();
            let all: Vec<Food> = foods.values().cloned().collect();
            let total = all.len();
            let items: Vec<Food> = all
                .into_iter()
                .skip(page * page_size)
                .take(page_size)
                .collect();
            Ok(Page::new(items, total, page, page_size))
        }

        async fn delete_food(&self, id: Uuid) -> Result<bool> {
            let mut foods = self.foods.write().unwrap();
            Ok(foods.remove(&id).is_some())
        }

        async fn get_food_by_barcode(&self, barcode: &str) -> Result<Option<Food>> {
            let foods = self.foods.read().unwrap();
            Ok(foods
                .values()
                .find(|f| f.barcode.as_deref() == Some(barcode))
                .cloned())
        }

        async fn save_meal(&self, meal: &Meal) -> Result<Uuid> {
            let mut meals = self.meals.write().unwrap();
            meals.insert(meal.id, meal.clone());
            Ok(meal.id)
        }

        async fn get_meal(&self, id: Uuid) -> Result<Option<Meal>> {
            let meals = self.meals.read().unwrap();
            Ok(meals.get(&id).cloned())
        }

        async fn get_meals_for_date(&self, date: NaiveDate) -> Result<Vec<Meal>> {
            let meals = self.meals.read().unwrap();
            Ok(meals.values().filter(|m| m.date == date).cloned().collect())
        }

        async fn get_meals_in_range(&self, start: NaiveDate, end: NaiveDate) -> Result<Vec<Meal>> {
            let meals = self.meals.read().unwrap();
            Ok(meals
                .values()
                .filter(|m| m.date >= start && m.date <= end)
                .cloned()
                .collect())
        }

        async fn delete_meal(&self, id: Uuid) -> Result<bool> {
            let mut meals = self.meals.write().unwrap();
            Ok(meals.remove(&id).is_some())
        }

        async fn get_recent_meals(&self, limit: usize) -> Result<Vec<Meal>> {
            let meals = self.meals.read().unwrap();
            let mut all: Vec<Meal> = meals.values().cloned().collect();
            all.sort_by(|a, b| b.created_at.cmp(&a.created_at));
            Ok(all.into_iter().take(limit).collect())
        }

        async fn save_user(&self, user: &User) -> Result<Uuid> {
            let mut users = self.users.write().unwrap();
            users.insert(user.id, user.clone());
            Ok(user.id)
        }

        async fn get_user(&self, id: Uuid) -> Result<Option<User>> {
            let users = self.users.read().unwrap();
            Ok(users.get(&id).cloned())
        }

        async fn get_user_by_username(&self, username: &str) -> Result<Option<User>> {
            let users = self.users.read().unwrap();
            Ok(users.values().find(|u| u.username == username).cloned())
        }

        async fn get_user_by_email(&self, email: &str) -> Result<Option<User>> {
            let users = self.users.read().unwrap();
            Ok(users.values().find(|u| u.email == email).cloned())
        }

        async fn delete_user(&self, id: Uuid) -> Result<bool> {
            let mut users = self.users.write().unwrap();
            Ok(users.remove(&id).is_some())
        }

        async fn record_user_login(&self, id: Uuid) -> Result<()> {
            let mut users = self.users.write().unwrap();
            if let Some(user) = users.get_mut(&id) {
                user.record_login();
            }
            Ok(())
        }

        async fn save_goal(&self, goal: &DailyGoal) -> Result<()> {
            let mut g = self.goal.write().unwrap();
            *g = Some(*goal);
            Ok(())
        }

        async fn get_current_goal(&self) -> Result<Option<DailyGoal>> {
            let g = self.goal.read().unwrap();
            Ok(*g)
        }

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

        async fn initialize(&self) -> Result<()> {
            Ok(())
        }

        async fn migrate(&self) -> Result<()> {
            Ok(())
        }

        async fn health_check(&self) -> HealthCheck {
            HealthCheck::healthy(0)
        }

        async fn close(&self) -> Result<()> {
            Ok(())
        }
    }
}
