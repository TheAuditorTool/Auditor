//! Meal logging models.

use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, NaiveDate, Utc, Local};

use super::{Food, NutritionInfo, Identifiable, Timestamped};

/// Type of meal for categorization
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MealType {
    Breakfast,
    Lunch,
    Dinner,
    Snack,
}

impl MealType {
    /// Get all meal types in typical daily order
    pub fn all() -> [Self; 4] {
        [Self::Breakfast, Self::Lunch, Self::Dinner, Self::Snack]
    }

    /// Get typical time range for this meal type
    pub fn typical_hours(&self) -> (u32, u32) {
        match self {
            Self::Breakfast => (6, 10),
            Self::Lunch => (11, 14),
            Self::Dinner => (17, 21),
            Self::Snack => (0, 24), // Any time
        }
    }

    /// Check if a given hour is typical for this meal type
    pub fn is_typical_time(&self, hour: u32) -> bool {
        let (start, end) = self.typical_hours();
        hour >= start && hour < end
    }
}

impl std::fmt::Display for MealType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            Self::Breakfast => "Breakfast",
            Self::Lunch => "Lunch",
            Self::Dinner => "Dinner",
            Self::Snack => "Snack",
        };
        write!(f, "{}", s)
    }
}

impl Default for MealType {
    fn default() -> Self {
        // Guess based on current time
        let hour = Local::now().hour();
        if hour < 10 {
            Self::Breakfast
        } else if hour < 14 {
            Self::Lunch
        } else if hour < 17 {
            Self::Snack
        } else {
            Self::Dinner
        }
    }
}

/// Entry for a single food item in a meal with quantity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MealEntry {
    /// Reference to the food item
    pub food_id: Uuid,
    /// Number of servings consumed
    pub servings: f32,
    /// Optional notes (e.g., "grilled, no oil")
    pub notes: Option<String>,
}

impl MealEntry {
    /// Create a new meal entry with default 1 serving
    pub fn new(food_id: Uuid) -> Self {
        Self {
            food_id,
            servings: 1.0,
            notes: None,
        }
    }

    /// Create a meal entry with specific servings
    pub fn with_servings(food_id: Uuid, servings: f32) -> Self {
        Self {
            food_id,
            servings,
            notes: None,
        }
    }

    /// Add notes to this entry
    pub fn with_notes(mut self, notes: impl Into<String>) -> Self {
        self.notes = Some(notes.into());
        self
    }

    /// Calculate nutrition for this entry given the food
    pub fn calculate_nutrition(&self, food: &Food) -> NutritionInfo {
        food.nutrition_for_servings(self.servings)
    }
}

/// A logged meal with associated food items
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Meal {
    /// Unique identifier
    pub id: Uuid,
    /// Type of meal
    pub meal_type: MealType,
    /// Date of the meal
    pub date: NaiveDate,
    /// Free-form description
    pub description: String,
    /// Food entries in this meal
    pub entries: Vec<MealEntry>,
    /// Cached total nutrition (calculated from entries)
    #[serde(default)]
    pub total_nutrition: Option<NutritionInfo>,
    /// User who logged this meal
    pub user_id: Option<Uuid>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last update timestamp
    pub updated_at: DateTime<Utc>,
}

impl Meal {
    /// Create a new meal with description and food IDs
    pub fn new(
        meal_type: MealType,
        description: impl Into<String>,
        food_ids: Vec<Uuid>,
    ) -> Self {
        let now = Utc::now();
        let entries = food_ids.into_iter().map(MealEntry::new).collect();

        Self {
            id: Uuid::new_v4(),
            meal_type,
            date: Local::now().date_naive(),
            description: description.into(),
            entries,
            total_nutrition: None,
            user_id: None,
            created_at: now,
            updated_at: now,
        }
    }

    /// Create an empty meal for a specific date
    pub fn empty(meal_type: MealType, date: NaiveDate) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            meal_type,
            date,
            description: String::new(),
            entries: Vec::new(),
            total_nutrition: None,
            user_id: None,
            created_at: now,
            updated_at: now,
        }
    }

    /// Add a food entry to this meal
    pub fn add_entry(&mut self, entry: MealEntry) {
        self.entries.push(entry);
        self.total_nutrition = None; // Invalidate cache
        self.updated_at = Utc::now();
    }

    /// Add food with specific servings
    pub fn add_food(&mut self, food_id: Uuid, servings: f32) {
        self.add_entry(MealEntry::with_servings(food_id, servings));
    }

    /// Remove a food entry by food_id (removes first match)
    pub fn remove_food(&mut self, food_id: Uuid) -> Option<MealEntry> {
        if let Some(pos) = self.entries.iter().position(|e| e.food_id == food_id) {
            self.total_nutrition = None;
            self.updated_at = Utc::now();
            Some(self.entries.remove(pos))
        } else {
            None
        }
    }

    /// Calculate total nutrition from entries and foods
    pub fn calculate_nutrition<'a>(
        &self,
        foods: impl IntoIterator<Item = &'a Food>,
    ) -> NutritionInfo {
        let food_map: std::collections::HashMap<Uuid, &Food> =
            foods.into_iter().map(|f| (f.id, f)).collect();

        let mut total = NutritionInfo::default();
        for entry in &self.entries {
            if let Some(food) = food_map.get(&entry.food_id) {
                total.add(&entry.calculate_nutrition(food));
            }
        }
        total
    }

    /// Get number of food entries
    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    /// Check if meal is empty
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty() && self.description.is_empty()
    }

    /// Set the user who logged this meal
    pub fn with_user(mut self, user_id: Uuid) -> Self {
        self.user_id = Some(user_id);
        self
    }

    /// Set a specific date
    pub fn with_date(mut self, date: NaiveDate) -> Self {
        self.date = date;
        self
    }
}

impl Identifiable for Meal {
    fn id(&self) -> Uuid {
        self.id
    }
}

impl Timestamped for Meal {
    fn created_at(&self) -> DateTime<Utc> {
        self.created_at
    }

    fn updated_at(&self) -> DateTime<Utc> {
        self.updated_at
    }
}

impl std::fmt::Display for Meal {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{} on {}: {} ({} items)",
            self.meal_type,
            self.date,
            if self.description.is_empty() {
                "(no description)"
            } else {
                &self.description
            },
            self.entries.len()
        )
    }
}

/// Quick log entry without food database lookup
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuickLog {
    /// Meal type
    pub meal_type: MealType,
    /// Date
    pub date: NaiveDate,
    /// Description of what was eaten
    pub description: String,
    /// Estimated total calories
    pub estimated_calories: Option<u32>,
}

impl QuickLog {
    /// Create a new quick log
    pub fn new(meal_type: MealType, description: impl Into<String>) -> Self {
        Self {
            meal_type,
            date: Local::now().date_naive(),
            description: description.into(),
            estimated_calories: None,
        }
    }

    /// Set estimated calories
    pub fn with_calories(mut self, calories: u32) -> Self {
        self.estimated_calories = Some(calories);
        self
    }

    /// Convert to a full Meal (without food entries)
    pub fn to_meal(self) -> Meal {
        Meal::new(self.meal_type, self.description, vec![])
            .with_date(self.date)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_meal_type_typical_time() {
        assert!(MealType::Breakfast.is_typical_time(8));
        assert!(!MealType::Breakfast.is_typical_time(15));
        assert!(MealType::Snack.is_typical_time(15)); // Snacks anytime
    }

    #[test]
    fn test_meal_creation() {
        let food_id = Uuid::new_v4();
        let meal = Meal::new(MealType::Lunch, "Salad with chicken", vec![food_id]);

        assert_eq!(meal.meal_type, MealType::Lunch);
        assert_eq!(meal.entries.len(), 1);
        assert_eq!(meal.entries[0].food_id, food_id);
    }

    #[test]
    fn test_meal_add_remove() {
        let mut meal = Meal::empty(MealType::Dinner, Local::now().date_naive());
        let food_id = Uuid::new_v4();

        meal.add_food(food_id, 1.5);
        assert_eq!(meal.entry_count(), 1);

        let removed = meal.remove_food(food_id);
        assert!(removed.is_some());
        assert_eq!(meal.entry_count(), 0);
    }

    #[test]
    fn test_meal_entry_with_notes() {
        let entry = MealEntry::new(Uuid::new_v4())
            .with_notes("No sauce");

        assert_eq!(entry.notes.unwrap(), "No sauce");
    }

    #[test]
    fn test_quick_log_conversion() {
        let log = QuickLog::new(MealType::Breakfast, "Coffee and toast")
            .with_calories(300);

        let meal = log.to_meal();
        assert_eq!(meal.meal_type, MealType::Breakfast);
        assert!(meal.entries.is_empty());
    }
}
