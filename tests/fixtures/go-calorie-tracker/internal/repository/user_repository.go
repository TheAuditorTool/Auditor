package repository

import (
	"errors"
	"time"

	"github.com/example/calorie-tracker/internal/database"
	"github.com/example/calorie-tracker/internal/models"
	"gorm.io/gorm"
)

var (
	ErrUserNotFound     = errors.New("user not found")
	ErrEmailExists      = errors.New("email already exists")
	ErrInvalidUserData  = errors.New("invalid user data")
)

// UserRepository handles user data persistence.
type UserRepository struct {
	db *gorm.DB
}

// NewUserRepository creates a new UserRepository.
func NewUserRepository() *UserRepository {
	return &UserRepository{db: database.DB}
}

// Create creates a new user.
func (r *UserRepository) Create(user *models.User) error {
	if user.Email == "" || user.PasswordHash == "" {
		return ErrInvalidUserData
	}

	// Check if email exists
	var count int64
	r.db.Model(&models.User{}).Where("email = ?", user.Email).Count(&count)
	if count > 0 {
		return ErrEmailExists
	}

	return r.db.Create(user).Error
}

// GetByID retrieves a user by ID.
func (r *UserRepository) GetByID(id uint) (*models.User, error) {
	var user models.User
	err := r.db.First(&user, id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrUserNotFound
	}
	return &user, err
}

// GetByEmail retrieves a user by email.
func (r *UserRepository) GetByEmail(email string) (*models.User, error) {
	var user models.User
	err := r.db.Where("email = ?", email).First(&user).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrUserNotFound
	}
	return &user, err
}

// Update updates a user's information.
func (r *UserRepository) Update(user *models.User) error {
	return r.db.Save(user).Error
}

// UpdateProfile updates specific profile fields.
func (r *UserRepository) UpdateProfile(userID uint, name string, dailyGoal int, weight, height float64) error {
	return r.db.Model(&models.User{}).
		Where("id = ?", userID).
		Updates(map[string]interface{}{
			"name":       name,
			"daily_goal": dailyGoal,
			"weight":     weight,
			"height":     height,
			"updated_at": time.Now(),
		}).Error
}

// Delete soft-deletes a user.
func (r *UserRepository) Delete(id uint) error {
	return r.db.Delete(&models.User{}, id).Error
}

// GetWithDailyLogs retrieves a user with their daily logs.
func (r *UserRepository) GetWithDailyLogs(userID uint, startDate, endDate time.Time) (*models.User, error) {
	var user models.User
	err := r.db.
		Preload("DailyLogs", "date >= ? AND date <= ?", startDate, endDate).
		First(&user, userID).Error

	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrUserNotFound
	}
	return &user, err
}

// GetActiveUsers returns all active users.
func (r *UserRepository) GetActiveUsers() ([]models.User, error) {
	var users []models.User
	err := r.db.Where("is_active = ?", true).Find(&users).Error
	return users, err
}

// DeactivateUser marks a user as inactive.
func (r *UserRepository) DeactivateUser(id uint) error {
	return r.db.Model(&models.User{}).
		Where("id = ?", id).
		Update("is_active", false).Error
}
