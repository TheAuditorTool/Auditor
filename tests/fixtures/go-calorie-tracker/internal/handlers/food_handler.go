package handlers

import (
	"net/http"
	"strconv"

	"github.com/example/calorie-tracker/internal/models"
	"github.com/example/calorie-tracker/internal/repository"
	"github.com/gin-gonic/gin"
)

// FoodHandler handles food-related endpoints.
type FoodHandler struct {
	foodRepo *repository.FoodRepository
}

// NewFoodHandler creates a new FoodHandler.
func NewFoodHandler(foodRepo *repository.FoodRepository) *FoodHandler {
	return &FoodHandler{foodRepo: foodRepo}
}

// CreateFoodRequest contains food creation data.
type CreateFoodRequest struct {
	Name        string  `json:"name" binding:"required"`
	Brand       string  `json:"brand"`
	Barcode     string  `json:"barcode"`
	ServingSize float64 `json:"serving_size" binding:"required,gt=0"`
	ServingUnit string  `json:"serving_unit" binding:"required"`
	Calories    int     `json:"calories" binding:"required,gte=0"`
	Protein     float64 `json:"protein" binding:"gte=0"`
	Carbs       float64 `json:"carbs" binding:"gte=0"`
	Fat         float64 `json:"fat" binding:"gte=0"`
	Fiber       float64 `json:"fiber" binding:"gte=0"`
	Sugar       float64 `json:"sugar" binding:"gte=0"`
	Sodium      float64 `json:"sodium" binding:"gte=0"`
}

// Create creates a new food item.
// @Summary Create a new food item
// @Tags foods
// @Security Bearer
// @Accept json
// @Produce json
// @Param request body CreateFoodRequest true "Food data"
// @Success 201 {object} models.Food
// @Failure 400 {object} map[string]string
// @Router /foods [post]
func (h *FoodHandler) Create(c *gin.Context) {
	var req CreateFoodRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	userID, _ := c.Get("user_id")
	userIDPtr := userID.(uint)

	food := &models.Food{
		Name:        req.Name,
		Brand:       req.Brand,
		Barcode:     req.Barcode,
		ServingSize: req.ServingSize,
		ServingUnit: req.ServingUnit,
		Calories:    req.Calories,
		Protein:     req.Protein,
		Carbs:       req.Carbs,
		Fat:         req.Fat,
		Fiber:       req.Fiber,
		Sugar:       req.Sugar,
		Sodium:      req.Sodium,
		CreatedBy:   &userIDPtr,
	}

	if err := h.foodRepo.Create(food); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create food"})
		return
	}

	c.JSON(http.StatusCreated, food)
}

// Get retrieves a food item by ID.
// @Summary Get food item by ID
// @Tags foods
// @Produce json
// @Param id path int true "Food ID"
// @Success 200 {object} models.Food
// @Failure 404 {object} map[string]string
// @Router /foods/{id} [get]
func (h *FoodHandler) Get(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid food ID"})
		return
	}

	food, err := h.foodRepo.GetByID(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Food not found"})
		return
	}

	c.JSON(http.StatusOK, food)
}

// Search searches for foods by query.
// @Summary Search foods
// @Tags foods
// @Produce json
// @Param q query string true "Search query"
// @Param limit query int false "Result limit" default(20)
// @Param safe query bool false "Use safe search" default(true)
// @Success 200 {array} models.Food
// @Router /foods/search [get]
func (h *FoodHandler) Search(c *gin.Context) {
	query := c.Query("q")
	if query == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Search query is required"})
		return
	}

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	useSafe := c.DefaultQuery("safe", "true") == "true"

	var foods []models.Food
	var err error

	if useSafe {
		// Use safe parameterized query
		foods, err = h.foodRepo.SearchSafe(query, limit)
	} else {
		// VULNERABILITY: This path uses SQL injection vulnerable search
		// Intentionally included for security rule testing
		foods, err = h.foodRepo.Search(query, limit)
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Search failed"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"results": foods,
		"count":   len(foods),
	})
}

// GetByBarcode retrieves a food item by barcode.
// @Summary Get food by barcode
// @Tags foods
// @Produce json
// @Param barcode path string true "Barcode"
// @Success 200 {object} models.Food
// @Failure 404 {object} map[string]string
// @Router /foods/barcode/{barcode} [get]
func (h *FoodHandler) GetByBarcode(c *gin.Context) {
	barcode := c.Param("barcode")

	food, err := h.foodRepo.GetByBarcode(barcode)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Food not found"})
		return
	}

	c.JSON(http.StatusOK, food)
}

// GetPopular returns popular food items.
// @Summary Get popular foods
// @Tags foods
// @Produce json
// @Param limit query int false "Result limit" default(10)
// @Success 200 {array} models.Food
// @Router /foods/popular [get]
func (h *FoodHandler) GetPopular(c *gin.Context) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "10"))
	if limit <= 0 || limit > 50 {
		limit = 10
	}

	foods, err := h.foodRepo.GetPopular(limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get popular foods"})
		return
	}

	c.JSON(http.StatusOK, foods)
}

// Update updates a food item.
// @Summary Update food item
// @Tags foods
// @Security Bearer
// @Accept json
// @Produce json
// @Param id path int true "Food ID"
// @Param request body CreateFoodRequest true "Food data"
// @Success 200 {object} models.Food
// @Failure 404 {object} map[string]string
// @Router /foods/{id} [put]
func (h *FoodHandler) Update(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid food ID"})
		return
	}

	food, err := h.foodRepo.GetByID(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Food not found"})
		return
	}

	var req CreateFoodRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	food.Name = req.Name
	food.Brand = req.Brand
	food.Barcode = req.Barcode
	food.ServingSize = req.ServingSize
	food.ServingUnit = req.ServingUnit
	food.Calories = req.Calories
	food.Protein = req.Protein
	food.Carbs = req.Carbs
	food.Fat = req.Fat
	food.Fiber = req.Fiber
	food.Sugar = req.Sugar
	food.Sodium = req.Sodium

	if err := h.foodRepo.Update(food); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update food"})
		return
	}

	c.JSON(http.StatusOK, food)
}

// Delete removes a food item.
// @Summary Delete food item
// @Tags foods
// @Security Bearer
// @Param id path int true "Food ID"
// @Success 204
// @Failure 404 {object} map[string]string
// @Router /foods/{id} [delete]
func (h *FoodHandler) Delete(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid food ID"})
		return
	}

	if err := h.foodRepo.Delete(uint(id)); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Food not found"})
		return
	}

	c.Status(http.StatusNoContent)
}
