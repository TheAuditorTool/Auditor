// Package storage provides task persistence implementations.
package storage

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/example/task-queue/internal/queue"
)

// Common storage errors
var (
	ErrNotFound      = errors.New("record not found")
	ErrDuplicateKey  = errors.New("duplicate key")
	ErrStorageClosed = errors.New("storage is closed")
)

// Storage defines the interface for task persistence
type Storage interface {
	// Task operations
	SaveTask(ctx context.Context, task *queue.Task) error
	GetTask(ctx context.Context, id string) (*queue.Task, error)
	UpdateTask(ctx context.Context, task *queue.Task) error
	DeleteTask(ctx context.Context, id string) error
	ListTasks(ctx context.Context, filter TaskFilter) ([]*queue.Task, error)

	// Bulk operations
	SaveTasks(ctx context.Context, tasks []*queue.Task) error
	DeleteTasks(ctx context.Context, ids []string) error

	// Query operations
	CountTasks(ctx context.Context, filter TaskFilter) (int, error)
	GetTasksByState(ctx context.Context, state queue.TaskState) ([]*queue.Task, error)
	GetStaleTasks(ctx context.Context, olderThan time.Duration) ([]*queue.Task, error)

	// Lifecycle
	Close() error
	Ping(ctx context.Context) error
}

// TaskFilter defines filtering options for task queries
type TaskFilter struct {
	State      queue.TaskState
	Type       string
	Priority   queue.Priority
	CreatedAfter  time.Time
	CreatedBefore time.Time
	Limit      int
	Offset     int
	OrderBy    string
	OrderDesc  bool
}

// ResultSet represents a paginated result
type ResultSet[T any] struct {
	Items      []T   `json:"items"`
	Total      int   `json:"total"`
	Page       int   `json:"page"`
	PerPage    int   `json:"per_page"`
	TotalPages int   `json:"total_pages"`
}

// Transaction represents a storage transaction
type Transaction interface {
	Storage
	Commit() error
	Rollback() error
}

// TransactionalStorage supports transactions
type TransactionalStorage interface {
	Storage
	Begin(ctx context.Context) (Transaction, error)
}

// Migrator handles database migrations
type Migrator interface {
	Up(ctx context.Context) error
	Down(ctx context.Context) error
	Version() (int, error)
}

// Serializer handles task serialization
type Serializer interface {
	Serialize(task *queue.Task) ([]byte, error)
	Deserialize(data []byte) (*queue.Task, error)
}

// JSONSerializer implements Serializer using JSON
type JSONSerializer struct{}

// Serialize serializes a task to JSON
func (s *JSONSerializer) Serialize(task *queue.Task) ([]byte, error) {
	return json.Marshal(task)
}

// Deserialize deserializes a task from JSON
func (s *JSONSerializer) Deserialize(data []byte) (*queue.Task, error) {
	var task queue.Task
	if err := json.Unmarshal(data, &task); err != nil {
		return nil, err
	}
	return &task, nil
}

// InMemoryStorage is a simple in-memory storage for testing
type InMemoryStorage struct {
	tasks map[string]*queue.Task
}

// NewInMemoryStorage creates a new in-memory storage
func NewInMemoryStorage() *InMemoryStorage {
	return &InMemoryStorage{
		tasks: make(map[string]*queue.Task),
	}
}

// SaveTask saves a task
func (s *InMemoryStorage) SaveTask(ctx context.Context, task *queue.Task) error {
	s.tasks[task.ID] = task
	return nil
}

// GetTask retrieves a task
func (s *InMemoryStorage) GetTask(ctx context.Context, id string) (*queue.Task, error) {
	task, ok := s.tasks[id]
	if !ok {
		return nil, ErrNotFound
	}
	return task, nil
}

// UpdateTask updates a task
func (s *InMemoryStorage) UpdateTask(ctx context.Context, task *queue.Task) error {
	if _, ok := s.tasks[task.ID]; !ok {
		return ErrNotFound
	}
	s.tasks[task.ID] = task
	return nil
}

// DeleteTask deletes a task
func (s *InMemoryStorage) DeleteTask(ctx context.Context, id string) error {
	delete(s.tasks, id)
	return nil
}

// ListTasks lists tasks with filter
func (s *InMemoryStorage) ListTasks(ctx context.Context, filter TaskFilter) ([]*queue.Task, error) {
	result := make([]*queue.Task, 0)

	for _, task := range s.tasks {
		if filter.State != "" && task.State != filter.State {
			continue
		}
		if filter.Type != "" && task.Type != filter.Type {
			continue
		}
		result = append(result, task)
	}

	// Apply offset and limit
	if filter.Offset > 0 && filter.Offset < len(result) {
		result = result[filter.Offset:]
	}
	if filter.Limit > 0 && filter.Limit < len(result) {
		result = result[:filter.Limit]
	}

	return result, nil
}

// SaveTasks saves multiple tasks
func (s *InMemoryStorage) SaveTasks(ctx context.Context, tasks []*queue.Task) error {
	for _, task := range tasks {
		s.tasks[task.ID] = task
	}
	return nil
}

// DeleteTasks deletes multiple tasks
func (s *InMemoryStorage) DeleteTasks(ctx context.Context, ids []string) error {
	for _, id := range ids {
		delete(s.tasks, id)
	}
	return nil
}

// CountTasks counts tasks matching filter
func (s *InMemoryStorage) CountTasks(ctx context.Context, filter TaskFilter) (int, error) {
	tasks, err := s.ListTasks(ctx, filter)
	if err != nil {
		return 0, err
	}
	return len(tasks), nil
}

// GetTasksByState gets all tasks in a state
func (s *InMemoryStorage) GetTasksByState(ctx context.Context, state queue.TaskState) ([]*queue.Task, error) {
	return s.ListTasks(ctx, TaskFilter{State: state})
}

// GetStaleTasks gets tasks older than duration
func (s *InMemoryStorage) GetStaleTasks(ctx context.Context, olderThan time.Duration) ([]*queue.Task, error) {
	threshold := time.Now().Add(-olderThan)
	result := make([]*queue.Task, 0)

	for _, task := range s.tasks {
		if task.CreatedAt.Before(threshold) {
			result = append(result, task)
		}
	}

	return result, nil
}

// Close closes the storage
func (s *InMemoryStorage) Close() error {
	s.tasks = nil
	return nil
}

// Ping checks storage health
func (s *InMemoryStorage) Ping(ctx context.Context) error {
	if s.tasks == nil {
		return ErrStorageClosed
	}
	return nil
}
