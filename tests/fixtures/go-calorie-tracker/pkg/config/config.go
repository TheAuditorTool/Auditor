package config

import (
	"os"
	"strconv"
)

// Config holds application configuration.
type Config struct {
	Server   ServerConfig
	Database DatabaseConfig
	Auth     AuthConfig
}

// ServerConfig holds server configuration.
type ServerConfig struct {
	Port         string
	ReadTimeout  int
	WriteTimeout int
	Debug        bool
}

// DatabaseConfig holds database configuration.
type DatabaseConfig struct {
	Path        string
	MaxIdleConn int
	MaxOpenConn int
}

// AuthConfig holds authentication configuration.
type AuthConfig struct {
	JWTSecret     string
	TokenDuration int // hours
}

// Load loads configuration from environment variables.
func Load() *Config {
	return &Config{
		Server: ServerConfig{
			Port:         getEnv("PORT", "8080"),
			ReadTimeout:  getEnvInt("READ_TIMEOUT", 15),
			WriteTimeout: getEnvInt("WRITE_TIMEOUT", 15),
			Debug:        getEnvBool("DEBUG", false),
		},
		Database: DatabaseConfig{
			Path:        getEnv("DATABASE_PATH", "calorie_tracker.db"),
			MaxIdleConn: getEnvInt("DB_MAX_IDLE_CONN", 10),
			MaxOpenConn: getEnvInt("DB_MAX_OPEN_CONN", 100),
		},
		Auth: AuthConfig{
			JWTSecret:     getEnv("JWT_SECRET", "change-this-in-production"),
			TokenDuration: getEnvInt("TOKEN_DURATION_HOURS", 24),
		},
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}
