// Package client provides a Go client library for the task queue API.
package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// Client is a task queue API client
type Client struct {
	baseURL    string
	httpClient *http.Client
	apiKey     string
}

// Option is a client configuration option
type Option func(*Client)

// WithTimeout sets the HTTP client timeout
func WithTimeout(d time.Duration) Option {
	return func(c *Client) {
		c.httpClient.Timeout = d
	}
}

// WithAPIKey sets the API key for authentication
func WithAPIKey(key string) Option {
	return func(c *Client) {
		c.apiKey = key
	}
}

// WithHTTPClient sets a custom HTTP client
func WithHTTPClient(hc *http.Client) Option {
	return func(c *Client) {
		c.httpClient = hc
	}
}

// New creates a new client
func New(baseURL string, opts ...Option) *Client {
	c := &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}

	for _, opt := range opts {
		opt(c)
	}

	return c
}

// Task represents a task
type Task struct {
	ID          string                 `json:"id"`
	Type        string                 `json:"type"`
	Payload     map[string]interface{} `json:"payload"`
	Priority    int                    `json:"priority"`
	State       string                 `json:"state"`
	CreatedAt   time.Time              `json:"created_at"`
	StartedAt   *time.Time             `json:"started_at,omitempty"`
	CompletedAt *time.Time             `json:"completed_at,omitempty"`
	Retries     int                    `json:"retries"`
	MaxRetries  int                    `json:"max_retries"`
	Error       string                 `json:"error,omitempty"`
	Result      interface{}            `json:"result,omitempty"`
	Metadata    map[string]string      `json:"metadata,omitempty"`
}

// EnqueueRequest is the request to enqueue a task
type EnqueueRequest struct {
	Type       string                 `json:"type"`
	Payload    map[string]interface{} `json:"payload"`
	Priority   int                    `json:"priority,omitempty"`
	MaxRetries int                    `json:"max_retries,omitempty"`
	Metadata   map[string]string      `json:"metadata,omitempty"`
}

// EnqueueResponse is the response from enqueueing a task
type EnqueueResponse struct {
	TaskID    string    `json:"task_id"`
	CreatedAt time.Time `json:"created_at"`
}

// ListOptions specifies options for listing tasks
type ListOptions struct {
	State  string
	Type   string
	Limit  int
	Offset int
}

// Stats contains queue statistics
type Stats struct {
	TasksProcessed  int64         `json:"tasks_processed"`
	TasksFailed     int64         `json:"tasks_failed"`
	TasksRetried    int64         `json:"tasks_retried"`
	ActiveWorkers   int           `json:"active_workers"`
	QueueDepth      int           `json:"queue_depth"`
	AvgTaskDuration time.Duration `json:"avg_task_duration"`
}

// HealthStatus contains health check response
type HealthStatus struct {
	Status    string    `json:"status"`
	QueueSize int       `json:"queue_size"`
	Timestamp time.Time `json:"timestamp"`
}

// apiResponse is the standard API response wrapper
type apiResponse struct {
	Success bool            `json:"success"`
	Data    json.RawMessage `json:"data,omitempty"`
	Error   string          `json:"error,omitempty"`
}

// Error represents an API error
type Error struct {
	StatusCode int
	Message    string
}

func (e *Error) Error() string {
	return fmt.Sprintf("API error (%d): %s", e.StatusCode, e.Message)
}

// do performs an HTTP request
func (c *Client) do(ctx context.Context, method, path string, body interface{}) ([]byte, error) {
	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request: %w", err)
		}
		bodyReader = bytes.NewReader(data)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	if c.apiKey != "" {
		req.Header.Set("Authorization", c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	return respBody, nil
}

// parseResponse parses the API response
func parseResponse[T any](data []byte) (T, error) {
	var result T
	var resp apiResponse

	if err := json.Unmarshal(data, &resp); err != nil {
		return result, fmt.Errorf("failed to parse response: %w", err)
	}

	if !resp.Success {
		return result, &Error{Message: resp.Error}
	}

	if len(resp.Data) > 0 {
		if err := json.Unmarshal(resp.Data, &result); err != nil {
			return result, fmt.Errorf("failed to parse data: %w", err)
		}
	}

	return result, nil
}

// Enqueue enqueues a new task
func (c *Client) Enqueue(ctx context.Context, req EnqueueRequest) (*EnqueueResponse, error) {
	data, err := c.do(ctx, http.MethodPost, "/tasks", req)
	if err != nil {
		return nil, err
	}

	result, err := parseResponse[EnqueueResponse](data)
	if err != nil {
		return nil, err
	}

	return &result, nil
}

// Get retrieves a task by ID
func (c *Client) Get(ctx context.Context, id string) (*Task, error) {
	data, err := c.do(ctx, http.MethodGet, "/tasks/"+id, nil)
	if err != nil {
		return nil, err
	}

	result, err := parseResponse[Task](data)
	if err != nil {
		return nil, err
	}

	return &result, nil
}

// List lists tasks with optional filters
func (c *Client) List(ctx context.Context, opts ListOptions) ([]Task, error) {
	path := "/tasks"

	params := url.Values{}
	if opts.State != "" {
		params.Set("state", opts.State)
	}
	if opts.Type != "" {
		params.Set("type", opts.Type)
	}
	if opts.Limit > 0 {
		params.Set("limit", fmt.Sprintf("%d", opts.Limit))
	}
	if opts.Offset > 0 {
		params.Set("offset", fmt.Sprintf("%d", opts.Offset))
	}

	if len(params) > 0 {
		path += "?" + params.Encode()
	}

	data, err := c.do(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	result, err := parseResponse[[]Task](data)
	if err != nil {
		return nil, err
	}

	return result, nil
}

// Cancel cancels a pending task
func (c *Client) Cancel(ctx context.Context, id string) (*Task, error) {
	data, err := c.do(ctx, http.MethodPost, "/tasks/"+id+"/cancel", nil)
	if err != nil {
		return nil, err
	}

	result, err := parseResponse[Task](data)
	if err != nil {
		return nil, err
	}

	return &result, nil
}

// Retry retries a failed task
func (c *Client) Retry(ctx context.Context, id string) (*Task, error) {
	data, err := c.do(ctx, http.MethodPost, "/tasks/"+id+"/retry", nil)
	if err != nil {
		return nil, err
	}

	result, err := parseResponse[Task](data)
	if err != nil {
		return nil, err
	}

	return &result, nil
}

// Delete deletes a task
func (c *Client) Delete(ctx context.Context, id string) error {
	data, err := c.do(ctx, http.MethodDelete, "/tasks/"+id, nil)
	if err != nil {
		return err
	}

	_, err = parseResponse[struct{}](data)
	return err
}

// BulkEnqueue enqueues multiple tasks
func (c *Client) BulkEnqueue(ctx context.Context, reqs []EnqueueRequest) ([]EnqueueResponse, []string, error) {
	data, err := c.do(ctx, http.MethodPost, "/tasks/bulk", reqs)
	if err != nil {
		return nil, nil, err
	}

	var result struct {
		Created  []EnqueueResponse `json:"created"`
		Failures []string          `json:"failures"`
	}

	if err := json.Unmarshal(data, &struct {
		Data *struct {
			Created  []EnqueueResponse `json:"created"`
			Failures []string          `json:"failures"`
		} `json:"data"`
	}{Data: &result}); err != nil {
		return nil, nil, fmt.Errorf("failed to parse bulk response: %w", err)
	}

	return result.Created, result.Failures, nil
}

// Stats returns queue statistics
func (c *Client) Stats(ctx context.Context) (*Stats, error) {
	data, err := c.do(ctx, http.MethodGet, "/stats", nil)
	if err != nil {
		return nil, err
	}

	result, err := parseResponse[Stats](data)
	if err != nil {
		return nil, err
	}

	return &result, nil
}

// Health checks server health
func (c *Client) Health(ctx context.Context) (*HealthStatus, error) {
	data, err := c.do(ctx, http.MethodGet, "/health", nil)
	if err != nil {
		return nil, err
	}

	result, err := parseResponse[HealthStatus](data)
	if err != nil {
		return nil, err
	}

	return &result, nil
}

// Wait waits for a task to complete
func (c *Client) Wait(ctx context.Context, id string, pollInterval time.Duration) (*Task, error) {
	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-ticker.C:
			task, err := c.Get(ctx, id)
			if err != nil {
				return nil, err
			}

			switch task.State {
			case "completed", "failed", "cancelled":
				return task, nil
			}
		}
	}
}
