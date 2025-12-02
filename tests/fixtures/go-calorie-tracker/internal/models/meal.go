package models

import (
	"time"

	"gorm.io/gorm"
)

// MealType represents the type of meal.
type MealType string

const (
	MealTypeBreakfast MealType = "breakfast"
	MealTypeLunch     MealType = "lunch"
	MealTypeDinner    MealType = "dinner"
	MealTypeSnack     MealType = "snack"
)

// Meal represents a grouped collection of food entries for a specific meal.
type Meal struct {
	ID        uint           `gorm:"primaryKey" json:"id"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
	DeletedAt gorm.DeletedAt `gorm:"index" json:"-"`
	UserID    uint           `gorm:"not null;index" json:"user_id"`
	Type      MealType       `gorm:"size:20;not null" json:"type"`
	Name      string         `gorm:"size:100" json:"name,omitempty"`
	LoggedAt  time.Time      `gorm:"not null;index" json:"logged_at"`
	Notes     string         `gorm:"size:500" json:"notes,omitempty"`

	// Relationships
	User        *User       `gorm:"foreignKey:UserID" json:"user,omitempty"`
	FoodEntries []FoodEntry `gorm:"foreignKey:MealID" json:"food_entries,omitempty"`
}

// TableName returns the table name for Meal model.
func (Meal) TableName() string {
	return "meals"
}

// TotalCalories sums up calories from all food entries in this meal.
func (m *Meal) TotalCalories() int {
	total := 0
	for _, entry := range m.FoodEntries {
		total += entry.TotalCalories()
	}
	return total
}

// TotalMacros returns the total macros for the meal.
func (m *Meal) TotalMacros() (protein, carbs, fat float64) {
	for _, entry := range m.FoodEntries {
		protein += entry.TotalProtein()
		carbs += entry.TotalCarbs()
		fat += entry.TotalFat()
	}
	return
}

// DailyLog represents a daily summary of nutrition for a user.
type DailyLog struct {
	ID            uint           `gorm:"primaryKey" json:"id"`
	CreatedAt     time.Time      `json:"created_at"`
	UpdatedAt     time.Time      `json:"updated_at"`
	DeletedAt     gorm.DeletedAt `gorm:"index" json:"-"`
	UserID        uint           `gorm:"not null;uniqueIndex:idx_user_date" json:"user_id"`
	Date          time.Time      `gorm:"not null;uniqueIndex:idx_user_date;type:date" json:"date"`
	TotalCalories int            `json:"total_calories"`
	TotalProtein  float64        `json:"total_protein"`
	TotalCarbs    float64        `json:"total_carbs"`
	TotalFat      float64        `json:"total_fat"`
	GoalCalories  int            `json:"goal_calories"`
	WaterIntake   float64        `json:"water_intake"`
	Weight        *float64       `json:"weight,omitempty"`
	Notes         string         `gorm:"size:1000" json:"notes,omitempty"`

	// Relationships
	User *User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

// TableName returns the table name for DailyLog model.
func (DailyLog) TableName() string {
	return "daily_logs"
}

// CalorieBalance returns the difference between consumed and goal calories.
// Positive means over goal, negative means under.
func (dl *DailyLog) CalorieBalance() int {
	return dl.TotalCalories - dl.GoalCalories
}

// GoalProgress returns the percentage of daily calorie goal achieved.
func (dl *DailyLog) GoalProgress() float64 {
	if dl.GoalCalories <= 0 {
		return 0
	}
	return float64(dl.TotalCalories) / float64(dl.GoalCalories) * 100
}

// IsUnderGoal returns true if calories consumed are under the goal.
func (dl *DailyLog) IsUnderGoal() bool {
	return dl.TotalCalories < dl.GoalCalories
}
