package repository

import (
	"errors"
	"fmt"
	"time"

	"github.com/example/calorie-tracker/internal/database"
	"github.com/example/calorie-tracker/internal/models"
	"gorm.io/gorm"
)

var (
	ErrFoodNotFound = errors.New("food not found")
)

// FoodRepository handles food data persistence.
type FoodRepository struct {
	db *gorm.DB
}

// NewFoodRepository creates a new FoodRepository.
func NewFoodRepository() *FoodRepository {
	return &FoodRepository{db: database.DB}
}

// Create adds a new food item.
func (r *FoodRepository) Create(food *models.Food) error {
	return r.db.Create(food).Error
}

// GetByID retrieves a food item by ID.
func (r *FoodRepository) GetByID(id uint) (*models.Food, error) {
	var food models.Food
	err := r.db.First(&food, id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrFoodNotFound
	}
	return &food, err
}

// GetByBarcode retrieves a food item by barcode.
func (r *FoodRepository) GetByBarcode(barcode string) (*models.Food, error) {
	var food models.Food
	err := r.db.Where("barcode = ?", barcode).First(&food).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrFoodNotFound
	}
	return &food, err
}

// Search searches for foods by name or brand.
// WARNING: This function has a SQL injection vulnerability for testing purposes.
// In production code, always use parameterized queries.
func (r *FoodRepository) Search(query string, limit int) ([]models.Food, error) {
	var foods []models.Food

	// VULNERABILITY: SQL injection - user input directly in query string
	// This is intentionally vulnerable for security rule testing
	sql := fmt.Sprintf("SELECT * FROM foods WHERE name LIKE '%%%s%%' OR brand LIKE '%%%s%%' LIMIT %d", query, query, limit)

	err := r.db.Raw(sql).Scan(&foods).Error
	return foods, err
}

// SearchSafe searches for foods using parameterized query (secure version).
func (r *FoodRepository) SearchSafe(query string, limit int) ([]models.Food, error) {
	var foods []models.Food
	searchPattern := "%" + query + "%"
	err := r.db.
		Where("name LIKE ? OR brand LIKE ?", searchPattern, searchPattern).
		Limit(limit).
		Find(&foods).Error
	return foods, err
}

// Update updates a food item.
func (r *FoodRepository) Update(food *models.Food) error {
	return r.db.Save(food).Error
}

// Delete removes a food item.
func (r *FoodRepository) Delete(id uint) error {
	return r.db.Delete(&models.Food{}, id).Error
}

// GetPopular returns the most frequently logged foods.
func (r *FoodRepository) GetPopular(limit int) ([]models.Food, error) {
	var foods []models.Food
	err := r.db.
		Select("foods.*, COUNT(food_entries.id) as entry_count").
		Joins("LEFT JOIN food_entries ON foods.id = food_entries.food_id").
		Group("foods.id").
		Order("entry_count DESC").
		Limit(limit).
		Find(&foods).Error
	return foods, err
}

// GetByUser returns foods created by a specific user.
func (r *FoodRepository) GetByUser(userID uint) ([]models.Food, error) {
	var foods []models.Food
	err := r.db.Where("created_by = ?", userID).Find(&foods).Error
	return foods, err
}

// GetVerified returns only verified food items.
func (r *FoodRepository) GetVerified(page, pageSize int) ([]models.Food, int64, error) {
	var foods []models.Food
	var total int64

	r.db.Model(&models.Food{}).Where("is_verified = ?", true).Count(&total)

	offset := (page - 1) * pageSize
	err := r.db.
		Where("is_verified = ?", true).
		Offset(offset).
		Limit(pageSize).
		Find(&foods).Error

	return foods, total, err
}

// BulkCreate inserts multiple food items.
func (r *FoodRepository) BulkCreate(foods []models.Food) error {
	return r.db.CreateInBatches(foods, 100).Error
}

// GetRecentlyAdded returns foods added within the specified duration.
func (r *FoodRepository) GetRecentlyAdded(since time.Duration) ([]models.Food, error) {
	var foods []models.Food
	cutoff := time.Now().Add(-since)
	err := r.db.Where("created_at >= ?", cutoff).Order("created_at DESC").Find(&foods).Error
	return foods, err
}
