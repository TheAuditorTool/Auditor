// Package main demonstrates Gin framework patterns for testing framework detection.
package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// User represents a user in the system
type User struct {
	ID    uint   `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

func main() {
	r := gin.Default()

	// Global middleware
	r.Use(gin.Logger())
	r.Use(gin.Recovery())
	r.Use(AuthMiddleware())

	// Health check
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	// API routes
	api := r.Group("/api")
	api.Use(RateLimitMiddleware())
	{
		// User routes
		api.GET("/users", ListUsers)
		api.GET("/users/:id", GetUser)
		api.POST("/users", CreateUser)
		api.PUT("/users/:id", UpdateUser)
		api.DELETE("/users/:id", DeleteUser)

		// Protected admin routes
		admin := api.Group("/admin")
		admin.Use(AdminOnlyMiddleware())
		{
			admin.GET("/stats", GetStats)
			admin.POST("/config", UpdateConfig)
		}
	}

	r.Run(":8080")
}

// AuthMiddleware checks for valid authentication
func AuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		token := c.GetHeader("Authorization")
		if token == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
			return
		}
		c.Next()
	}
}

// RateLimitMiddleware limits request rate
func RateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Rate limiting logic
		c.Next()
	}
}

// AdminOnlyMiddleware restricts to admin users
func AdminOnlyMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Admin check logic
		c.Next()
	}
}

// ListUsers returns all users
func ListUsers(c *gin.Context) {
	users := []User{
		{ID: 1, Name: "Alice", Email: "alice@example.com"},
		{ID: 2, Name: "Bob", Email: "bob@example.com"},
	}
	c.JSON(http.StatusOK, users)
}

// GetUser returns a single user
func GetUser(c *gin.Context) {
	id := c.Param("id")
	c.JSON(http.StatusOK, gin.H{"id": id})
}

// CreateUser creates a new user
func CreateUser(c *gin.Context) {
	var user User
	if err := c.ShouldBindJSON(&user); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, user)
}

// UpdateUser updates an existing user
func UpdateUser(c *gin.Context) {
	id := c.Param("id")
	var user User
	if err := c.ShouldBindJSON(&user); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	user.ID = 1 // Would parse id
	_ = id
	c.JSON(http.StatusOK, user)
}

// DeleteUser deletes a user
func DeleteUser(c *gin.Context) {
	id := c.Param("id")
	_ = id
	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

// GetStats returns admin stats
func GetStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"users": 100, "requests": 1000})
}

// UpdateConfig updates system configuration
func UpdateConfig(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "updated"})
}
