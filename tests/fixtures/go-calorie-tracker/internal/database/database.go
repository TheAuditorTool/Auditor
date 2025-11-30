package database

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/example/calorie-tracker/internal/models"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

// Config holds database configuration.
type Config struct {
	Path        string
	Debug       bool
	MaxIdleConn int
	MaxOpenConn int
}

// DefaultConfig returns the default database configuration.
func DefaultConfig() Config {
	path := os.Getenv("DATABASE_PATH")
	if path == "" {
		path = "calorie_tracker.db"
	}

	return Config{
		Path:        path,
		Debug:       os.Getenv("DEBUG") == "true",
		MaxIdleConn: 10,
		MaxOpenConn: 100,
	}
}

// Connect initializes the database connection.
func Connect(cfg Config) error {
	var logLevel logger.LogLevel
	if cfg.Debug {
		logLevel = logger.Info
	} else {
		logLevel = logger.Silent
	}

	gormLogger := logger.New(
		log.New(os.Stdout, "\r\n", log.LstdFlags),
		logger.Config{
			SlowThreshold:             time.Second,
			LogLevel:                  logLevel,
			IgnoreRecordNotFoundError: true,
			Colorful:                  true,
		},
	)

	var err error
	DB, err = gorm.Open(sqlite.Open(cfg.Path), &gorm.Config{
		Logger: gormLogger,
	})

	if err != nil {
		return fmt.Errorf("failed to connect to database: %w", err)
	}

	sqlDB, err := DB.DB()
	if err != nil {
		return fmt.Errorf("failed to get sql.DB: %w", err)
	}

	sqlDB.SetMaxIdleConns(cfg.MaxIdleConn)
	sqlDB.SetMaxOpenConns(cfg.MaxOpenConn)
	sqlDB.SetConnMaxLifetime(time.Hour)

	return nil
}

// Migrate runs database migrations.
func Migrate() error {
	return DB.AutoMigrate(
		&models.User{},
		&models.Food{},
		&models.FoodEntry{},
		&models.Meal{},
		&models.DailyLog{},
	)
}

// Close closes the database connection.
func Close() error {
	sqlDB, err := DB.DB()
	if err != nil {
		return err
	}
	return sqlDB.Close()
}

// Transaction wraps a function in a database transaction.
func Transaction(fn func(tx *gorm.DB) error) error {
	return DB.Transaction(fn)
}
