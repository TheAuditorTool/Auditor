// Package main provides a standalone worker process.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/example/task-queue/internal/queue"
	"github.com/example/task-queue/internal/task"
	"github.com/example/task-queue/internal/worker"
)

// WorkerConfig holds worker configuration
type WorkerConfig struct {
	QueueURL     string
	NumWorkers   int
	TaskTimeout  time.Duration
	PollInterval time.Duration
	LogLevel     string
}

// DefaultWorkerConfig returns default worker configuration
func DefaultWorkerConfig() WorkerConfig {
	return WorkerConfig{
		QueueURL:     "memory://",
		NumWorkers:   2,
		TaskTimeout:  60 * time.Second,
		PollInterval: time.Second,
		LogLevel:     "info",
	}
}

func main() {
	cfg := parseFlags()

	logger := log.New(os.Stdout, "[worker] ", log.LstdFlags|log.Lshortfile)
	logger.Printf("Starting worker with config: %+v", cfg)

	// Initialize queue (in real app, this would connect to a shared queue)
	q := queue.NewMemoryQueue()
	defer q.Close()

	// Initialize registry
	registry := task.NewRegistry()

	// Add logging hook
	registry.AddHook(&task.HookFunc{
		before: func(ctx context.Context, t *queue.Task) error {
			logger.Printf("Starting task %s (type=%s)", t.ID, t.Type)
			return nil
		},
		after: func(ctx context.Context, t *queue.Task, result interface{}, err error) {
			if err != nil {
				logger.Printf("Task %s failed: %v", t.ID, err)
			} else {
				logger.Printf("Task %s completed", t.ID)
			}
		},
	})

	// Register handlers
	registerWorkerHandlers(registry, logger)

	// Create worker pool
	pool := worker.NewPool(
		q,
		registry,
		worker.PoolConfig{
			NumWorkers:      cfg.NumWorkers,
			MaxQueueSize:    1000,
			TaskTimeout:     cfg.TaskTimeout,
			ShutdownTimeout: 30 * time.Second,
			RetryDelay:      time.Second,
			MaxRetries:      3,
		},
		worker.WithTaskCompleteCallback(func(r *worker.Result) {
			logger.Printf("Task %s processed by worker %d in %v",
				r.Task.ID, r.WorkerID, r.Duration)
		}),
	)

	// Start pool
	if err := pool.Start(); err != nil {
		logger.Fatalf("Failed to start worker pool: %v", err)
	}

	// Enqueue some test tasks
	go func() {
		for i := 0; i < 10; i++ {
			task := &queue.Task{
				Type: "compute",
				Payload: map[string]interface{}{
					"value": i,
				},
			}
			if err := q.Enqueue(context.Background(), task); err != nil {
				logger.Printf("Failed to enqueue task: %v", err)
			}
			time.Sleep(500 * time.Millisecond)
		}
	}()

	// Handle shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Println("Shutting down worker...")

	if err := pool.Stop(); err != nil {
		logger.Printf("Error stopping pool: %v", err)
	}

	logger.Println("Worker stopped")
}

func parseFlags() WorkerConfig {
	cfg := DefaultWorkerConfig()

	flag.StringVar(&cfg.QueueURL, "queue", cfg.QueueURL, "Queue URL")
	flag.IntVar(&cfg.NumWorkers, "workers", cfg.NumWorkers, "Number of workers")
	flag.DurationVar(&cfg.TaskTimeout, "timeout", cfg.TaskTimeout, "Task timeout")
	flag.DurationVar(&cfg.PollInterval, "poll", cfg.PollInterval, "Poll interval")
	flag.StringVar(&cfg.LogLevel, "log-level", cfg.LogLevel, "Log level")

	flag.Parse()

	return cfg
}

func registerWorkerHandlers(registry *task.Registry, logger *log.Logger) {
	// Compute task
	task.RegisterFunc(registry, "compute", 30*time.Second,
		func(ctx context.Context, payload ComputePayload) (ComputeResult, error) {
			logger.Printf("Computing value: %d", payload.Value)
			// Simulate computation
			time.Sleep(100 * time.Millisecond)
			return ComputeResult{
				Result: payload.Value * 2,
			}, nil
		})

	// Transform task
	task.RegisterFunc(registry, "transform", 30*time.Second,
		func(ctx context.Context, payload TransformPayload) (TransformResult, error) {
			logger.Printf("Transforming data: %s", payload.Data)
			time.Sleep(50 * time.Millisecond)
			return TransformResult{
				Transformed: fmt.Sprintf("TRANSFORMED(%s)", payload.Data),
			}, nil
		})

	// Aggregate task
	task.RegisterFunc(registry, "aggregate", 60*time.Second,
		func(ctx context.Context, payload AggregatePayload) (AggregateResult, error) {
			logger.Printf("Aggregating %d values", len(payload.Values))
			var sum float64
			for _, v := range payload.Values {
				sum += v
			}
			return AggregateResult{
				Sum:     sum,
				Average: sum / float64(len(payload.Values)),
				Count:   len(payload.Values),
			}, nil
		})

	// Index task
	task.RegisterFunc(registry, "index", 120*time.Second,
		func(ctx context.Context, payload IndexPayload) (IndexResult, error) {
			logger.Printf("Indexing documents from %s", payload.Source)
			time.Sleep(200 * time.Millisecond)
			return IndexResult{
				Indexed:  100,
				Duration: 200 * time.Millisecond,
			}, nil
		})
}

// Task payload and result types

type ComputePayload struct {
	Value int `json:"value"`
}

type ComputeResult struct {
	Result int `json:"result"`
}

type TransformPayload struct {
	Data string `json:"data"`
}

type TransformResult struct {
	Transformed string `json:"transformed"`
}

type AggregatePayload struct {
	Values []float64 `json:"values"`
}

type AggregateResult struct {
	Sum     float64 `json:"sum"`
	Average float64 `json:"average"`
	Count   int     `json:"count"`
}

type IndexPayload struct {
	Source string `json:"source"`
	Count  int    `json:"count"`
}

type IndexResult struct {
	Indexed  int           `json:"indexed"`
	Duration time.Duration `json:"duration"`
}
