// Package queue provides task queue abstractions and implementations.
package queue

import (
	"context"
	"errors"
	"time"
)

// Common queue errors
var (
	ErrQueueEmpty    = errors.New("queue is empty")
	ErrQueueFull     = errors.New("queue is full")
	ErrTaskNotFound  = errors.New("task not found")
	ErrQueueClosed   = errors.New("queue is closed")
	ErrInvalidTask   = errors.New("invalid task")
	ErrTimeout       = errors.New("operation timed out")
)

// Priority levels for tasks
type Priority int

const (
	PriorityLow Priority = iota
	PriorityNormal
	PriorityHigh
	PriorityCritical
)

// String returns the string representation of a priority
func (p Priority) String() string {
	switch p {
	case PriorityLow:
		return "low"
	case PriorityNormal:
		return "normal"
	case PriorityHigh:
		return "high"
	case PriorityCritical:
		return "critical"
	default:
		return "unknown"
	}
}

// TaskState represents the current state of a task
type TaskState string

const (
	StatePending    TaskState = "pending"
	StateProcessing TaskState = "processing"
	StateCompleted  TaskState = "completed"
	StateFailed     TaskState = "failed"
	StateRetrying   TaskState = "retrying"
	StateCancelled  TaskState = "cancelled"
)

// Task represents a unit of work in the queue
type Task struct {
	ID          string                 `json:"id"`
	Type        string                 `json:"type"`
	Payload     map[string]interface{} `json:"payload"`
	Priority    Priority               `json:"priority"`
	State       TaskState              `json:"state"`
	CreatedAt   time.Time              `json:"created_at"`
	StartedAt   *time.Time             `json:"started_at,omitempty"`
	CompletedAt *time.Time             `json:"completed_at,omitempty"`
	Retries     int                    `json:"retries"`
	MaxRetries  int                    `json:"max_retries"`
	Error       string                 `json:"error,omitempty"`
	Result      interface{}            `json:"result,omitempty"`
	Metadata    map[string]string      `json:"metadata,omitempty"`
}

// Queue defines the interface for task queue operations
type Queue interface {
	// Enqueue adds a task to the queue
	Enqueue(ctx context.Context, task *Task) error

	// Dequeue removes and returns the next task from the queue
	Dequeue(ctx context.Context) (*Task, error)

	// Peek returns the next task without removing it
	Peek(ctx context.Context) (*Task, error)

	// Get retrieves a specific task by ID
	Get(ctx context.Context, id string) (*Task, error)

	// Update updates an existing task
	Update(ctx context.Context, task *Task) error

	// Delete removes a task from the queue
	Delete(ctx context.Context, id string) error

	// Len returns the number of tasks in the queue
	Len() int

	// Close closes the queue and releases resources
	Close() error
}

// BlockingQueue extends Queue with blocking operations
type BlockingQueue interface {
	Queue

	// DequeueBlocking blocks until a task is available or context is cancelled
	DequeueBlocking(ctx context.Context) (*Task, error)

	// EnqueueWithTimeout enqueues with a timeout
	EnqueueWithTimeout(ctx context.Context, task *Task, timeout time.Duration) error
}

// PriorityQueue extends Queue with priority-based operations
type PriorityQueue interface {
	Queue

	// EnqueueWithPriority adds a task with specific priority
	EnqueueWithPriority(ctx context.Context, task *Task, priority Priority) error

	// DequeueByPriority gets the highest priority task
	DequeueByPriority(ctx context.Context) (*Task, error)
}

// QueueStats holds queue statistics
type QueueStats struct {
	TotalEnqueued  int64         `json:"total_enqueued"`
	TotalDequeued  int64         `json:"total_dequeued"`
	TotalFailed    int64         `json:"total_failed"`
	CurrentSize    int           `json:"current_size"`
	AvgWaitTime    time.Duration `json:"avg_wait_time"`
	AvgProcessTime time.Duration `json:"avg_process_time"`
}

// StatsCollector interface for queue statistics
type StatsCollector interface {
	Stats() QueueStats
	ResetStats()
}
