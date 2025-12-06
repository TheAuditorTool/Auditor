// Package main provides the task queue server entry point.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/example/task-queue/internal/api"
	"github.com/example/task-queue/internal/queue"
	"github.com/example/task-queue/internal/storage"
	"github.com/example/task-queue/internal/task"
	"github.com/example/task-queue/internal/worker"
)

// Config holds server configuration
type Config struct {
	Port            int
	NumWorkers      int
	QueueSize       int
	TaskTimeout     time.Duration
	ShutdownTimeout time.Duration
	DBPath          string
	LogLevel        string
}

// DefaultConfig returns default configuration
func DefaultConfig() Config {
	return Config{
		Port:            8080,
		NumWorkers:      4,
		QueueSize:       10000,
		TaskTimeout:     30 * time.Second,
		ShutdownTimeout: 30 * time.Second,
		DBPath:          "tasks.db",
		LogLevel:        "info",
	}
}

// ParseFlags parses command line flags
func ParseFlags() Config {
	cfg := DefaultConfig()

	flag.IntVar(&cfg.Port, "port", cfg.Port, "Server port")
	flag.IntVar(&cfg.NumWorkers, "workers", cfg.NumWorkers, "Number of workers")
	flag.IntVar(&cfg.QueueSize, "queue-size", cfg.QueueSize, "Maximum queue size")
	flag.DurationVar(&cfg.TaskTimeout, "task-timeout", cfg.TaskTimeout, "Task execution timeout")
	flag.DurationVar(&cfg.ShutdownTimeout, "shutdown-timeout", cfg.ShutdownTimeout, "Graceful shutdown timeout")
	flag.StringVar(&cfg.DBPath, "db", cfg.DBPath, "Database path")
	flag.StringVar(&cfg.LogLevel, "log-level", cfg.LogLevel, "Log level (debug, info, warn, error)")

	flag.Parse()

	return cfg
}

func main() {
	cfg := ParseFlags()

	logger := log.New(os.Stdout, "[taskqueue] ", log.LstdFlags|log.Lshortfile)
	logger.Printf("Starting task queue server with config: %+v", cfg)

	// Initialize storage
	store, err := storage.NewSQLiteStorage(storage.SQLiteConfig{
		Path:            cfg.DBPath,
		MaxOpenConns:    10,
		MaxIdleConns:    5,
		ConnMaxLifetime: time.Hour,
	})
	if err != nil {
		logger.Fatalf("Failed to initialize storage: %v", err)
	}
	defer store.Close()

	// Initialize queue
	q := queue.NewMemoryQueue(
		queue.WithMaxSize(cfg.QueueSize),
		queue.WithEnqueueCallback(func(t *queue.Task) {
			logger.Printf("Task enqueued: %s (type=%s)", t.ID, t.Type)
		}),
		queue.WithDequeueCallback(func(t *queue.Task) {
			logger.Printf("Task dequeued: %s (type=%s)", t.ID, t.Type)
		}),
	)
	defer q.Close()

	// Initialize task registry and register handlers
	registry := task.NewRegistry()
	registerTaskHandlers(registry, logger)

	// Initialize worker pool
	pool := worker.NewPool(
		q,
		registry,
		worker.PoolConfig{
			NumWorkers:      cfg.NumWorkers,
			MaxQueueSize:    cfg.QueueSize,
			TaskTimeout:     cfg.TaskTimeout,
			ShutdownTimeout: cfg.ShutdownTimeout,
			RetryDelay:      time.Second,
			MaxRetries:      3,
		},
		worker.WithTaskCompleteCallback(func(r *worker.Result) {
			logger.Printf("Task completed: %s (duration=%v)", r.Task.ID, r.Duration)
		}),
		worker.WithTaskFailCallback(func(t *queue.Task, err error) {
			logger.Printf("Task failed: %s (error=%v)", t.ID, err)
		}),
		worker.WithPanicHandler(func(id int, recovered interface{}) {
			logger.Printf("Worker %d panicked: %v", id, recovered)
		}),
	)

	// Start worker pool
	if err := pool.Start(); err != nil {
		logger.Fatalf("Failed to start worker pool: %v", err)
	}
	defer pool.Stop()

	// Initialize API handler
	handler := api.NewHandler(q, pool, store)

	// Set up middleware
	rateLimiter := api.NewRateLimiter(100, time.Minute)
	metrics := api.NewMetrics()

	mux := api.Chain(
		handler.Router(),
		api.RequestID(),
		api.Logger(logger),
		api.Recover(logger),
		api.Timeout(30*time.Second),
		rateLimiter.Middleware(),
		metrics.Middleware(),
		api.SecureHeaders(),
		api.MaxBodySize(10<<20), // 10MB
		api.CORS([]string{"*"}),
	)

	// Create server
	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in goroutine
	go func() {
		logger.Printf("Server listening on port %d", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Println("Shutting down server...")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		logger.Printf("Server shutdown error: %v", err)
	}

	logger.Println("Server stopped")
}

// registerTaskHandlers registers all task handlers
func registerTaskHandlers(registry *task.Registry, logger *log.Logger) {
	// Email task handler
	task.RegisterFunc(registry, "email", 30*time.Second,
		func(ctx context.Context, payload EmailPayload) (EmailResult, error) {
			logger.Printf("Sending email to %s", payload.To)
			// Simulate email sending
			time.Sleep(100 * time.Millisecond)
			return EmailResult{
				Sent:   true,
				SentAt: time.Now(),
			}, nil
		})

	// Data processing task handler
	task.RegisterFunc(registry, "process_data", 60*time.Second,
		func(ctx context.Context, payload DataPayload) (DataResult, error) {
			logger.Printf("Processing data: %s", payload.Source)
			// Simulate processing
			time.Sleep(200 * time.Millisecond)
			return DataResult{
				Processed: payload.Count,
				Duration:  200 * time.Millisecond,
			}, nil
		})

	// Report generation task handler
	task.RegisterFunc(registry, "generate_report", 120*time.Second,
		func(ctx context.Context, payload ReportPayload) (ReportResult, error) {
			logger.Printf("Generating report: %s", payload.ReportType)
			// Simulate report generation
			time.Sleep(500 * time.Millisecond)
			return ReportResult{
				ReportID: "rpt_" + payload.ReportType,
				URL:      fmt.Sprintf("/reports/%s", payload.ReportType),
			}, nil
		})

	// Notification task handler
	task.RegisterFunc(registry, "notification", 10*time.Second,
		func(ctx context.Context, payload NotificationPayload) (NotificationResult, error) {
			logger.Printf("Sending notification to user %s", payload.UserID)
			time.Sleep(50 * time.Millisecond)
			return NotificationResult{
				Delivered: true,
				Channel:   payload.Channel,
			}, nil
		})

	// Cleanup task handler
	task.RegisterFunc(registry, "cleanup", 300*time.Second,
		func(ctx context.Context, payload CleanupPayload) (CleanupResult, error) {
			logger.Printf("Running cleanup for %s", payload.Target)
			time.Sleep(100 * time.Millisecond)
			return CleanupResult{
				Cleaned: 42,
				Target:  payload.Target,
			}, nil
		})
}

// Task payloads and results

type EmailPayload struct {
	To      string `json:"to"`
	Subject string `json:"subject"`
	Body    string `json:"body"`
}

type EmailResult struct {
	Sent   bool      `json:"sent"`
	SentAt time.Time `json:"sent_at"`
}

type DataPayload struct {
	Source string `json:"source"`
	Count  int    `json:"count"`
}

type DataResult struct {
	Processed int           `json:"processed"`
	Duration  time.Duration `json:"duration"`
}

type ReportPayload struct {
	ReportType string                 `json:"report_type"`
	Params     map[string]interface{} `json:"params"`
}

type ReportResult struct {
	ReportID string `json:"report_id"`
	URL      string `json:"url"`
}

type NotificationPayload struct {
	UserID  string `json:"user_id"`
	Message string `json:"message"`
	Channel string `json:"channel"`
}

type NotificationResult struct {
	Delivered bool   `json:"delivered"`
	Channel   string `json:"channel"`
}

type CleanupPayload struct {
	Target  string `json:"target"`
	MaxAge  int    `json:"max_age_days"`
	DryRun  bool   `json:"dry_run"`
}

type CleanupResult struct {
	Cleaned int    `json:"cleaned"`
	Target  string `json:"target"`
}
