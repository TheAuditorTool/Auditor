// Package api provides HTTP handlers for the task queue API.
package api

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/example/task-queue/internal/queue"
	"github.com/example/task-queue/internal/worker"
)

// Handler holds dependencies for HTTP handlers
type Handler struct {
	queue   queue.Queue
	pool    *worker.Pool
	storage Storage
}

// Storage interface for task persistence
type Storage interface {
	SaveTask(ctx context.Context, task *queue.Task) error
	GetTask(ctx context.Context, id string) (*queue.Task, error)
	ListTasks(ctx context.Context, filter TaskFilter) ([]*queue.Task, error)
	DeleteTask(ctx context.Context, id string) error
}

// TaskFilter for listing tasks
type TaskFilter struct {
	State    queue.TaskState
	Type     string
	Priority queue.Priority
	Limit    int
	Offset   int
}

// NewHandler creates a new API handler
func NewHandler(q queue.Queue, p *worker.Pool, s Storage) *Handler {
	return &Handler{
		queue:   q,
		pool:    p,
		storage: s,
	}
}

// Response is a standard API response
type Response struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
	Meta    *Meta       `json:"meta,omitempty"`
}

// Meta contains response metadata
type Meta struct {
	Total   int    `json:"total,omitempty"`
	Page    int    `json:"page,omitempty"`
	PerPage int    `json:"per_page,omitempty"`
	TraceID string `json:"trace_id,omitempty"`
}

// EnqueueRequest is the request body for enqueueing tasks
type EnqueueRequest struct {
	Type       string                 `json:"type"`
	Payload    map[string]interface{} `json:"payload"`
	Priority   queue.Priority         `json:"priority"`
	MaxRetries int                    `json:"max_retries"`
	Metadata   map[string]string      `json:"metadata,omitempty"`
}

// Validate validates the enqueue request
func (r *EnqueueRequest) Validate() error {
	if r.Type == "" {
		return errors.New("task type is required")
	}
	if r.Payload == nil {
		return errors.New("payload is required")
	}
	return nil
}

// EnqueueResponse is returned after enqueueing a task
type EnqueueResponse struct {
	TaskID    string    `json:"task_id"`
	CreatedAt time.Time `json:"created_at"`
}

// Enqueue handles POST /tasks
func (h *Handler) Enqueue(w http.ResponseWriter, r *http.Request) {
	var req EnqueueRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	if err := req.Validate(); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	task := &queue.Task{
		Type:       req.Type,
		Payload:    req.Payload,
		Priority:   req.Priority,
		MaxRetries: req.MaxRetries,
		Metadata:   req.Metadata,
	}

	if err := h.queue.Enqueue(r.Context(), task); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to enqueue task: "+err.Error())
		return
	}

	// Persist to storage
	if h.storage != nil {
		if err := h.storage.SaveTask(r.Context(), task); err != nil {
			// Log but don't fail the request
		}
	}

	writeJSON(w, http.StatusCreated, Response{
		Success: true,
		Data: EnqueueResponse{
			TaskID:    task.ID,
			CreatedAt: task.CreatedAt,
		},
	})
}

// GetTask handles GET /tasks/{id}
func (h *Handler) GetTask(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		writeError(w, http.StatusBadRequest, "task id is required")
		return
	}

	task, err := h.queue.Get(r.Context(), id)
	if err != nil {
		if errors.Is(err, queue.ErrTaskNotFound) {
			writeError(w, http.StatusNotFound, "task not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    task,
	})
}

// ListTasks handles GET /tasks
func (h *Handler) ListTasks(w http.ResponseWriter, r *http.Request) {
	filter := TaskFilter{
		Limit:  50,
		Offset: 0,
	}

	// Parse query parameters
	if state := r.URL.Query().Get("state"); state != "" {
		filter.State = queue.TaskState(state)
	}
	if taskType := r.URL.Query().Get("type"); taskType != "" {
		filter.Type = taskType
	}
	if limit := r.URL.Query().Get("limit"); limit != "" {
		if l, err := strconv.Atoi(limit); err == nil && l > 0 {
			filter.Limit = l
		}
	}
	if offset := r.URL.Query().Get("offset"); offset != "" {
		if o, err := strconv.Atoi(offset); err == nil && o >= 0 {
			filter.Offset = o
		}
	}

	if h.storage == nil {
		writeError(w, http.StatusNotImplemented, "storage not configured")
		return
	}

	tasks, err := h.storage.ListTasks(r.Context(), filter)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    tasks,
		Meta: &Meta{
			Total:   len(tasks),
			PerPage: filter.Limit,
		},
	})
}

// DeleteTask handles DELETE /tasks/{id}
func (h *Handler) DeleteTask(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		writeError(w, http.StatusBadRequest, "task id is required")
		return
	}

	if err := h.queue.Delete(r.Context(), id); err != nil {
		if errors.Is(err, queue.ErrTaskNotFound) {
			writeError(w, http.StatusNotFound, "task not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
	})
}

// CancelTask handles POST /tasks/{id}/cancel
func (h *Handler) CancelTask(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		writeError(w, http.StatusBadRequest, "task id is required")
		return
	}

	task, err := h.queue.Get(r.Context(), id)
	if err != nil {
		if errors.Is(err, queue.ErrTaskNotFound) {
			writeError(w, http.StatusNotFound, "task not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	if task.State != queue.StatePending && task.State != queue.StateRetrying {
		writeError(w, http.StatusConflict, "task cannot be cancelled in current state")
		return
	}

	task.State = queue.StateCancelled
	now := time.Now()
	task.CompletedAt = &now

	if err := h.queue.Update(r.Context(), task); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    task,
	})
}

// RetryTask handles POST /tasks/{id}/retry
func (h *Handler) RetryTask(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		writeError(w, http.StatusBadRequest, "task id is required")
		return
	}

	task, err := h.queue.Get(r.Context(), id)
	if err != nil {
		if errors.Is(err, queue.ErrTaskNotFound) {
			writeError(w, http.StatusNotFound, "task not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	if task.State != queue.StateFailed {
		writeError(w, http.StatusConflict, "only failed tasks can be retried")
		return
	}

	// Reset task state
	task.State = queue.StatePending
	task.Error = ""
	task.StartedAt = nil
	task.CompletedAt = nil
	task.Retries = 0

	// Re-enqueue
	if err := h.queue.Enqueue(r.Context(), task); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    task,
	})
}

// GetStats handles GET /stats
func (h *Handler) GetStats(w http.ResponseWriter, r *http.Request) {
	var stats interface{}

	if h.pool != nil {
		stats = h.pool.Metrics()
	} else if collector, ok := h.queue.(queue.StatsCollector); ok {
		stats = collector.Stats()
	} else {
		writeError(w, http.StatusNotImplemented, "stats not available")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    stats,
	})
}

// HealthCheck handles GET /health
func (h *Handler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	status := "healthy"

	// Check queue
	if _, err := h.queue.Peek(r.Context()); err != nil && err != queue.ErrQueueEmpty {
		status = "degraded"
	}

	// Check pool
	if h.pool != nil && h.pool.State() != worker.StateRunning {
		status = "degraded"
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data: map[string]interface{}{
			"status":     status,
			"queue_size": h.queue.Len(),
			"timestamp":  time.Now().UTC(),
		},
	})
}

// BulkEnqueue handles POST /tasks/bulk
func (h *Handler) BulkEnqueue(w http.ResponseWriter, r *http.Request) {
	var requests []EnqueueRequest
	if err := json.NewDecoder(io.LimitReader(r.Body, 10<<20)).Decode(&requests); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	if len(requests) == 0 {
		writeError(w, http.StatusBadRequest, "no tasks provided")
		return
	}

	if len(requests) > 1000 {
		writeError(w, http.StatusBadRequest, "maximum 1000 tasks per bulk request")
		return
	}

	results := make([]EnqueueResponse, 0, len(requests))
	failures := make([]string, 0)

	for i, req := range requests {
		if err := req.Validate(); err != nil {
			failures = append(failures, "task "+strconv.Itoa(i)+": "+err.Error())
			continue
		}

		task := &queue.Task{
			Type:       req.Type,
			Payload:    req.Payload,
			Priority:   req.Priority,
			MaxRetries: req.MaxRetries,
			Metadata:   req.Metadata,
		}

		if err := h.queue.Enqueue(r.Context(), task); err != nil {
			failures = append(failures, "task "+strconv.Itoa(i)+": "+err.Error())
			continue
		}

		results = append(results, EnqueueResponse{
			TaskID:    task.ID,
			CreatedAt: task.CreatedAt,
		})
	}

	statusCode := http.StatusCreated
	if len(failures) > 0 {
		statusCode = http.StatusMultiStatus
	}

	writeJSON(w, statusCode, Response{
		Success: len(failures) == 0,
		Data: map[string]interface{}{
			"created":  results,
			"failures": failures,
		},
		Meta: &Meta{
			Total: len(results),
		},
	})
}

// writeJSON writes a JSON response
func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// writeError writes an error response
func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, Response{
		Success: false,
		Error:   message,
	})
}

// Router creates and configures the HTTP router
func (h *Handler) Router() http.Handler {
	mux := http.NewServeMux()

	// Task endpoints
	mux.HandleFunc("POST /tasks", h.Enqueue)
	mux.HandleFunc("POST /tasks/bulk", h.BulkEnqueue)
	mux.HandleFunc("GET /tasks", h.ListTasks)
	mux.HandleFunc("GET /tasks/{id}", h.GetTask)
	mux.HandleFunc("DELETE /tasks/{id}", h.DeleteTask)
	mux.HandleFunc("POST /tasks/{id}/cancel", h.CancelTask)
	mux.HandleFunc("POST /tasks/{id}/retry", h.RetryTask)

	// Monitoring endpoints
	mux.HandleFunc("GET /stats", h.GetStats)
	mux.HandleFunc("GET /health", h.HealthCheck)

	return mux
}
