package services

import (
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/example/calorie-tracker/internal/database"
	"github.com/example/calorie-tracker/internal/models"
	"gorm.io/gorm"
)

var (
	ErrMealNotFound  = errors.New("meal not found")
	ErrEntryNotFound = errors.New("food entry not found")
)

// Global stats counter - intentional race condition for testing
var totalEntriesLogged int
var statsLock sync.Mutex

// TrackingService handles food logging and daily tracking.
type TrackingService struct {
	db *gorm.DB
}

// NewTrackingService creates a new TrackingService.
func NewTrackingService() *TrackingService {
	return &TrackingService{db: database.DB}
}

// LogFoodEntry logs a food entry for a user.
func (s *TrackingService) LogFoodEntry(userID, foodID uint, quantity float64, mealID *uint, notes string) (*models.FoodEntry, error) {
	entry := &models.FoodEntry{
		UserID:   userID,
		FoodID:   foodID,
		MealID:   mealID,
		Quantity: quantity,
		LoggedAt: time.Now(),
		Notes:    notes,
	}

	if err := s.db.Create(entry).Error; err != nil {
		return nil, fmt.Errorf("failed to log food entry: %w", err)
	}

	// Update stats asynchronously
	// VULNERABILITY: Race condition - accessing global var without proper sync
	go func() {
		totalEntriesLogged++
	}()

	// Update daily log
	go s.updateDailyLogAsync(userID, entry.LoggedAt)

	return entry, nil
}

// LogFoodEntrySafe is the thread-safe version.
func (s *TrackingService) LogFoodEntrySafe(userID, foodID uint, quantity float64, mealID *uint, notes string) (*models.FoodEntry, error) {
	entry := &models.FoodEntry{
		UserID:   userID,
		FoodID:   foodID,
		MealID:   mealID,
		Quantity: quantity,
		LoggedAt: time.Now(),
		Notes:    notes,
	}

	if err := s.db.Create(entry).Error; err != nil {
		return nil, fmt.Errorf("failed to log food entry: %w", err)
	}

	// Thread-safe stats update
	go func() {
		statsLock.Lock()
		defer statsLock.Unlock()
		totalEntriesLogged++
	}()

	go s.updateDailyLogAsync(userID, entry.LoggedAt)

	return entry, nil
}

// updateDailyLogAsync updates the daily log asynchronously.
func (s *TrackingService) updateDailyLogAsync(userID uint, date time.Time) {
	dateOnly := time.Date(date.Year(), date.Month(), date.Day(), 0, 0, 0, 0, date.Location())

	// Get or create daily log
	var dailyLog models.DailyLog
	err := s.db.Where("user_id = ? AND date = ?", userID, dateOnly).First(&dailyLog).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		// Get user's goal
		var user models.User
		if err := s.db.First(&user, userID).Error; err != nil {
			return
		}

		dailyLog = models.DailyLog{
			UserID:       userID,
			Date:         dateOnly,
			GoalCalories: user.DailyGoal,
		}
		s.db.Create(&dailyLog)
	}

	// Calculate totals for the day
	s.recalculateDailyTotals(&dailyLog)
}

// recalculateDailyTotals recalculates all totals for a daily log.
func (s *TrackingService) recalculateDailyTotals(log *models.DailyLog) error {
	type result struct {
		TotalCalories int
		TotalProtein  float64
		TotalCarbs    float64
		TotalFat      float64
	}

	var r result
	dateStart := log.Date
	dateEnd := dateStart.Add(24 * time.Hour)

	err := s.db.Model(&models.FoodEntry{}).
		Select(`
			COALESCE(SUM(foods.calories * food_entries.quantity), 0) as total_calories,
			COALESCE(SUM(foods.protein * food_entries.quantity), 0) as total_protein,
			COALESCE(SUM(foods.carbs * food_entries.quantity), 0) as total_carbs,
			COALESCE(SUM(foods.fat * food_entries.quantity), 0) as total_fat
		`).
		Joins("JOIN foods ON foods.id = food_entries.food_id").
		Where("food_entries.user_id = ? AND food_entries.logged_at >= ? AND food_entries.logged_at < ?",
			log.UserID, dateStart, dateEnd).
		Scan(&r).Error

	if err != nil {
		return err
	}

	log.TotalCalories = r.TotalCalories
	log.TotalProtein = r.TotalProtein
	log.TotalCarbs = r.TotalCarbs
	log.TotalFat = r.TotalFat

	return s.db.Save(log).Error
}

// CreateMeal creates a new meal.
func (s *TrackingService) CreateMeal(userID uint, mealType models.MealType, name, notes string) (*models.Meal, error) {
	meal := &models.Meal{
		UserID:   userID,
		Type:     mealType,
		Name:     name,
		Notes:    notes,
		LoggedAt: time.Now(),
	}

	if err := s.db.Create(meal).Error; err != nil {
		return nil, fmt.Errorf("failed to create meal: %w", err)
	}

	return meal, nil
}

// GetMealWithEntries retrieves a meal with its food entries.
func (s *TrackingService) GetMealWithEntries(mealID uint) (*models.Meal, error) {
	var meal models.Meal
	err := s.db.
		Preload("FoodEntries").
		Preload("FoodEntries.Food").
		First(&meal, mealID).Error

	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrMealNotFound
	}

	return &meal, err
}

// GetDailyLog retrieves the daily log for a user on a specific date.
func (s *TrackingService) GetDailyLog(userID uint, date time.Time) (*models.DailyLog, error) {
	dateOnly := time.Date(date.Year(), date.Month(), date.Day(), 0, 0, 0, 0, date.Location())

	var log models.DailyLog
	err := s.db.Where("user_id = ? AND date = ?", userID, dateOnly).First(&log).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}

	return &log, err
}

// GetWeeklyProgress returns daily logs for the past 7 days.
func (s *TrackingService) GetWeeklyProgress(userID uint) ([]models.DailyLog, error) {
	var logs []models.DailyLog
	endDate := time.Now()
	startDate := endDate.AddDate(0, 0, -7)

	err := s.db.
		Where("user_id = ? AND date >= ? AND date <= ?", userID, startDate, endDate).
		Order("date ASC").
		Find(&logs).Error

	return logs, err
}

// DeleteFoodEntry removes a food entry.
func (s *TrackingService) DeleteFoodEntry(entryID, userID uint) error {
	result := s.db.Where("id = ? AND user_id = ?", entryID, userID).Delete(&models.FoodEntry{})
	if result.RowsAffected == 0 {
		return ErrEntryNotFound
	}
	return result.Error
}

// GetTodaysSummary returns a summary of today's nutrition.
func (s *TrackingService) GetTodaysSummary(userID uint) (*DailySummary, error) {
	today := time.Now()
	log, err := s.GetDailyLog(userID, today)
	if err != nil {
		return nil, err
	}

	if log == nil {
		// No entries today
		return &DailySummary{Date: today}, nil
	}

	return &DailySummary{
		Date:          today,
		TotalCalories: log.TotalCalories,
		TotalProtein:  log.TotalProtein,
		TotalCarbs:    log.TotalCarbs,
		TotalFat:      log.TotalFat,
		GoalCalories:  log.GoalCalories,
		Remaining:     log.GoalCalories - log.TotalCalories,
		Progress:      log.GoalProgress(),
	}, nil
}

// DailySummary contains a summary of daily nutrition.
type DailySummary struct {
	Date          time.Time `json:"date"`
	TotalCalories int       `json:"total_calories"`
	TotalProtein  float64   `json:"total_protein"`
	TotalCarbs    float64   `json:"total_carbs"`
	TotalFat      float64   `json:"total_fat"`
	GoalCalories  int       `json:"goal_calories"`
	Remaining     int       `json:"remaining"`
	Progress      float64   `json:"progress"`
}

// BulkLogEntries logs multiple food entries in a transaction.
func (s *TrackingService) BulkLogEntries(entries []models.FoodEntry) error {
	return s.db.Transaction(func(tx *gorm.DB) error {
		for _, entry := range entries {
			if err := tx.Create(&entry).Error; err != nil {
				return err
			}
		}
		return nil
	})
}

// GetFoodEntriesForDate returns all food entries for a user on a specific date.
func (s *TrackingService) GetFoodEntriesForDate(userID uint, date time.Time) ([]models.FoodEntry, error) {
	var entries []models.FoodEntry
	dateStart := time.Date(date.Year(), date.Month(), date.Day(), 0, 0, 0, 0, date.Location())
	dateEnd := dateStart.Add(24 * time.Hour)

	err := s.db.
		Preload("Food").
		Preload("Meal").
		Where("user_id = ? AND logged_at >= ? AND logged_at < ?", userID, dateStart, dateEnd).
		Order("logged_at ASC").
		Find(&entries).Error

	return entries, err
}
