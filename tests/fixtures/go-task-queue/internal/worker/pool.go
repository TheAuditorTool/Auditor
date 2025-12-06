// Package worker provides worker pool implementation for task processing.
package worker

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/example/task-queue/internal/queue"
	"github.com/example/task-queue/internal/task"
)

// Common worker errors
var (
	ErrPoolShutdown   = errors.New("worker pool is shut down")
	ErrPoolNotStarted = errors.New("worker pool not started")
	ErrWorkerPanic    = errors.New("worker panicked")
)

// PoolState represents the current state of the worker pool
type PoolState int32

const (
	StateIdle PoolState = iota
	StateRunning
	StateShuttingDown
	StateStopped
)

// String returns the string representation of pool state
func (s PoolState) String() string {
	switch s {
	case StateIdle:
		return "idle"
	case StateRunning:
		return "running"
	case StateShuttingDown:
		return "shutting_down"
	case StateStopped:
		return "stopped"
	default:
		return "unknown"
	}
}

// PoolConfig holds configuration for the worker pool
type PoolConfig struct {
	NumWorkers      int
	MaxQueueSize    int
	TaskTimeout     time.Duration
	ShutdownTimeout time.Duration
	RetryDelay      time.Duration
	MaxRetries      int
}

// DefaultPoolConfig returns default pool configuration
func DefaultPoolConfig() PoolConfig {
	return PoolConfig{
		NumWorkers:      4,
		MaxQueueSize:    1000,
		TaskTimeout:     30 * time.Second,
		ShutdownTimeout: 10 * time.Second,
		RetryDelay:      time.Second,
		MaxRetries:      3,
	}
}

// Pool manages a pool of workers for task processing
type Pool struct {
	config   PoolConfig
	queue    queue.BlockingQueue
	registry *task.Registry
	state    atomic.Int32
	wg       sync.WaitGroup
	cancel   context.CancelFunc
	ctx      context.Context

	// Channels for communication
	jobs       chan *queue.Task
	results    chan *Result
	done       chan struct{}
	workerDone chan int

	// Metrics
	metrics *PoolMetrics

	// Callbacks
	onTaskComplete func(*Result)
	onTaskFail     func(*queue.Task, error)
	onWorkerPanic  func(workerID int, recovered interface{})
}

// Result represents the result of processing a task
type Result struct {
	Task      *queue.Task   `json:"task"`
	Output    interface{}   `json:"output,omitempty"`
	Error     error         `json:"error,omitempty"`
	Duration  time.Duration `json:"duration"`
	WorkerID  int           `json:"worker_id"`
	Timestamp time.Time     `json:"timestamp"`
}

// PoolMetrics holds pool performance metrics
type PoolMetrics struct {
	TasksProcessed  atomic.Int64
	TasksFailed     atomic.Int64
	TasksRetried    atomic.Int64
	TotalDuration   atomic.Int64
	ActiveWorkers   atomic.Int32
	QueueDepth      atomic.Int32
	WorkerRestarts  atomic.Int64
}

// Snapshot returns a snapshot of current metrics
func (m *PoolMetrics) Snapshot() MetricsSnapshot {
	processed := m.TasksProcessed.Load()
	totalDuration := m.TotalDuration.Load()

	var avgDuration time.Duration
	if processed > 0 {
		avgDuration = time.Duration(totalDuration / processed)
	}

	return MetricsSnapshot{
		TasksProcessed:  processed,
		TasksFailed:     m.TasksFailed.Load(),
		TasksRetried:    m.TasksRetried.Load(),
		ActiveWorkers:   int(m.ActiveWorkers.Load()),
		QueueDepth:      int(m.QueueDepth.Load()),
		AvgTaskDuration: avgDuration,
		WorkerRestarts:  m.WorkerRestarts.Load(),
	}
}

// MetricsSnapshot is a point-in-time snapshot of metrics
type MetricsSnapshot struct {
	TasksProcessed  int64         `json:"tasks_processed"`
	TasksFailed     int64         `json:"tasks_failed"`
	TasksRetried    int64         `json:"tasks_retried"`
	ActiveWorkers   int           `json:"active_workers"`
	QueueDepth      int           `json:"queue_depth"`
	AvgTaskDuration time.Duration `json:"avg_task_duration"`
	WorkerRestarts  int64         `json:"worker_restarts"`
}

// PoolOption is a functional option for Pool
type PoolOption func(*Pool)

// WithTaskCompleteCallback sets the task complete callback
func WithTaskCompleteCallback(fn func(*Result)) PoolOption {
	return func(p *Pool) {
		p.onTaskComplete = fn
	}
}

// WithTaskFailCallback sets the task fail callback
func WithTaskFailCallback(fn func(*queue.Task, error)) PoolOption {
	return func(p *Pool) {
		p.onTaskFail = fn
	}
}

// WithPanicHandler sets the worker panic handler
func WithPanicHandler(fn func(int, interface{})) PoolOption {
	return func(p *Pool) {
		p.onWorkerPanic = fn
	}
}

// NewPool creates a new worker pool
func NewPool(q queue.BlockingQueue, registry *task.Registry, config PoolConfig, opts ...PoolOption) *Pool {
	ctx, cancel := context.WithCancel(context.Background())

	p := &Pool{
		config:     config,
		queue:      q,
		registry:   registry,
		ctx:        ctx,
		cancel:     cancel,
		jobs:       make(chan *queue.Task, config.MaxQueueSize),
		results:    make(chan *Result, config.MaxQueueSize),
		done:       make(chan struct{}),
		workerDone: make(chan int, config.NumWorkers),
		metrics:    &PoolMetrics{},
	}

	p.state.Store(int32(StateIdle))

	for _, opt := range opts {
		opt(p)
	}

	return p
}

// Start starts the worker pool
func (p *Pool) Start() error {
	if !p.state.CompareAndSwap(int32(StateIdle), int32(StateRunning)) {
		return ErrPoolShutdown
	}

	// Start workers
	for i := 0; i < p.config.NumWorkers; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}

	// Start result processor
	go p.processResults()

	// Start dispatcher
	go p.dispatcher()

	return nil
}

// worker is the main worker goroutine
func (p *Pool) worker(id int) {
	defer func() {
		if r := recover(); r != nil {
			p.metrics.WorkerRestarts.Add(1)
			if p.onWorkerPanic != nil {
				p.onWorkerPanic(id, r)
			}
			// Restart worker if pool is still running
			if PoolState(p.state.Load()) == StateRunning {
				go p.worker(id)
				return
			}
		}
		p.wg.Done()
		p.workerDone <- id
	}()

	p.metrics.ActiveWorkers.Add(1)
	defer p.metrics.ActiveWorkers.Add(-1)

	for {
		select {
		case <-p.ctx.Done():
			return
		case task, ok := <-p.jobs:
			if !ok {
				return
			}
			p.processTask(id, task)
		}
	}
}

// processTask processes a single task
func (p *Pool) processTask(workerID int, t *queue.Task) {
	start := time.Now()

	// Create task context with timeout
	ctx, cancel := context.WithTimeout(p.ctx, p.config.TaskTimeout)
	defer cancel()

	// Execute task
	output, err := p.registry.Execute(ctx, t)

	duration := time.Since(start)

	result := &Result{
		Task:      t,
		Output:    output,
		Error:     err,
		Duration:  duration,
		WorkerID:  workerID,
		Timestamp: time.Now(),
	}

	// Send result
	select {
	case p.results <- result:
	case <-p.ctx.Done():
		return
	}
}

// dispatcher pulls tasks from the queue and dispatches to workers
func (p *Pool) dispatcher() {
	for {
		select {
		case <-p.ctx.Done():
			close(p.jobs)
			return
		default:
		}

		// Blocking dequeue
		t, err := p.queue.DequeueBlocking(p.ctx)
		if err != nil {
			if p.ctx.Err() != nil {
				close(p.jobs)
				return
			}
			continue
		}

		p.metrics.QueueDepth.Add(1)

		select {
		case p.jobs <- t:
		case <-p.ctx.Done():
			close(p.jobs)
			return
		}
	}
}

// processResults handles task results
func (p *Pool) processResults() {
	for result := range p.results {
		p.metrics.QueueDepth.Add(-1)
		p.metrics.TotalDuration.Add(result.Duration.Nanoseconds())

		if result.Error != nil {
			p.metrics.TasksFailed.Add(1)
			p.handleFailedTask(result)
		} else {
			p.metrics.TasksProcessed.Add(1)
			p.handleCompletedTask(result)
		}
	}
}

// handleCompletedTask handles successful task completion
func (p *Pool) handleCompletedTask(result *Result) {
	now := time.Now()
	result.Task.State = queue.StateCompleted
	result.Task.CompletedAt = &now
	result.Task.Result = result.Output

	if err := p.queue.Update(p.ctx, result.Task); err != nil {
		// Log error but continue
	}

	if p.onTaskComplete != nil {
		p.onTaskComplete(result)
	}
}

// handleFailedTask handles failed task with retry logic
func (p *Pool) handleFailedTask(result *Result) {
	task := result.Task

	if task.Retries < p.config.MaxRetries {
		// Retry
		task.Retries++
		task.State = queue.StateRetrying
		task.Error = result.Error.Error()
		p.metrics.TasksRetried.Add(1)

		// Re-enqueue after delay
		go func() {
			time.Sleep(p.config.RetryDelay * time.Duration(task.Retries))
			if err := p.queue.Enqueue(p.ctx, task); err != nil {
				p.handlePermanentFailure(task, result.Error)
			}
		}()
	} else {
		p.handlePermanentFailure(task, result.Error)
	}
}

// handlePermanentFailure handles tasks that cannot be retried
func (p *Pool) handlePermanentFailure(t *queue.Task, err error) {
	now := time.Now()
	t.State = queue.StateFailed
	t.CompletedAt = &now
	t.Error = err.Error()

	if updateErr := p.queue.Update(p.ctx, t); updateErr != nil {
		// Log error but continue
	}

	if p.onTaskFail != nil {
		p.onTaskFail(t, err)
	}
}

// Stop gracefully stops the worker pool
func (p *Pool) Stop() error {
	if !p.state.CompareAndSwap(int32(StateRunning), int32(StateShuttingDown)) {
		return ErrPoolNotStarted
	}

	// Signal shutdown
	p.cancel()

	// Wait with timeout
	done := make(chan struct{})
	go func() {
		p.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		// Clean shutdown
	case <-time.After(p.config.ShutdownTimeout):
		return fmt.Errorf("shutdown timed out after %v", p.config.ShutdownTimeout)
	}

	close(p.results)
	p.state.Store(int32(StateStopped))

	return nil
}

// Submit submits a task for processing
func (p *Pool) Submit(ctx context.Context, t *queue.Task) error {
	if PoolState(p.state.Load()) != StateRunning {
		return ErrPoolShutdown
	}

	return p.queue.Enqueue(ctx, t)
}

// Metrics returns the current metrics
func (p *Pool) Metrics() MetricsSnapshot {
	return p.metrics.Snapshot()
}

// State returns the current pool state
func (p *Pool) State() PoolState {
	return PoolState(p.state.Load())
}

// WaitForCompletion waits for all current tasks to complete
func (p *Pool) WaitForCompletion(ctx context.Context) error {
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			if p.queue.Len() == 0 && p.metrics.QueueDepth.Load() == 0 {
				return nil
			}
		}
	}
}

// ScaleUp adds more workers
func (p *Pool) ScaleUp(count int) {
	for i := 0; i < count; i++ {
		p.wg.Add(1)
		go p.worker(p.config.NumWorkers + i)
	}
	p.config.NumWorkers += count
}

// ScaleDown removes workers (they'll stop after current task)
func (p *Pool) ScaleDown(count int) {
	if count > p.config.NumWorkers {
		count = p.config.NumWorkers
	}

	// Workers will exit naturally when receiving done signal
	p.config.NumWorkers -= count
}
