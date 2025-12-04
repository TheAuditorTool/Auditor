package queue

import (
	"container/heap"
	"context"
	"sync"
	"sync/atomic"
	"time"

	"github.com/google/uuid"
)

// MemoryQueue is a thread-safe in-memory task queue
type MemoryQueue struct {
	mu       sync.RWMutex
	tasks    []*Task
	taskMap  map[string]*Task
	closed   atomic.Bool
	notify   chan struct{}
	stats    *queueStats
	maxSize  int
	onEnqueue func(*Task)
	onDequeue func(*Task)
}

// queueStats holds internal statistics
type queueStats struct {
	totalEnqueued  atomic.Int64
	totalDequeued  atomic.Int64
	totalFailed    atomic.Int64
	waitTimeSum    atomic.Int64
	waitTimeCount  atomic.Int64
	processTimeSum atomic.Int64
	processTimeCount atomic.Int64
}

// MemoryQueueOption is a functional option for MemoryQueue
type MemoryQueueOption func(*MemoryQueue)

// WithMaxSize sets the maximum queue size
func WithMaxSize(size int) MemoryQueueOption {
	return func(q *MemoryQueue) {
		q.maxSize = size
	}
}

// WithEnqueueCallback sets a callback for enqueue events
func WithEnqueueCallback(fn func(*Task)) MemoryQueueOption {
	return func(q *MemoryQueue) {
		q.onEnqueue = fn
	}
}

// WithDequeueCallback sets a callback for dequeue events
func WithDequeueCallback(fn func(*Task)) MemoryQueueOption {
	return func(q *MemoryQueue) {
		q.onDequeue = fn
	}
}

// NewMemoryQueue creates a new in-memory queue
func NewMemoryQueue(opts ...MemoryQueueOption) *MemoryQueue {
	q := &MemoryQueue{
		tasks:   make([]*Task, 0),
		taskMap: make(map[string]*Task),
		notify:  make(chan struct{}, 1),
		stats:   &queueStats{},
		maxSize: 10000, // Default max size
	}

	for _, opt := range opts {
		opt(q)
	}

	return q
}

// Enqueue adds a task to the queue
func (q *MemoryQueue) Enqueue(ctx context.Context, task *Task) error {
	if q.closed.Load() {
		return ErrQueueClosed
	}

	if task == nil {
		return ErrInvalidTask
	}

	q.mu.Lock()
	defer q.mu.Unlock()

	if q.maxSize > 0 && len(q.tasks) >= q.maxSize {
		return ErrQueueFull
	}

	// Assign ID if not set
	if task.ID == "" {
		task.ID = uuid.New().String()
	}

	task.State = StatePending
	task.CreatedAt = time.Now()

	q.tasks = append(q.tasks, task)
	q.taskMap[task.ID] = task
	q.stats.totalEnqueued.Add(1)

	// Notify waiting consumers
	select {
	case q.notify <- struct{}{}:
	default:
	}

	if q.onEnqueue != nil {
		go q.onEnqueue(task)
	}

	return nil
}

// Dequeue removes and returns the next task
func (q *MemoryQueue) Dequeue(ctx context.Context) (*Task, error) {
	if q.closed.Load() {
		return nil, ErrQueueClosed
	}

	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.tasks) == 0 {
		return nil, ErrQueueEmpty
	}

	task := q.tasks[0]
	q.tasks = q.tasks[1:]

	now := time.Now()
	task.State = StateProcessing
	task.StartedAt = &now

	// Track wait time
	waitTime := now.Sub(task.CreatedAt)
	q.stats.waitTimeSum.Add(waitTime.Nanoseconds())
	q.stats.waitTimeCount.Add(1)
	q.stats.totalDequeued.Add(1)

	if q.onDequeue != nil {
		go q.onDequeue(task)
	}

	return task, nil
}

// DequeueBlocking blocks until a task is available
func (q *MemoryQueue) DequeueBlocking(ctx context.Context) (*Task, error) {
	for {
		task, err := q.Dequeue(ctx)
		if err == nil {
			return task, nil
		}

		if err != ErrQueueEmpty {
			return nil, err
		}

		// Wait for notification or context cancellation
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-q.notify:
			// Try again
		}
	}
}

// EnqueueWithTimeout enqueues with a timeout
func (q *MemoryQueue) EnqueueWithTimeout(ctx context.Context, task *Task, timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Try to enqueue with retry on full queue
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		err := q.Enqueue(ctx, task)
		if err == nil {
			return nil
		}

		if err != ErrQueueFull {
			return err
		}

		select {
		case <-ctx.Done():
			return ErrTimeout
		case <-ticker.C:
			// Retry
		}
	}
}

// Peek returns the next task without removing it
func (q *MemoryQueue) Peek(ctx context.Context) (*Task, error) {
	q.mu.RLock()
	defer q.mu.RUnlock()

	if len(q.tasks) == 0 {
		return nil, ErrQueueEmpty
	}

	return q.tasks[0], nil
}

// Get retrieves a task by ID
func (q *MemoryQueue) Get(ctx context.Context, id string) (*Task, error) {
	q.mu.RLock()
	defer q.mu.RUnlock()

	task, ok := q.taskMap[id]
	if !ok {
		return nil, ErrTaskNotFound
	}

	return task, nil
}

// Update updates a task
func (q *MemoryQueue) Update(ctx context.Context, task *Task) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	existing, ok := q.taskMap[task.ID]
	if !ok {
		return ErrTaskNotFound
	}

	// Update fields
	existing.State = task.State
	existing.Error = task.Error
	existing.Result = task.Result
	existing.Retries = task.Retries
	existing.CompletedAt = task.CompletedAt

	return nil
}

// Delete removes a task
func (q *MemoryQueue) Delete(ctx context.Context, id string) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	if _, ok := q.taskMap[id]; !ok {
		return ErrTaskNotFound
	}

	delete(q.taskMap, id)

	// Remove from slice
	for i, t := range q.tasks {
		if t.ID == id {
			q.tasks = append(q.tasks[:i], q.tasks[i+1:]...)
			break
		}
	}

	return nil
}

// Len returns the queue length
func (q *MemoryQueue) Len() int {
	q.mu.RLock()
	defer q.mu.RUnlock()
	return len(q.tasks)
}

// Close closes the queue
func (q *MemoryQueue) Close() error {
	q.closed.Store(true)
	close(q.notify)
	return nil
}

// Stats returns queue statistics
func (q *MemoryQueue) Stats() QueueStats {
	var avgWait, avgProcess time.Duration

	waitCount := q.stats.waitTimeCount.Load()
	if waitCount > 0 {
		avgWait = time.Duration(q.stats.waitTimeSum.Load() / waitCount)
	}

	processCount := q.stats.processTimeCount.Load()
	if processCount > 0 {
		avgProcess = time.Duration(q.stats.processTimeSum.Load() / processCount)
	}

	return QueueStats{
		TotalEnqueued:  q.stats.totalEnqueued.Load(),
		TotalDequeued:  q.stats.totalDequeued.Load(),
		TotalFailed:    q.stats.totalFailed.Load(),
		CurrentSize:    q.Len(),
		AvgWaitTime:    avgWait,
		AvgProcessTime: avgProcess,
	}
}

// ResetStats resets the statistics
func (q *MemoryQueue) ResetStats() {
	q.stats.totalEnqueued.Store(0)
	q.stats.totalDequeued.Store(0)
	q.stats.totalFailed.Store(0)
	q.stats.waitTimeSum.Store(0)
	q.stats.waitTimeCount.Store(0)
	q.stats.processTimeSum.Store(0)
	q.stats.processTimeCount.Store(0)
}

// MarkFailed marks a task as failed
func (q *MemoryQueue) MarkFailed(ctx context.Context, id string, errMsg string) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	task, ok := q.taskMap[id]
	if !ok {
		return ErrTaskNotFound
	}

	task.State = StateFailed
	task.Error = errMsg
	now := time.Now()
	task.CompletedAt = &now

	q.stats.totalFailed.Add(1)

	return nil
}

// MarkCompleted marks a task as completed
func (q *MemoryQueue) MarkCompleted(ctx context.Context, id string, result interface{}) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	task, ok := q.taskMap[id]
	if !ok {
		return ErrTaskNotFound
	}

	now := time.Now()
	task.State = StateCompleted
	task.Result = result
	task.CompletedAt = &now

	// Track process time
	if task.StartedAt != nil {
		processTime := now.Sub(*task.StartedAt)
		q.stats.processTimeSum.Add(processTime.Nanoseconds())
		q.stats.processTimeCount.Add(1)
	}

	return nil
}

// Retry re-queues a failed task
func (q *MemoryQueue) Retry(ctx context.Context, id string) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	task, ok := q.taskMap[id]
	if !ok {
		return ErrTaskNotFound
	}

	if task.Retries >= task.MaxRetries {
		return errors.New("max retries exceeded")
	}

	task.State = StateRetrying
	task.Retries++
	task.Error = ""
	task.StartedAt = nil

	// Move to end of queue
	for i, t := range q.tasks {
		if t.ID == id {
			q.tasks = append(q.tasks[:i], q.tasks[i+1:]...)
			break
		}
	}
	q.tasks = append(q.tasks, task)

	return nil
}

// Drain removes and returns all tasks
func (q *MemoryQueue) Drain(ctx context.Context) ([]*Task, error) {
	q.mu.Lock()
	defer q.mu.Unlock()

	tasks := make([]*Task, len(q.tasks))
	copy(tasks, q.tasks)

	q.tasks = q.tasks[:0]
	q.taskMap = make(map[string]*Task)

	return tasks, nil
}

// priorityItem implements heap.Interface for priority queue
type priorityItem struct {
	task     *Task
	priority Priority
	index    int
}

// PriorityMemoryQueue is a priority-based queue implementation
type PriorityMemoryQueue struct {
	mu      sync.RWMutex
	items   priorityHeap
	taskMap map[string]*priorityItem
	closed  atomic.Bool
	notify  chan struct{}
}

type priorityHeap []*priorityItem

func (h priorityHeap) Len() int           { return len(h) }
func (h priorityHeap) Less(i, j int) bool { return h[i].priority > h[j].priority }
func (h priorityHeap) Swap(i, j int) {
	h[i], h[j] = h[j], h[i]
	h[i].index = i
	h[j].index = j
}

func (h *priorityHeap) Push(x interface{}) {
	n := len(*h)
	item := x.(*priorityItem)
	item.index = n
	*h = append(*h, item)
}

func (h *priorityHeap) Pop() interface{} {
	old := *h
	n := len(old)
	item := old[n-1]
	old[n-1] = nil
	item.index = -1
	*h = old[0 : n-1]
	return item
}

// NewPriorityMemoryQueue creates a priority queue
func NewPriorityMemoryQueue() *PriorityMemoryQueue {
	pq := &PriorityMemoryQueue{
		items:   make(priorityHeap, 0),
		taskMap: make(map[string]*priorityItem),
		notify:  make(chan struct{}, 1),
	}
	heap.Init(&pq.items)
	return pq
}

// Enqueue adds a task with default priority
func (pq *PriorityMemoryQueue) Enqueue(ctx context.Context, task *Task) error {
	return pq.EnqueueWithPriority(ctx, task, task.Priority)
}

// EnqueueWithPriority adds a task with specific priority
func (pq *PriorityMemoryQueue) EnqueueWithPriority(ctx context.Context, task *Task, priority Priority) error {
	if pq.closed.Load() {
		return ErrQueueClosed
	}

	if task == nil {
		return ErrInvalidTask
	}

	pq.mu.Lock()
	defer pq.mu.Unlock()

	if task.ID == "" {
		task.ID = uuid.New().String()
	}

	task.State = StatePending
	task.Priority = priority
	task.CreatedAt = time.Now()

	item := &priorityItem{
		task:     task,
		priority: priority,
	}

	heap.Push(&pq.items, item)
	pq.taskMap[task.ID] = item

	select {
	case pq.notify <- struct{}{}:
	default:
	}

	return nil
}

// Dequeue removes the next task (not priority based)
func (pq *PriorityMemoryQueue) Dequeue(ctx context.Context) (*Task, error) {
	return pq.DequeueByPriority(ctx)
}

// DequeueByPriority removes the highest priority task
func (pq *PriorityMemoryQueue) DequeueByPriority(ctx context.Context) (*Task, error) {
	if pq.closed.Load() {
		return nil, ErrQueueClosed
	}

	pq.mu.Lock()
	defer pq.mu.Unlock()

	if pq.items.Len() == 0 {
		return nil, ErrQueueEmpty
	}

	item := heap.Pop(&pq.items).(*priorityItem)
	delete(pq.taskMap, item.task.ID)

	now := time.Now()
	item.task.State = StateProcessing
	item.task.StartedAt = &now

	return item.task, nil
}

// Peek returns the highest priority task
func (pq *PriorityMemoryQueue) Peek(ctx context.Context) (*Task, error) {
	pq.mu.RLock()
	defer pq.mu.RUnlock()

	if len(pq.items) == 0 {
		return nil, ErrQueueEmpty
	}

	return pq.items[0].task, nil
}

// Get retrieves a task by ID
func (pq *PriorityMemoryQueue) Get(ctx context.Context, id string) (*Task, error) {
	pq.mu.RLock()
	defer pq.mu.RUnlock()

	item, ok := pq.taskMap[id]
	if !ok {
		return nil, ErrTaskNotFound
	}

	return item.task, nil
}

// Update updates a task
func (pq *PriorityMemoryQueue) Update(ctx context.Context, task *Task) error {
	pq.mu.Lock()
	defer pq.mu.Unlock()

	item, ok := pq.taskMap[task.ID]
	if !ok {
		return ErrTaskNotFound
	}

	item.task.State = task.State
	item.task.Error = task.Error
	item.task.Result = task.Result

	// Update priority if changed
	if item.priority != task.Priority {
		item.priority = task.Priority
		heap.Fix(&pq.items, item.index)
	}

	return nil
}

// Delete removes a task
func (pq *PriorityMemoryQueue) Delete(ctx context.Context, id string) error {
	pq.mu.Lock()
	defer pq.mu.Unlock()

	item, ok := pq.taskMap[id]
	if !ok {
		return ErrTaskNotFound
	}

	heap.Remove(&pq.items, item.index)
	delete(pq.taskMap, id)

	return nil
}

// Len returns the queue length
func (pq *PriorityMemoryQueue) Len() int {
	pq.mu.RLock()
	defer pq.mu.RUnlock()
	return len(pq.items)
}

// Close closes the queue
func (pq *PriorityMemoryQueue) Close() error {
	pq.closed.Store(true)
	close(pq.notify)
	return nil
}

// errors is imported for Retry function
var errors = struct {
	New func(text string) error
}{
	New: func(text string) error {
		return &customError{text}
	},
}

type customError struct {
	msg string
}

func (e *customError) Error() string {
	return e.msg
}
