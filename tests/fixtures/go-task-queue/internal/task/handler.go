// Package task provides task handling abstractions with generics support.
package task

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"reflect"
	"time"

	"github.com/example/task-queue/internal/queue"
)

// Common handler errors
var (
	ErrHandlerNotFound = errors.New("handler not found for task type")
	ErrPayloadDecode   = errors.New("failed to decode task payload")
	ErrHandlerPanic    = errors.New("handler panicked")
	ErrHandlerTimeout  = errors.New("handler execution timed out")
)

// Handler is a generic interface for task handlers
type Handler[T any, R any] interface {
	// Handle processes the task and returns a result
	Handle(ctx context.Context, payload T) (R, error)

	// TaskType returns the type identifier for this handler
	TaskType() string

	// Timeout returns the maximum execution time
	Timeout() time.Duration
}

// HandlerFunc is a function adapter for Handler interface
type HandlerFunc[T any, R any] struct {
	taskType string
	timeout  time.Duration
	fn       func(context.Context, T) (R, error)
}

// NewHandlerFunc creates a new handler from a function
func NewHandlerFunc[T any, R any](taskType string, timeout time.Duration, fn func(context.Context, T) (R, error)) *HandlerFunc[T, R] {
	return &HandlerFunc[T, R]{
		taskType: taskType,
		timeout:  timeout,
		fn:       fn,
	}
}

// Handle implements Handler interface
func (h *HandlerFunc[T, R]) Handle(ctx context.Context, payload T) (R, error) {
	return h.fn(ctx, payload)
}

// TaskType implements Handler interface
func (h *HandlerFunc[T, R]) TaskType() string {
	return h.taskType
}

// Timeout implements Handler interface
func (h *HandlerFunc[T, R]) Timeout() time.Duration {
	return h.timeout
}

// RawHandler is a non-generic handler interface for type erasure
type RawHandler interface {
	HandleRaw(ctx context.Context, payload map[string]interface{}) (interface{}, error)
	TaskType() string
	Timeout() time.Duration
}

// TypedHandler wraps a generic handler for type erasure
type TypedHandler[T any, R any] struct {
	handler Handler[T, R]
}

// WrapHandler wraps a generic handler into a RawHandler
func WrapHandler[T any, R any](h Handler[T, R]) RawHandler {
	return &TypedHandler[T, R]{handler: h}
}

// HandleRaw implements RawHandler with JSON marshaling
func (th *TypedHandler[T, R]) HandleRaw(ctx context.Context, payload map[string]interface{}) (interface{}, error) {
	// Marshal to JSON then unmarshal to typed struct
	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrPayloadDecode, err)
	}

	var typed T
	if err := json.Unmarshal(jsonBytes, &typed); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrPayloadDecode, err)
	}

	return th.handler.Handle(ctx, typed)
}

// TaskType implements RawHandler
func (th *TypedHandler[T, R]) TaskType() string {
	return th.handler.TaskType()
}

// Timeout implements RawHandler
func (th *TypedHandler[T, R]) Timeout() time.Duration {
	return th.handler.Timeout()
}

// Registry maintains a map of task types to handlers
type Registry struct {
	handlers map[string]RawHandler
	hooks    []Hook
}

// Hook is called during task lifecycle
type Hook interface {
	BeforeExecute(ctx context.Context, task *queue.Task) error
	AfterExecute(ctx context.Context, task *queue.Task, result interface{}, err error)
}

// HookFunc is a function adapter for hooks
type HookFunc struct {
	before func(context.Context, *queue.Task) error
	after  func(context.Context, *queue.Task, interface{}, error)
}

// BeforeExecute implements Hook
func (h *HookFunc) BeforeExecute(ctx context.Context, task *queue.Task) error {
	if h.before != nil {
		return h.before(ctx, task)
	}
	return nil
}

// AfterExecute implements Hook
func (h *HookFunc) AfterExecute(ctx context.Context, task *queue.Task, result interface{}, err error) {
	if h.after != nil {
		h.after(ctx, task, result, err)
	}
}

// NewRegistry creates a new handler registry
func NewRegistry() *Registry {
	return &Registry{
		handlers: make(map[string]RawHandler),
		hooks:    make([]Hook, 0),
	}
}

// Register adds a handler to the registry
func (r *Registry) Register(h RawHandler) {
	r.handlers[h.TaskType()] = h
}

// RegisterFunc registers a handler function
func RegisterFunc[T any, R any](r *Registry, taskType string, timeout time.Duration, fn func(context.Context, T) (R, error)) {
	handler := NewHandlerFunc(taskType, timeout, fn)
	r.Register(WrapHandler(handler))
}

// Get retrieves a handler by task type
func (r *Registry) Get(taskType string) (RawHandler, bool) {
	h, ok := r.handlers[taskType]
	return h, ok
}

// AddHook adds a lifecycle hook
func (r *Registry) AddHook(h Hook) {
	r.hooks = append(r.hooks, h)
}

// Execute runs a task with the appropriate handler
func (r *Registry) Execute(ctx context.Context, task *queue.Task) (interface{}, error) {
	handler, ok := r.handlers[task.Type]
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrHandlerNotFound, task.Type)
	}

	// Run before hooks
	for _, hook := range r.hooks {
		if err := hook.BeforeExecute(ctx, task); err != nil {
			return nil, err
		}
	}

	// Set up timeout context
	timeout := handler.Timeout()
	if timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, timeout)
		defer cancel()
	}

	// Execute with panic recovery
	var result interface{}
	var execErr error

	done := make(chan struct{})
	go func() {
		defer func() {
			if r := recover(); r != nil {
				execErr = fmt.Errorf("%w: %v", ErrHandlerPanic, r)
			}
			close(done)
		}()
		result, execErr = handler.HandleRaw(ctx, task.Payload)
	}()

	select {
	case <-ctx.Done():
		execErr = ErrHandlerTimeout
	case <-done:
		// Normal completion
	}

	// Run after hooks
	for _, hook := range r.hooks {
		hook.AfterExecute(ctx, task, result, execErr)
	}

	return result, execErr
}

// Types returns all registered task types
func (r *Registry) Types() []string {
	types := make([]string, 0, len(r.handlers))
	for t := range r.handlers {
		types = append(types, t)
	}
	return types
}

// Middleware wraps a handler with additional functionality
type Middleware func(RawHandler) RawHandler

// WithRetry wraps a handler with retry logic
func WithRetry(maxRetries int, backoff time.Duration) Middleware {
	return func(next RawHandler) RawHandler {
		return &retryHandler{
			next:       next,
			maxRetries: maxRetries,
			backoff:    backoff,
		}
	}
}

type retryHandler struct {
	next       RawHandler
	maxRetries int
	backoff    time.Duration
}

func (r *retryHandler) HandleRaw(ctx context.Context, payload map[string]interface{}) (interface{}, error) {
	var lastErr error
	for i := 0; i <= r.maxRetries; i++ {
		result, err := r.next.HandleRaw(ctx, payload)
		if err == nil {
			return result, nil
		}
		lastErr = err
		if i < r.maxRetries {
			time.Sleep(r.backoff * time.Duration(i+1))
		}
	}
	return nil, lastErr
}

func (r *retryHandler) TaskType() string    { return r.next.TaskType() }
func (r *retryHandler) Timeout() time.Duration { return r.next.Timeout() }

// WithLogging wraps a handler with logging
func WithLogging(logger Logger) Middleware {
	return func(next RawHandler) RawHandler {
		return &loggingHandler{
			next:   next,
			logger: logger,
		}
	}
}

// Logger interface for task logging
type Logger interface {
	Info(msg string, fields map[string]interface{})
	Error(msg string, err error, fields map[string]interface{})
}

type loggingHandler struct {
	next   RawHandler
	logger Logger
}

func (l *loggingHandler) HandleRaw(ctx context.Context, payload map[string]interface{}) (interface{}, error) {
	start := time.Now()
	l.logger.Info("task started", map[string]interface{}{
		"type": l.next.TaskType(),
	})

	result, err := l.next.HandleRaw(ctx, payload)

	fields := map[string]interface{}{
		"type":     l.next.TaskType(),
		"duration": time.Since(start).String(),
	}

	if err != nil {
		l.logger.Error("task failed", err, fields)
	} else {
		l.logger.Info("task completed", fields)
	}

	return result, err
}

func (l *loggingHandler) TaskType() string    { return l.next.TaskType() }
func (l *loggingHandler) Timeout() time.Duration { return l.next.Timeout() }

// PayloadValidator validates task payloads
type PayloadValidator interface {
	Validate(payload map[string]interface{}) error
}

// ValidatorFunc is a function adapter for PayloadValidator
type ValidatorFunc func(map[string]interface{}) error

func (f ValidatorFunc) Validate(payload map[string]interface{}) error {
	return f(payload)
}

// WithValidation wraps a handler with payload validation
func WithValidation(validator PayloadValidator) Middleware {
	return func(next RawHandler) RawHandler {
		return &validatingHandler{
			next:      next,
			validator: validator,
		}
	}
}

type validatingHandler struct {
	next      RawHandler
	validator PayloadValidator
}

func (v *validatingHandler) HandleRaw(ctx context.Context, payload map[string]interface{}) (interface{}, error) {
	if err := v.validator.Validate(payload); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}
	return v.next.HandleRaw(ctx, payload)
}

func (v *validatingHandler) TaskType() string    { return v.next.TaskType() }
func (v *validatingHandler) Timeout() time.Duration { return v.next.Timeout() }

// Chain applies multiple middlewares to a handler
func Chain(h RawHandler, middlewares ...Middleware) RawHandler {
	for i := len(middlewares) - 1; i >= 0; i-- {
		h = middlewares[i](h)
	}
	return h
}

// GetTypeName returns the type name using reflection
func GetTypeName(v interface{}) string {
	t := reflect.TypeOf(v)
	if t.Kind() == reflect.Ptr {
		t = t.Elem()
	}
	return t.Name()
}
