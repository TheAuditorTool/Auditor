package models

import (
	"time"

	"gorm.io/gorm"
)

// User represents a registered user in the calorie tracking system.
type User struct {
	ID           uint           `gorm:"primaryKey" json:"id"`
	CreatedAt    time.Time      `json:"created_at"`
	UpdatedAt    time.Time      `json:"updated_at"`
	DeletedAt    gorm.DeletedAt `gorm:"index" json:"-"`
	Email        string         `gorm:"uniqueIndex;size:255;not null" json:"email"`
	PasswordHash string         `gorm:"size:255;not null" json:"-"`
	Name         string         `gorm:"size:100;not null" json:"name"`
	DailyGoal    int            `gorm:"default:2000" json:"daily_goal"`
	Weight       float64        `json:"weight"`
	Height       float64        `json:"height"`
	BirthDate    *time.Time     `json:"birth_date,omitempty"`
	IsActive     bool           `gorm:"default:true" json:"is_active"`

	// Relationships
	Meals       []Meal       `gorm:"foreignKey:UserID" json:"meals,omitempty"`
	FoodEntries []FoodEntry  `gorm:"foreignKey:UserID" json:"food_entries,omitempty"`
	DailyLogs   []DailyLog   `gorm:"foreignKey:UserID" json:"daily_logs,omitempty"`
}

// TableName returns the table name for User model.
func (User) TableName() string {
	return "users"
}

// BMI calculates the user's Body Mass Index.
func (u *User) BMI() float64 {
	if u.Height <= 0 {
		return 0
	}
	heightInMeters := u.Height / 100
	return u.Weight / (heightInMeters * heightInMeters)
}

// Age calculates the user's age from birth date.
func (u *User) Age() int {
	if u.BirthDate == nil {
		return 0
	}
	now := time.Now()
	age := now.Year() - u.BirthDate.Year()
	if now.YearDay() < u.BirthDate.YearDay() {
		age--
	}
	return age
}

// TDEE estimates Total Daily Energy Expenditure using Mifflin-St Jeor equation.
// activityLevel: 1.2 (sedentary) to 1.9 (very active)
func (u *User) TDEE(activityLevel float64, isMale bool) float64 {
	if u.Weight <= 0 || u.Height <= 0 {
		return 0
	}

	var bmr float64
	age := float64(u.Age())

	if isMale {
		bmr = 10*u.Weight + 6.25*u.Height - 5*age + 5
	} else {
		bmr = 10*u.Weight + 6.25*u.Height - 5*age - 161
	}

	return bmr * activityLevel
}
