package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/example/calorie-tracker/internal/database"
	"github.com/example/calorie-tracker/internal/handlers"
	"github.com/example/calorie-tracker/internal/middleware"
	"github.com/example/calorie-tracker/internal/repository"
	"github.com/example/calorie-tracker/internal/services"
	"github.com/gin-gonic/gin"
)

func main() {
	// Initialize database
	cfg := database.DefaultConfig()
	if err := database.Connect(cfg); err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer database.Close()

	// Run migrations
	if err := database.Migrate(); err != nil {
		log.Fatalf("Failed to run migrations: %v", err)
	}

	// Initialize repositories
	userRepo := repository.NewUserRepository()
	foodRepo := repository.NewFoodRepository()

	// Initialize services
	authService := services.NewAuthService(userRepo)
	trackingService := services.NewTrackingService()

	// Initialize handlers
	authHandler := handlers.NewAuthHandler(authService)
	foodHandler := handlers.NewFoodHandler(foodRepo)
	trackingHandler := handlers.NewTrackingHandler(trackingService)

	// Setup router
	router := setupRouter(authService, authHandler, foodHandler, trackingHandler)

	// Start server with graceful shutdown
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in goroutine
	go func() {
		log.Printf("Starting server on port %s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Give outstanding requests time to complete
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server exited")
}

func setupRouter(
	authService *services.AuthService,
	authHandler *handlers.AuthHandler,
	foodHandler *handlers.FoodHandler,
	trackingHandler *handlers.TrackingHandler,
) *gin.Engine {
	router := gin.New()

	// Global middleware
	router.Use(gin.Recovery())
	router.Use(middleware.RequestLogger())
	router.Use(middleware.RequestID())

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"version": "1.0.0",
		})
	})

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Auth routes (public)
		auth := v1.Group("/auth")
		{
			auth.POST("/register", authHandler.Register)
			auth.POST("/login", authHandler.Login)
			auth.POST("/forgot-password", authHandler.ForgotPassword)
		}

		// Auth routes (protected)
		authProtected := v1.Group("/auth")
		authProtected.Use(middleware.AuthMiddleware(authService))
		{
			authProtected.POST("/refresh", authHandler.RefreshToken)
			authProtected.POST("/change-password", authHandler.ChangePassword)
		}

		// Food routes (public read, protected write)
		foods := v1.Group("/foods")
		{
			foods.GET("/:id", foodHandler.Get)
			foods.GET("/search", foodHandler.Search)
			foods.GET("/barcode/:barcode", foodHandler.GetByBarcode)
			foods.GET("/popular", foodHandler.GetPopular)
		}

		foodsProtected := v1.Group("/foods")
		foodsProtected.Use(middleware.AuthMiddleware(authService))
		{
			foodsProtected.POST("", foodHandler.Create)
			foodsProtected.PUT("/:id", foodHandler.Update)
			foodsProtected.DELETE("/:id", foodHandler.Delete)
		}

		// Tracking routes (all protected)
		tracking := v1.Group("/tracking")
		tracking.Use(middleware.AuthMiddleware(authService))
		{
			// Entries
			tracking.POST("/entries", trackingHandler.LogEntry)
			tracking.GET("/entries", trackingHandler.GetEntriesForDate)
			tracking.DELETE("/entries/:id", trackingHandler.DeleteEntry)

			// Meals
			tracking.POST("/meals", trackingHandler.CreateMeal)
			tracking.GET("/meals/:id", trackingHandler.GetMeal)

			// Summaries
			tracking.GET("/today", trackingHandler.GetTodaySummary)
			tracking.GET("/daily", trackingHandler.GetDailyLog)
			tracking.GET("/weekly", trackingHandler.GetWeeklyProgress)
		}
	}

	return router
}
