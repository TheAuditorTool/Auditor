//! Food and nutrition data models.

use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

use super::{Identifiable, Timestamped};
use crate::{validate_nutrition, CalorieTrackerError, Result};

/// Category of food for organization and filtering
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FoodCategory {
    Protein,
    Carbohydrate,
    Vegetable,
    Fruit,
    Dairy,
    Fat,
    Beverage,
    Snack,
    Condiment,
    Other,
}

impl Default for FoodCategory {
    fn default() -> Self {
        Self::Other
    }
}

impl std::fmt::Display for FoodCategory {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            Self::Protein => "Protein",
            Self::Carbohydrate => "Carbohydrate",
            Self::Vegetable => "Vegetable",
            Self::Fruit => "Fruit",
            Self::Dairy => "Dairy",
            Self::Fat => "Fat",
            Self::Beverage => "Beverage",
            Self::Snack => "Snack",
            Self::Condiment => "Condiment",
            Self::Other => "Other",
        };
        write!(f, "{}", s)
    }
}

/// Detailed nutrition information
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct NutritionInfo {
    /// Calories in kcal
    pub calories: u32,
    /// Protein in grams
    pub protein: f32,
    /// Carbohydrates in grams
    pub carbs: f32,
    /// Fat in grams
    pub fat: f32,
    /// Fiber in grams (optional)
    #[serde(default)]
    pub fiber: f32,
    /// Sugar in grams (optional)
    #[serde(default)]
    pub sugar: f32,
    /// Sodium in mg (optional)
    #[serde(default)]
    pub sodium: f32,
}

impl NutritionInfo {
    /// Create new nutrition info with macros only
    pub fn macros(calories: u32, protein: f32, carbs: f32, fat: f32) -> Self {
        Self {
            calories,
            protein,
            carbs,
            fat,
            ..Default::default()
        }
    }

    /// Calculate total macros in grams
    pub fn total_macros(&self) -> f32 {
        self.protein + self.carbs + self.fat
    }

    /// Get protein as percentage of total calories
    pub fn protein_pct(&self) -> f32 {
        if self.calories == 0 {
            return 0.0;
        }
        // 4 calories per gram of protein
        (self.protein * 4.0 / self.calories as f32) * 100.0
    }

    /// Get carbs as percentage of total calories
    pub fn carbs_pct(&self) -> f32 {
        if self.calories == 0 {
            return 0.0;
        }
        // 4 calories per gram of carbs
        (self.carbs * 4.0 / self.calories as f32) * 100.0
    }

    /// Get fat as percentage of total calories
    pub fn fat_pct(&self) -> f32 {
        if self.calories == 0 {
            return 0.0;
        }
        // 9 calories per gram of fat
        (self.fat * 9.0 / self.calories as f32) * 100.0
    }

    /// Add nutrition info from another item
    pub fn add(&mut self, other: &NutritionInfo) {
        self.calories += other.calories;
        self.protein += other.protein;
        self.carbs += other.carbs;
        self.fat += other.fat;
        self.fiber += other.fiber;
        self.sugar += other.sugar;
        self.sodium += other.sodium;
    }

    /// Scale nutrition by a factor (e.g., 0.5 for half serving)
    pub fn scale(&self, factor: f32) -> Self {
        Self {
            calories: (self.calories as f32 * factor).round() as u32,
            protein: self.protein * factor,
            carbs: self.carbs * factor,
            fat: self.fat * factor,
            fiber: self.fiber * factor,
            sugar: self.sugar * factor,
            sodium: self.sodium * factor,
        }
    }

    /// Validate the nutrition values are reasonable
    pub fn validate(&self) -> Result<()> {
        validate_nutrition(self.calories, self.protein, self.carbs, self.fat)
    }
}

impl std::ops::Add for NutritionInfo {
    type Output = Self;

    fn add(self, rhs: Self) -> Self::Output {
        Self {
            calories: self.calories + rhs.calories,
            protein: self.protein + rhs.protein,
            carbs: self.carbs + rhs.carbs,
            fat: self.fat + rhs.fat,
            fiber: self.fiber + rhs.fiber,
            sugar: self.sugar + rhs.sugar,
            sodium: self.sodium + rhs.sodium,
        }
    }
}

/// A food item with nutritional information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Food {
    /// Unique identifier
    pub id: Uuid,
    /// Name of the food
    pub name: String,
    /// Serving size description
    pub serving_size: String,
    /// Nutritional information per serving
    pub nutrition: NutritionInfo,
    /// Category for organization
    #[serde(default)]
    pub category: FoodCategory,
    /// Brand name (if applicable)
    #[serde(default)]
    pub brand: Option<String>,
    /// Barcode/UPC (if applicable)
    #[serde(default)]
    pub barcode: Option<String>,
    /// User notes
    #[serde(default)]
    pub notes: Option<String>,
    /// Whether this is a custom user-created food
    #[serde(default)]
    pub is_custom: bool,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last update timestamp
    pub updated_at: DateTime<Utc>,
}

impl Food {
    /// Create a new food item with basic info
    pub fn new(
        name: impl Into<String>,
        calories: u32,
        protein: f32,
        carbs: f32,
        fat: f32,
        serving_size: impl Into<String>,
    ) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            name: name.into(),
            serving_size: serving_size.into(),
            nutrition: NutritionInfo::macros(calories, protein, carbs, fat),
            category: FoodCategory::default(),
            brand: None,
            barcode: None,
            notes: None,
            is_custom: true,
            created_at: now,
            updated_at: now,
        }
    }

    /// Create a food with full nutrition info
    pub fn with_nutrition(
        name: impl Into<String>,
        serving_size: impl Into<String>,
        nutrition: NutritionInfo,
    ) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            name: name.into(),
            serving_size: serving_size.into(),
            nutrition,
            category: FoodCategory::default(),
            brand: None,
            barcode: None,
            notes: None,
            is_custom: true,
            created_at: now,
            updated_at: now,
        }
    }

    /// Convenience getters for common nutritional values
    pub fn calories(&self) -> u32 {
        self.nutrition.calories
    }

    pub fn protein(&self) -> f32 {
        self.nutrition.protein
    }

    pub fn carbs(&self) -> f32 {
        self.nutrition.carbs
    }

    pub fn fat(&self) -> f32 {
        self.nutrition.fat
    }

    /// Set the category
    pub fn with_category(mut self, category: FoodCategory) -> Self {
        self.category = category;
        self
    }

    /// Set the brand
    pub fn with_brand(mut self, brand: impl Into<String>) -> Self {
        self.brand = Some(brand.into());
        self
    }

    /// Set the barcode
    pub fn with_barcode(mut self, barcode: impl Into<String>) -> Self {
        self.barcode = Some(barcode.into());
        self
    }

    /// Validate this food item
    pub fn validate(&self) -> Result<()> {
        if self.name.trim().is_empty() {
            return Err(CalorieTrackerError::Validation {
                field: "name".into(),
                message: "Food name cannot be empty".into(),
            });
        }

        if self.name.len() > 200 {
            return Err(CalorieTrackerError::Validation {
                field: "name".into(),
                message: "Food name cannot exceed 200 characters".into(),
            });
        }

        self.nutrition.validate()
    }

    /// Calculate nutrition for a specific number of servings
    pub fn nutrition_for_servings(&self, servings: f32) -> NutritionInfo {
        self.nutrition.scale(servings)
    }
}

impl Identifiable for Food {
    fn id(&self) -> Uuid {
        self.id
    }
}

impl Timestamped for Food {
    fn created_at(&self) -> DateTime<Utc> {
        self.created_at
    }

    fn updated_at(&self) -> DateTime<Utc> {
        self.updated_at
    }
}

impl std::fmt::Display for Food {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{} ({}) - {} kcal, {}g protein",
            self.name, self.serving_size, self.calories(), self.protein()
        )
    }
}

/// Builder for creating Food items with fluent API
#[derive(Debug, Default)]
pub struct FoodBuilder {
    name: Option<String>,
    serving_size: Option<String>,
    nutrition: NutritionInfo,
    category: FoodCategory,
    brand: Option<String>,
    barcode: Option<String>,
    notes: Option<String>,
}

impl FoodBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn name(mut self, name: impl Into<String>) -> Self {
        self.name = Some(name.into());
        self
    }

    pub fn serving_size(mut self, size: impl Into<String>) -> Self {
        self.serving_size = Some(size.into());
        self
    }

    pub fn calories(mut self, calories: u32) -> Self {
        self.nutrition.calories = calories;
        self
    }

    pub fn protein(mut self, grams: f32) -> Self {
        self.nutrition.protein = grams;
        self
    }

    pub fn carbs(mut self, grams: f32) -> Self {
        self.nutrition.carbs = grams;
        self
    }

    pub fn fat(mut self, grams: f32) -> Self {
        self.nutrition.fat = grams;
        self
    }

    pub fn fiber(mut self, grams: f32) -> Self {
        self.nutrition.fiber = grams;
        self
    }

    pub fn category(mut self, category: FoodCategory) -> Self {
        self.category = category;
        self
    }

    pub fn brand(mut self, brand: impl Into<String>) -> Self {
        self.brand = Some(brand.into());
        self
    }

    pub fn barcode(mut self, barcode: impl Into<String>) -> Self {
        self.barcode = Some(barcode.into());
        self
    }

    pub fn notes(mut self, notes: impl Into<String>) -> Self {
        self.notes = Some(notes.into());
        self
    }

    pub fn build(self) -> Result<Food> {
        let name = self.name.ok_or_else(|| CalorieTrackerError::Validation {
            field: "name".into(),
            message: "Food name is required".into(),
        })?;

        let serving_size = self.serving_size.unwrap_or_else(|| "1 serving".into());

        let now = Utc::now();
        let food = Food {
            id: Uuid::new_v4(),
            name,
            serving_size,
            nutrition: self.nutrition,
            category: self.category,
            brand: self.brand,
            barcode: self.barcode,
            notes: self.notes,
            is_custom: true,
            created_at: now,
            updated_at: now,
        };

        food.validate()?;
        Ok(food)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_food_creation() {
        let food = Food::new("Chicken Breast", 165, 31.0, 0.0, 3.6, "100g");
        assert_eq!(food.name, "Chicken Breast");
        assert_eq!(food.calories(), 165);
        assert_eq!(food.protein(), 31.0);
    }

    #[test]
    fn test_nutrition_percentages() {
        let nutrition = NutritionInfo::macros(200, 20.0, 20.0, 10.0);
        // 20g protein * 4 cal/g = 80 cal = 40% of 200
        assert!((nutrition.protein_pct() - 40.0).abs() < 0.1);
    }

    #[test]
    fn test_nutrition_scaling() {
        let nutrition = NutritionInfo::macros(100, 10.0, 20.0, 5.0);
        let half = nutrition.scale(0.5);
        assert_eq!(half.calories, 50);
        assert_eq!(half.protein, 5.0);
    }

    #[test]
    fn test_food_builder() {
        let food = FoodBuilder::new()
            .name("Test Food")
            .calories(100)
            .protein(10.0)
            .category(FoodCategory::Protein)
            .build()
            .unwrap();

        assert_eq!(food.name, "Test Food");
        assert_eq!(food.category, FoodCategory::Protein);
    }

    #[test]
    fn test_food_builder_missing_name() {
        let result = FoodBuilder::new()
            .calories(100)
            .build();

        assert!(result.is_err());
    }

    #[test]
    fn test_nutrition_add() {
        let a = NutritionInfo::macros(100, 10.0, 15.0, 5.0);
        let b = NutritionInfo::macros(200, 20.0, 25.0, 10.0);
        let sum = a + b;

        assert_eq!(sum.calories, 300);
        assert_eq!(sum.protein, 30.0);
    }
}
