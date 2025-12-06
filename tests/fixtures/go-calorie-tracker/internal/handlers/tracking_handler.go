package handlers

import (
	"net/http"
	"strconv"
	"time"

	"github.com/example/calorie-tracker/internal/models"
	"github.com/example/calorie-tracker/internal/services"
	"github.com/gin-gonic/gin"
)

// TrackingHandler handles food tracking endpoints.
type TrackingHandler struct {
	trackingService *services.TrackingService
}

// NewTrackingHandler creates a new TrackingHandler.
func NewTrackingHandler(trackingService *services.TrackingService) *TrackingHandler {
	return &TrackingHandler{trackingService: trackingService}
}

// LogEntryRequest contains food entry data.
type LogEntryRequest struct {
	FoodID   uint    `json:"food_id" binding:"required"`
	Quantity float64 `json:"quantity" binding:"required,gt=0"`
	MealID   *uint   `json:"meal_id"`
	Notes    string  `json:"notes"`
}

// LogEntry logs a food entry.
// @Summary Log a food entry
// @Tags tracking
// @Security Bearer
// @Accept json
// @Produce json
// @Param request body LogEntryRequest true "Entry data"
// @Success 201 {object} models.FoodEntry
// @Failure 400 {object} map[string]string
// @Router /tracking/entries [post]
func (h *TrackingHandler) LogEntry(c *gin.Context) {
	userID, _ := c.Get("user_id")

	var req LogEntryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	entry, err := h.trackingService.LogFoodEntry(
		userID.(uint),
		req.FoodID,
		req.Quantity,
		req.MealID,
		req.Notes,
	)

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, entry)
}

// DeleteEntry deletes a food entry.
// @Summary Delete a food entry
// @Tags tracking
// @Security Bearer
// @Param id path int true "Entry ID"
// @Success 204
// @Failure 404 {object} map[string]string
// @Router /tracking/entries/{id} [delete]
func (h *TrackingHandler) DeleteEntry(c *gin.Context) {
	userID, _ := c.Get("user_id")

	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid entry ID"})
		return
	}

	if err := h.trackingService.DeleteFoodEntry(uint(id), userID.(uint)); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Entry not found"})
		return
	}

	c.Status(http.StatusNoContent)
}

// CreateMealRequest contains meal creation data.
type CreateMealRequest struct {
	Type  models.MealType `json:"type" binding:"required,oneof=breakfast lunch dinner snack"`
	Name  string          `json:"name"`
	Notes string          `json:"notes"`
}

// CreateMeal creates a new meal.
// @Summary Create a meal
// @Tags tracking
// @Security Bearer
// @Accept json
// @Produce json
// @Param request body CreateMealRequest true "Meal data"
// @Success 201 {object} models.Meal
// @Failure 400 {object} map[string]string
// @Router /tracking/meals [post]
func (h *TrackingHandler) CreateMeal(c *gin.Context) {
	userID, _ := c.Get("user_id")

	var req CreateMealRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	meal, err := h.trackingService.CreateMeal(userID.(uint), req.Type, req.Name, req.Notes)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, meal)
}

// GetMeal retrieves a meal with its entries.
// @Summary Get meal details
// @Tags tracking
// @Security Bearer
// @Param id path int true "Meal ID"
// @Success 200 {object} models.Meal
// @Failure 404 {object} map[string]string
// @Router /tracking/meals/{id} [get]
func (h *TrackingHandler) GetMeal(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid meal ID"})
		return
	}

	meal, err := h.trackingService.GetMealWithEntries(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Meal not found"})
		return
	}

	c.JSON(http.StatusOK, meal)
}

// GetTodaySummary returns today's nutrition summary.
// @Summary Get today's summary
// @Tags tracking
// @Security Bearer
// @Success 200 {object} services.DailySummary
// @Router /tracking/today [get]
func (h *TrackingHandler) GetTodaySummary(c *gin.Context) {
	userID, _ := c.Get("user_id")

	summary, err := h.trackingService.GetTodaysSummary(userID.(uint))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, summary)
}

// GetDailyLog returns the daily log for a specific date.
// @Summary Get daily log
// @Tags tracking
// @Security Bearer
// @Param date query string true "Date (YYYY-MM-DD)"
// @Success 200 {object} models.DailyLog
// @Failure 400 {object} map[string]string
// @Router /tracking/daily [get]
func (h *TrackingHandler) GetDailyLog(c *gin.Context) {
	userID, _ := c.Get("user_id")

	dateStr := c.Query("date")
	date, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid date format. Use YYYY-MM-DD"})
		return
	}

	log, err := h.trackingService.GetDailyLog(userID.(uint), date)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if log == nil {
		c.JSON(http.StatusOK, gin.H{"message": "No data for this date"})
		return
	}

	c.JSON(http.StatusOK, log)
}

// GetWeeklyProgress returns the weekly progress.
// @Summary Get weekly progress
// @Tags tracking
// @Security Bearer
// @Success 200 {array} models.DailyLog
// @Router /tracking/weekly [get]
func (h *TrackingHandler) GetWeeklyProgress(c *gin.Context) {
	userID, _ := c.Get("user_id")

	logs, err := h.trackingService.GetWeeklyProgress(userID.(uint))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Calculate weekly totals
	var totalCalories int
	var totalProtein, totalCarbs, totalFat float64
	for _, log := range logs {
		totalCalories += log.TotalCalories
		totalProtein += log.TotalProtein
		totalCarbs += log.TotalCarbs
		totalFat += log.TotalFat
	}

	c.JSON(http.StatusOK, gin.H{
		"days": logs,
		"totals": gin.H{
			"calories": totalCalories,
			"protein":  totalProtein,
			"carbs":    totalCarbs,
			"fat":      totalFat,
		},
		"averages": gin.H{
			"calories": totalCalories / max(len(logs), 1),
			"protein":  totalProtein / float64(max(len(logs), 1)),
			"carbs":    totalCarbs / float64(max(len(logs), 1)),
			"fat":      totalFat / float64(max(len(logs), 1)),
		},
	})
}

// GetEntriesForDate returns all entries for a specific date.
// @Summary Get entries for date
// @Tags tracking
// @Security Bearer
// @Param date query string true "Date (YYYY-MM-DD)"
// @Success 200 {array} models.FoodEntry
// @Failure 400 {object} map[string]string
// @Router /tracking/entries [get]
func (h *TrackingHandler) GetEntriesForDate(c *gin.Context) {
	userID, _ := c.Get("user_id")

	dateStr := c.DefaultQuery("date", time.Now().Format("2006-01-02"))
	date, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid date format. Use YYYY-MM-DD"})
		return
	}

	entries, err := h.trackingService.GetFoodEntriesForDate(userID.(uint), date)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"date":    dateStr,
		"entries": entries,
		"count":   len(entries),
	})
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
