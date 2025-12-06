package services

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/example/calorie-tracker/internal/database"
	"github.com/example/calorie-tracker/internal/models"
	"github.com/example/calorie-tracker/internal/repository"
)

// JobsService handles background processing.
type JobsService struct {
	userRepo *repository.UserRepository
	wg       sync.WaitGroup
	stopChan chan struct{}
}

// NewJobsService creates a new JobsService.
func NewJobsService(userRepo *repository.UserRepository) *JobsService {
	return &JobsService{
		userRepo: userRepo,
		stopChan: make(chan struct{}),
	}
}

// Start starts all background jobs.
func (s *JobsService) Start(ctx context.Context) {
	log.Println("Starting background jobs...")

	s.wg.Add(3)

	go s.dailySummaryJob(ctx)
	go s.cleanupJob(ctx)
	go s.notificationJob(ctx)
}

// Stop stops all background jobs and waits for them to complete.
func (s *JobsService) Stop() {
	log.Println("Stopping background jobs...")
	close(s.stopChan)
	s.wg.Wait()
	log.Println("All background jobs stopped")
}

// dailySummaryJob generates daily summaries for all users.
func (s *JobsService) dailySummaryJob(ctx context.Context) {
	defer s.wg.Done()

	ticker := time.NewTicker(24 * time.Hour)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-s.stopChan:
			return
		case <-ticker.C:
			s.generateDailySummaries()
		}
	}
}

// generateDailySummaries generates summaries for all active users.
func (s *JobsService) generateDailySummaries() {
	users, err := s.userRepo.GetActiveUsers()
	if err != nil {
		log.Printf("Failed to get active users: %v", err)
		return
	}

	// VULNERABILITY: Race condition - processing users concurrently without proper sync
	// Each goroutine accesses shared database connection
	for _, user := range users {
		go func(u models.User) {
			// VULNERABILITY: Captured loop variable (pre-Go 1.22 pattern)
			// In Go 1.22+, this is fixed, but older versions have race condition
			if err := s.generateUserSummary(u.ID); err != nil {
				log.Printf("Failed to generate summary for user %d: %v", u.ID, err)
			}
		}(user) // Passing user as parameter is the safe pattern
	}
}

// generateUserSummary generates a daily summary for a user.
func (s *JobsService) generateUserSummary(userID uint) error {
	yesterday := time.Now().AddDate(0, 0, -1)
	dateOnly := time.Date(yesterday.Year(), yesterday.Month(), yesterday.Day(), 0, 0, 0, 0, yesterday.Location())

	var log models.DailyLog
	err := database.DB.Where("user_id = ? AND date = ?", userID, dateOnly).First(&log).Error
	if err != nil {
		return fmt.Errorf("no data found for user %d on %s", userID, dateOnly.Format("2006-01-02"))
	}

	// Generate summary report
	summary := fmt.Sprintf(
		"Daily Summary for %s:\n"+
			"Calories: %d / %d (%.1f%%)\n"+
			"Protein: %.1fg\n"+
			"Carbs: %.1fg\n"+
			"Fat: %.1fg",
		dateOnly.Format("Jan 2, 2006"),
		log.TotalCalories,
		log.GoalCalories,
		log.GoalProgress(),
		log.TotalProtein,
		log.TotalCarbs,
		log.TotalFat,
	)

	// In a real app, this would send an email or push notification
	fmt.Println(summary)

	return nil
}

// cleanupJob removes old data.
func (s *JobsService) cleanupJob(ctx context.Context) {
	defer s.wg.Done()

	ticker := time.NewTicker(7 * 24 * time.Hour) // Weekly
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-s.stopChan:
			return
		case <-ticker.C:
			s.cleanupOldData()
		}
	}
}

// cleanupOldData removes data older than retention period.
func (s *JobsService) cleanupOldData() {
	retentionDays := 365 // Keep data for 1 year
	cutoff := time.Now().AddDate(0, 0, -retentionDays)

	// Delete old food entries
	result := database.DB.Where("logged_at < ?", cutoff).Delete(&models.FoodEntry{})
	if result.Error != nil {
		log.Printf("Failed to cleanup old food entries: %v", result.Error)
	} else {
		log.Printf("Cleaned up %d old food entries", result.RowsAffected)
	}

	// Delete old daily logs
	result = database.DB.Where("date < ?", cutoff).Delete(&models.DailyLog{})
	if result.Error != nil {
		log.Printf("Failed to cleanup old daily logs: %v", result.Error)
	} else {
		log.Printf("Cleaned up %d old daily logs", result.RowsAffected)
	}
}

// notificationJob sends notifications to users.
func (s *JobsService) notificationJob(ctx context.Context) {
	defer s.wg.Done()

	ticker := time.NewTicker(1 * time.Hour)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-s.stopChan:
			return
		case <-ticker.C:
			s.sendReminders()
		}
	}
}

// sendReminders sends meal reminders to users.
func (s *JobsService) sendReminders() {
	now := time.Now()
	hour := now.Hour()

	var mealType string
	switch {
	case hour >= 7 && hour < 10:
		mealType = "breakfast"
	case hour >= 11 && hour < 14:
		mealType = "lunch"
	case hour >= 17 && hour < 20:
		mealType = "dinner"
	default:
		return // No reminders outside meal times
	}

	users, err := s.userRepo.GetActiveUsers()
	if err != nil {
		log.Printf("Failed to get active users for reminders: %v", err)
		return
	}

	// Check which users haven't logged this meal today
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())

	for _, user := range users {
		var count int64
		database.DB.Model(&models.Meal{}).
			Where("user_id = ? AND type = ? AND logged_at >= ?", user.ID, mealType, today).
			Count(&count)

		if count == 0 {
			// Send reminder (in a real app, this would be a push notification)
			log.Printf("Reminder: User %s hasn't logged %s yet", user.Name, mealType)
		}
	}
}

// ProcessBatchEntries processes a batch of food entries asynchronously.
// This demonstrates proper goroutine usage with sync.WaitGroup.
func (s *JobsService) ProcessBatchEntries(entries []models.FoodEntry) error {
	var wg sync.WaitGroup
	errChan := make(chan error, len(entries))

	for i := range entries {
		wg.Add(1)
		go func(entry models.FoodEntry) {
			defer wg.Done()
			if err := database.DB.Create(&entry).Error; err != nil {
				errChan <- fmt.Errorf("failed to create entry: %w", err)
			}
		}(entries[i]) // Safe: passing by value
	}

	wg.Wait()
	close(errChan)

	// Collect any errors
	var errs []error
	for err := range errChan {
		errs = append(errs, err)
	}

	if len(errs) > 0 {
		return fmt.Errorf("batch processing had %d errors", len(errs))
	}

	return nil
}
