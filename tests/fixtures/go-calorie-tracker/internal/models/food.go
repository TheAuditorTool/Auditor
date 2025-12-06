package models

import (
	"time"

	"gorm.io/gorm"
)

// Food represents a food item in the database with nutritional information.
type Food struct {
	ID          uint           `gorm:"primaryKey" json:"id"`
	CreatedAt   time.Time      `json:"created_at"`
	UpdatedAt   time.Time      `json:"updated_at"`
	DeletedAt   gorm.DeletedAt `gorm:"index" json:"-"`
	Name        string         `gorm:"size:255;not null;index" json:"name"`
	Brand       string         `gorm:"size:255" json:"brand,omitempty"`
	Barcode     string         `gorm:"size:50;index" json:"barcode,omitempty"`
	ServingSize float64        `gorm:"not null" json:"serving_size"`
	ServingUnit string         `gorm:"size:20;not null" json:"serving_unit"`
	Calories    int            `gorm:"not null" json:"calories"`
	Protein     float64        `json:"protein"`
	Carbs       float64        `json:"carbs"`
	Fat         float64        `json:"fat"`
	Fiber       float64        `json:"fiber"`
	Sugar       float64        `json:"sugar"`
	Sodium      float64        `json:"sodium"`
	IsVerified  bool           `gorm:"default:false" json:"is_verified"`
	CreatedBy   *uint          `json:"created_by,omitempty"`

	// Relationships
	FoodEntries []FoodEntry `gorm:"foreignKey:FoodID" json:"-"`
}

// TableName returns the table name for Food model.
func (Food) TableName() string {
	return "foods"
}

// CaloriesPerGram returns the calorie density of the food.
func (f *Food) CaloriesPerGram() float64 {
	if f.ServingSize <= 0 {
		return 0
	}
	return float64(f.Calories) / f.ServingSize
}

// Macros returns the macro breakdown as percentages.
func (f *Food) Macros() (proteinPct, carbsPct, fatPct float64) {
	totalCals := float64(f.Calories)
	if totalCals <= 0 {
		return 0, 0, 0
	}

	// Protein and carbs = 4 cal/g, fat = 9 cal/g
	proteinCals := f.Protein * 4
	carbsCals := f.Carbs * 4
	fatCals := f.Fat * 9

	proteinPct = (proteinCals / totalCals) * 100
	carbsPct = (carbsCals / totalCals) * 100
	fatPct = (fatCals / totalCals) * 100

	return
}

// FoodEntry represents a logged food item with quantity for a user.
type FoodEntry struct {
	ID        uint           `gorm:"primaryKey" json:"id"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
	DeletedAt gorm.DeletedAt `gorm:"index" json:"-"`
	UserID    uint           `gorm:"not null;index" json:"user_id"`
	FoodID    uint           `gorm:"not null;index" json:"food_id"`
	MealID    *uint          `gorm:"index" json:"meal_id,omitempty"`
	Quantity  float64        `gorm:"not null" json:"quantity"`
	LoggedAt  time.Time      `gorm:"not null;index" json:"logged_at"`
	Notes     string         `gorm:"size:500" json:"notes,omitempty"`

	// Relationships
	User *User `gorm:"foreignKey:UserID" json:"user,omitempty"`
	Food *Food `gorm:"foreignKey:FoodID" json:"food,omitempty"`
	Meal *Meal `gorm:"foreignKey:MealID" json:"meal,omitempty"`
}

// TableName returns the table name for FoodEntry model.
func (FoodEntry) TableName() string {
	return "food_entries"
}

// TotalCalories calculates the calories for this entry based on quantity.
func (fe *FoodEntry) TotalCalories() int {
	if fe.Food == nil {
		return 0
	}
	return int(float64(fe.Food.Calories) * fe.Quantity)
}

// TotalProtein calculates protein for this entry.
func (fe *FoodEntry) TotalProtein() float64 {
	if fe.Food == nil {
		return 0
	}
	return fe.Food.Protein * fe.Quantity
}

// TotalCarbs calculates carbs for this entry.
func (fe *FoodEntry) TotalCarbs() float64 {
	if fe.Food == nil {
		return 0
	}
	return fe.Food.Carbs * fe.Quantity
}

// TotalFat calculates fat for this entry.
func (fe *FoodEntry) TotalFat() float64 {
	if fe.Food == nil {
		return 0
	}
	return fe.Food.Fat * fe.Quantity
}
