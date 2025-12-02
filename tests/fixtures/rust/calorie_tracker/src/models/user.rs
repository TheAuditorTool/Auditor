//! User profile and daily goals.

use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, NaiveDate, Utc};

use super::{Meal, NutritionInfo, Identifiable, Timestamped};

/// User preferences for the application
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserPreferences {
    /// Preferred measurement unit (metric/imperial)
    pub unit_system: UnitSystem,
    /// Default reminder times for meal logging
    pub reminder_times: Vec<String>,
    /// Theme preference
    pub theme: Theme,
    /// Whether to show nutritional details by default
    pub show_details: bool,
}

impl Default for UserPreferences {
    fn default() -> Self {
        Self {
            unit_system: UnitSystem::Metric,
            reminder_times: vec!["08:00".into(), "12:00".into(), "18:00".into()],
            theme: Theme::System,
            show_details: true,
        }
    }
}

/// Measurement unit system
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum UnitSystem {
    Metric,
    Imperial,
}

/// UI theme preference
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Theme {
    Light,
    Dark,
    System,
}

/// User profile with account information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    /// Unique identifier
    pub id: Uuid,
    /// Username (unique)
    pub username: String,
    /// Email address
    pub email: String,
    /// Password hash (argon2)
    #[serde(skip_serializing)]
    pub password_hash: String,
    /// Display name
    pub display_name: Option<String>,
    /// User preferences
    #[serde(default)]
    pub preferences: UserPreferences,
    /// Whether email is verified
    pub email_verified: bool,
    /// Whether account is active
    pub is_active: bool,
    /// Last login timestamp
    pub last_login: Option<DateTime<Utc>>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last update timestamp
    pub updated_at: DateTime<Utc>,
}

impl User {
    /// Create a new user with minimal info
    pub fn new(username: String, email: String, password_hash: String) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            username,
            email,
            password_hash,
            display_name: None,
            preferences: UserPreferences::default(),
            email_verified: false,
            is_active: true,
            last_login: None,
            created_at: now,
            updated_at: now,
        }
    }

    /// Get display name or fallback to username
    pub fn name(&self) -> &str {
        self.display_name.as_deref().unwrap_or(&self.username)
    }

    /// Update last login time to now
    pub fn record_login(&mut self) {
        self.last_login = Some(Utc::now());
        self.updated_at = Utc::now();
    }

    /// Set display name
    pub fn with_display_name(mut self, name: impl Into<String>) -> Self {
        self.display_name = Some(name.into());
        self
    }
}

impl Identifiable for User {
    fn id(&self) -> Uuid {
        self.id
    }
}

impl Timestamped for User {
    fn created_at(&self) -> DateTime<Utc> {
        self.created_at
    }

    fn updated_at(&self) -> DateTime<Utc> {
        self.updated_at
    }
}

/// Daily nutritional goals
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct DailyGoal {
    /// Target calories
    pub calories: u32,
    /// Target protein in grams
    pub protein: f32,
    /// Target carbs in grams
    pub carbs: f32,
    /// Target fat in grams
    pub fat: f32,
    /// Target fiber in grams
    #[serde(default)]
    pub fiber: f32,
    /// Target water intake in ml
    #[serde(default)]
    pub water_ml: u32,
}

impl Default for DailyGoal {
    fn default() -> Self {
        // Reasonable defaults for average adult
        Self {
            calories: 2000,
            protein: 50.0,
            carbs: 250.0,
            fat: 65.0,
            fiber: 25.0,
            water_ml: 2500,
        }
    }
}

impl DailyGoal {
    /// Create goals for weight loss (calorie deficit)
    pub fn weight_loss(maintenance_calories: u32) -> Self {
        let deficit = 500; // ~1 lb per week
        let calories = maintenance_calories.saturating_sub(deficit);

        Self {
            calories,
            protein: 0.8 * (calories as f32 / 4.0) * 0.3, // 30% from protein
            carbs: (calories as f32 / 4.0) * 0.4,          // 40% from carbs
            fat: (calories as f32 / 9.0) * 0.3,            // 30% from fat
            fiber: 30.0,
            water_ml: 3000,
        }
    }

    /// Create goals for muscle building
    pub fn muscle_building(body_weight_kg: f32) -> Self {
        let protein = body_weight_kg * 2.0; // 2g per kg
        let calories = (body_weight_kg * 35.0) as u32; // Higher calorie intake

        Self {
            calories,
            protein,
            carbs: (calories as f32 * 0.5) / 4.0,
            fat: (calories as f32 * 0.25) / 9.0,
            fiber: 35.0,
            water_ml: 4000,
        }
    }

    /// Calculate percentage of goal achieved
    pub fn calculate_progress(&self, actual: &NutritionInfo) -> GoalProgress {
        GoalProgress {
            calories_pct: (actual.calories as f32 / self.calories as f32) * 100.0,
            protein_pct: (actual.protein / self.protein) * 100.0,
            carbs_pct: (actual.carbs / self.carbs) * 100.0,
            fat_pct: (actual.fat / self.fat) * 100.0,
        }
    }

    /// Get remaining nutrients to reach goal
    pub fn remaining(&self, consumed: &NutritionInfo) -> NutritionInfo {
        NutritionInfo {
            calories: self.calories.saturating_sub(consumed.calories),
            protein: (self.protein - consumed.protein).max(0.0),
            carbs: (self.carbs - consumed.carbs).max(0.0),
            fat: (self.fat - consumed.fat).max(0.0),
            ..Default::default()
        }
    }
}

/// Progress towards daily goals (as percentages)
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct GoalProgress {
    pub calories_pct: f32,
    pub protein_pct: f32,
    pub carbs_pct: f32,
    pub fat_pct: f32,
}

impl GoalProgress {
    /// Check if all goals are met (100%+)
    pub fn all_met(&self) -> bool {
        self.calories_pct >= 100.0
            && self.protein_pct >= 100.0
            && self.carbs_pct >= 100.0
            && self.fat_pct >= 100.0
    }

    /// Check if any macro is over 100%
    pub fn any_exceeded(&self) -> bool {
        self.calories_pct > 100.0
            || self.protein_pct > 100.0
            || self.carbs_pct > 100.0
            || self.fat_pct > 100.0
    }

    /// Get overall progress (average of all macros)
    pub fn overall(&self) -> f32 {
        (self.calories_pct + self.protein_pct + self.carbs_pct + self.fat_pct) / 4.0
    }
}

/// Summary of a day's nutrition and meals
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DailySummary {
    /// Date of summary
    pub date: NaiveDate,
    /// All meals logged this day
    pub meals: Vec<Meal>,
    /// Total calories consumed
    pub total_calories: u32,
    /// Total protein consumed
    pub total_protein: f32,
    /// Total carbs consumed
    pub total_carbs: f32,
    /// Total fat consumed
    pub total_fat: f32,
    /// Daily goal (if set)
    pub goal: Option<DailyGoal>,
    /// Progress towards goal
    pub progress: Option<GoalProgress>,
}

impl DailySummary {
    /// Create an empty summary for a date
    pub fn empty(date: NaiveDate) -> Self {
        Self {
            date,
            meals: Vec::new(),
            total_calories: 0,
            total_protein: 0.0,
            total_carbs: 0.0,
            total_fat: 0.0,
            goal: None,
            progress: None,
        }
    }

    /// Create summary from meals and optional goal
    pub fn from_meals(date: NaiveDate, meals: Vec<Meal>, goal: Option<DailyGoal>) -> Self {
        let mut summary = Self {
            date,
            meals,
            total_calories: 0,
            total_protein: 0.0,
            total_carbs: 0.0,
            total_fat: 0.0,
            goal,
            progress: None,
        };

        // Calculate totals from meal nutrition
        for meal in &summary.meals {
            if let Some(ref nutrition) = meal.total_nutrition {
                summary.total_calories += nutrition.calories;
                summary.total_protein += nutrition.protein;
                summary.total_carbs += nutrition.carbs;
                summary.total_fat += nutrition.fat;
            }
        }

        // Calculate progress if we have a goal
        if let Some(ref goal) = summary.goal {
            let actual = NutritionInfo::macros(
                summary.total_calories,
                summary.total_protein,
                summary.total_carbs,
                summary.total_fat,
            );
            summary.progress = Some(goal.calculate_progress(&actual));
        }

        summary
    }

    /// Get total nutrition as NutritionInfo
    pub fn total_nutrition(&self) -> NutritionInfo {
        NutritionInfo::macros(
            self.total_calories,
            self.total_protein,
            self.total_carbs,
            self.total_fat,
        )
    }

    /// Get number of meals logged
    pub fn meal_count(&self) -> usize {
        self.meals.len()
    }

    /// Check if any meals logged
    pub fn has_meals(&self) -> bool {
        !self.meals.is_empty()
    }

    /// Get remaining to hit goal
    pub fn remaining(&self) -> Option<NutritionInfo> {
        self.goal.as_ref().map(|g| g.remaining(&self.total_nutrition()))
    }
}

impl std::fmt::Display for DailySummary {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}: {} meals, {} kcal, {:.1}g protein",
            self.date, self.meals.len(), self.total_calories, self.total_protein
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_daily_goal_default() {
        let goal = DailyGoal::default();
        assert_eq!(goal.calories, 2000);
        assert_eq!(goal.protein, 50.0);
    }

    #[test]
    fn test_goal_progress() {
        let goal = DailyGoal {
            calories: 2000,
            protein: 100.0,
            carbs: 250.0,
            fat: 70.0,
            fiber: 25.0,
            water_ml: 2500,
        };

        let consumed = NutritionInfo::macros(1000, 50.0, 125.0, 35.0);
        let progress = goal.calculate_progress(&consumed);

        assert!((progress.calories_pct - 50.0).abs() < 0.1);
        assert!((progress.protein_pct - 50.0).abs() < 0.1);
    }

    #[test]
    fn test_goal_remaining() {
        let goal = DailyGoal {
            calories: 2000,
            protein: 100.0,
            carbs: 250.0,
            fat: 70.0,
            fiber: 25.0,
            water_ml: 2500,
        };

        let consumed = NutritionInfo::macros(1500, 80.0, 200.0, 60.0);
        let remaining = goal.remaining(&consumed);

        assert_eq!(remaining.calories, 500);
        assert_eq!(remaining.protein, 20.0);
    }

    #[test]
    fn test_user_creation() {
        let user = User::new(
            "testuser".into(),
            "test@example.com".into(),
            "hashed_password".into(),
        );

        assert_eq!(user.username, "testuser");
        assert!(!user.email_verified);
        assert!(user.is_active);
    }

    #[test]
    fn test_user_name_fallback() {
        let user = User::new("john".into(), "john@example.com".into(), "hash".into());
        assert_eq!(user.name(), "john");

        let user_with_display = user.with_display_name("John Doe");
        assert_eq!(user_with_display.name(), "John Doe");
    }

    #[test]
    fn test_daily_summary_empty() {
        let summary = DailySummary::empty(chrono::Local::now().date_naive());
        assert!(!summary.has_meals());
        assert_eq!(summary.total_calories, 0);
    }
}
