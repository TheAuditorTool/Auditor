package queue

import (
	"container/heap"
	"context"
	"sync"
	"time"
)

// Notification is a minimal notification struct for the queue.
type Notification struct {
	ID        string
	UserID    string
	Type      int32
	Title     string
	Body      string
	Data      map[string]string
	Priority  int32
	CreatedAt int64
	SentAt    int64
}

// ScheduledNotification wraps a notification with its scheduled time.
type ScheduledNotification struct {
	Notification *Notification
	ScheduledAt  time.Time
	index        int
}

// PriorityQueue implements heap.Interface for scheduled notifications.
type PriorityQueue []*ScheduledNotification

func (pq PriorityQueue) Len() int { return len(pq) }

func (pq PriorityQueue) Less(i, j int) bool {
	return pq[i].ScheduledAt.Before(pq[j].ScheduledAt)
}

func (pq PriorityQueue) Swap(i, j int) {
	pq[i], pq[j] = pq[j], pq[i]
	pq[i].index = i
	pq[j].index = j
}

func (pq *PriorityQueue) Push(x interface{}) {
	n := len(*pq)
	item := x.(*ScheduledNotification)
	item.index = n
	*pq = append(*pq, item)
}

func (pq *PriorityQueue) Pop() interface{} {
	old := *pq
	n := len(old)
	item := old[n-1]
	old[n-1] = nil
	item.index = -1
	*pq = old[0 : n-1]
	return item
}

// NotificationQueue manages scheduled notifications.
type NotificationQueue struct {
	queue    PriorityQueue
	mu       sync.Mutex
	handler  func(*Notification) error
	stopChan chan struct{}
	wg       sync.WaitGroup
}

// NewNotificationQueue creates a new NotificationQueue.
func NewNotificationQueue(handler func(*Notification) error) *NotificationQueue {
	q := &NotificationQueue{
		queue:    make(PriorityQueue, 0),
		handler:  handler,
		stopChan: make(chan struct{}),
	}
	heap.Init(&q.queue)
	return q
}

// Start starts the queue processor.
func (q *NotificationQueue) Start(ctx context.Context) {
	q.wg.Add(1)
	go q.processLoop(ctx)
}

// Stop stops the queue processor.
func (q *NotificationQueue) Stop() {
	close(q.stopChan)
	q.wg.Wait()
}

// Schedule schedules a notification for future delivery.
func (q *NotificationQueue) Schedule(n *Notification, at time.Time) error {
	q.mu.Lock()
	defer q.mu.Unlock()

	item := &ScheduledNotification{
		Notification: n,
		ScheduledAt:  at,
	}
	heap.Push(&q.queue, item)

	return nil
}

// processLoop continuously processes scheduled notifications.
func (q *NotificationQueue) processLoop(ctx context.Context) {
	defer q.wg.Done()

	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-q.stopChan:
			return
		case <-ticker.C:
			q.processReady()
		}
	}
}

// processReady processes all notifications that are ready to be sent.
func (q *NotificationQueue) processReady() {
	now := time.Now()

	for {
		q.mu.Lock()
		if q.queue.Len() == 0 {
			q.mu.Unlock()
			return
		}

		// Peek at the next item
		next := q.queue[0]
		if next.ScheduledAt.After(now) {
			q.mu.Unlock()
			return
		}

		// Pop and process
		item := heap.Pop(&q.queue).(*ScheduledNotification)
		q.mu.Unlock()

		// Process in goroutine
		go func(n *Notification) {
			if err := q.handler(n); err != nil {
				// Log error and potentially retry
				// For now, just log
				println("Failed to send scheduled notification:", err.Error())
			}
		}(item.Notification)
	}
}

// Pending returns the number of pending notifications.
func (q *NotificationQueue) Pending() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return q.queue.Len()
}

// Clear clears all pending notifications.
func (q *NotificationQueue) Clear() {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.queue = make(PriorityQueue, 0)
	heap.Init(&q.queue)
}
