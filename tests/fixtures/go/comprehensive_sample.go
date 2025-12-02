// Package sample demonstrates all Go language features for testing TheAuditor extraction.
package sample

import (
	"context"
	"fmt"
	"sync"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Constants for testing
const (
	MaxRetries  = 3
	DefaultPort = "8080"
	apiVersion  = "v1"
)

// Package-level variables for race condition detection
var (
	GlobalCounter int
	SharedMap     = make(map[string]int)
	mu            sync.Mutex
)

// User represents a user entity with GORM tags
type User struct {
	gorm.Model
	Name     string `json:"name" gorm:"column:name;not null"`
	Email    string `json:"email" gorm:"uniqueIndex"`
	Password string `json:"-" gorm:"column:password"`
	Posts    []Post `gorm:"foreignKey:UserID"`
	Profile  *Profile
}

// Post represents a blog post
type Post struct {
	ID      uint   `gorm:"primaryKey"`
	Title   string `gorm:"column:title"`
	UserID  uint   `gorm:"index"`
	Author  *User  `gorm:"foreignKey:UserID"`
	Content string
}

// Profile is embedded in User
type Profile struct {
	Bio     string
	Website string
}

// Reader interface for testing interface extraction
type Reader interface {
	Read(p []byte) (n int, err error)
}

// Writer interface
type Writer interface {
	Write(p []byte) (n int, err error)
}

// ReadWriter combines Reader and Writer
type ReadWriter interface {
	Reader
	Writer
	Close() error
}

// Generic Stack type for Go 1.18+ generics testing
type Stack[T any] struct {
	items []T
}

// Push adds an item to the stack
func (s *Stack[T]) Push(item T) {
	s.items = append(s.items, item)
}

// Pop removes and returns the top item
func (s *Stack[T]) Pop() (T, bool) {
	if len(s.items) == 0 {
		var zero T
		return zero, false
	}
	item := s.items[len(s.items)-1]
	s.items = s.items[:len(s.items)-1]
	return item, true
}

// Map is a generic function for mapping slices
func Map[T any, U any](items []T, fn func(T) U) []U {
	result := make([]U, len(items))
	for i, item := range items {
		result[i] = fn(item)
	}
	return result
}

// Filter is a generic filter function
func Filter[T comparable](items []T, keep func(T) bool) []T {
	result := make([]T, 0)
	for _, item := range items {
		if keep(item) {
			result = append(result, item)
		}
	}
	return result
}

// ProcessItems demonstrates goroutine with captured loop variable (RACE!)
func ProcessItems(items []string) {
	for i, v := range items {
		// BUG: i and v are captured by the closure - data race!
		go func() {
			fmt.Printf("Processing item %d: %s\n", i, v)
			GlobalCounter++
		}()
	}
}

// ProcessItemsSafe demonstrates correct pattern with parameters
func ProcessItemsSafe(items []string) {
	for i, v := range items {
		// CORRECT: i and v passed as parameters
		go func(idx int, val string) {
			fmt.Printf("Processing item %d: %s\n", idx, val)
			mu.Lock()
			GlobalCounter++
			mu.Unlock()
		}(i, v)
	}
}

// FetchData demonstrates channel operations and defer
func FetchData(ctx context.Context, url string) ([]byte, error) {
	resultCh := make(chan []byte, 1)
	errCh := make(chan error, 1)

	go func() {
		defer close(resultCh)
		defer close(errCh)
		// Simulated fetch
		resultCh <- []byte("data")
	}()

	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case data := <-resultCh:
		return data, nil
	case err := <-errCh:
		return nil, err
	}
}

// GetUser demonstrates type assertion and error returns
func GetUser(db *gorm.DB, id uint) (*User, error) {
	var user User
	result := db.First(&user, id)
	if result.Error != nil {
		return nil, result.Error
	}
	return &user, nil
}

// HandleInterface demonstrates type switch
func HandleInterface(i interface{}) string {
	switch v := i.(type) {
	case string:
		return "string: " + v
	case int:
		return fmt.Sprintf("int: %d", v)
	case *User:
		return "user: " + v.Name
	default:
		return "unknown"
	}
}

// AssertReader demonstrates type assertion
func AssertReader(i interface{}) (Reader, bool) {
	r, ok := i.(Reader)
	return r, ok
}

// SetupRoutes demonstrates Gin route and middleware extraction
func SetupRoutes(r *gin.Engine) {
	// Global middleware
	r.Use(gin.Logger())
	r.Use(gin.Recovery())

	// API routes
	api := r.Group("/api/v1")
	{
		api.GET("/users", ListUsers)
		api.GET("/users/:id", GetUserHandler)
		api.POST("/users", CreateUser)
		api.PUT("/users/:id", UpdateUser)
		api.DELETE("/users/:id", DeleteUser)
	}
}

// ListUsers handler
func ListUsers(c *gin.Context) {
	c.JSON(200, gin.H{"users": []string{}})
}

// GetUserHandler handler
func GetUserHandler(c *gin.Context) {
	id := c.Param("id")
	c.JSON(200, gin.H{"id": id})
}

// CreateUser handler
func CreateUser(c *gin.Context) {
	c.JSON(201, gin.H{"status": "created"})
}

// UpdateUser handler
func UpdateUser(c *gin.Context) {
	c.JSON(200, gin.H{"status": "updated"})
}

// DeleteUser handler
func DeleteUser(c *gin.Context) {
	c.JSON(200, gin.H{"status": "deleted"})
}

// CloseResource demonstrates defer with error handling
func CloseResource(r Reader) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic: %v", r)
		}
	}()
	// Some operation
	return nil
}

// WorkerPool demonstrates multiple goroutines with channels
func WorkerPool(jobs <-chan int, results chan<- int) {
	for j := range jobs {
		// Process job
		results <- j * 2
	}
}
