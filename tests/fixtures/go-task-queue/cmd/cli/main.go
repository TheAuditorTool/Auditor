// Package main provides the task queue CLI client.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// Global configuration
var (
	baseURL string
	timeout time.Duration
	verbose bool
)

func init() {
	flag.StringVar(&baseURL, "url", "http://localhost:8080", "Task queue server URL")
	flag.DurationVar(&timeout, "timeout", 30*time.Second, "Request timeout")
	flag.BoolVar(&verbose, "verbose", false, "Verbose output")
}

func main() {
	flag.Parse()

	if len(flag.Args()) < 1 {
		printUsage()
		os.Exit(1)
	}

	cmd := flag.Args()[0]
	args := flag.Args()[1:]

	var err error
	switch cmd {
	case "enqueue":
		err = cmdEnqueue(args)
	case "get":
		err = cmdGet(args)
	case "list":
		err = cmdList(args)
	case "cancel":
		err = cmdCancel(args)
	case "retry":
		err = cmdRetry(args)
	case "delete":
		err = cmdDelete(args)
	case "stats":
		err = cmdStats(args)
	case "health":
		err = cmdHealth(args)
	case "bulk":
		err = cmdBulk(args)
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n", cmd)
		printUsage()
		os.Exit(1)
	}

	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("Task Queue CLI")
	fmt.Println()
	fmt.Println("Usage: taskq [options] <command> [args]")
	fmt.Println()
	fmt.Println("Commands:")
	fmt.Println("  enqueue <type> <payload>  Enqueue a new task")
	fmt.Println("  get <id>                  Get task details")
	fmt.Println("  list [--state=<state>]    List tasks")
	fmt.Println("  cancel <id>               Cancel a pending task")
	fmt.Println("  retry <id>                Retry a failed task")
	fmt.Println("  delete <id>               Delete a task")
	fmt.Println("  stats                     Show queue statistics")
	fmt.Println("  health                    Check server health")
	fmt.Println("  bulk <file>               Enqueue tasks from JSON file")
	fmt.Println()
	fmt.Println("Options:")
	flag.PrintDefaults()
}

// Client handles HTTP requests
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// NewClient creates a new client
func NewClient(baseURL string, timeout time.Duration) *Client {
	return &Client{
		baseURL: strings.TrimSuffix(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

// Request makes an HTTP request
func (c *Client) Request(method, path string, body interface{}) ([]byte, error) {
	url := c.baseURL + path

	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal body: %w", err)
		}
		bodyReader = bytes.NewReader(data)
	}

	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	if verbose {
		fmt.Printf("%s %s\n", method, url)
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

	if verbose {
		fmt.Printf("Response: %d\n", resp.StatusCode)
	}

	return respBody, nil
}

// Response is the standard API response
type Response struct {
	Success bool            `json:"success"`
	Data    json.RawMessage `json:"data,omitempty"`
	Error   string          `json:"error,omitempty"`
}

func parseResponse(data []byte, v interface{}) error {
	var resp Response
	if err := json.Unmarshal(data, &resp); err != nil {
		return fmt.Errorf("failed to parse response: %w", err)
	}

	if !resp.Success {
		return fmt.Errorf("API error: %s", resp.Error)
	}

	if v != nil && len(resp.Data) > 0 {
		if err := json.Unmarshal(resp.Data, v); err != nil {
			return fmt.Errorf("failed to parse data: %w", err)
		}
	}

	return nil
}

func cmdEnqueue(args []string) error {
	if len(args) < 2 {
		return fmt.Errorf("usage: enqueue <type> <payload_json>")
	}

	taskType := args[0]
	payloadStr := strings.Join(args[1:], " ")

	var payload map[string]interface{}
	if err := json.Unmarshal([]byte(payloadStr), &payload); err != nil {
		return fmt.Errorf("invalid payload JSON: %w", err)
	}

	client := NewClient(baseURL, timeout)
	resp, err := client.Request("POST", "/tasks", map[string]interface{}{
		"type":    taskType,
		"payload": payload,
	})
	if err != nil {
		return err
	}

	var result struct {
		TaskID    string    `json:"task_id"`
		CreatedAt time.Time `json:"created_at"`
	}
	if err := parseResponse(resp, &result); err != nil {
		return err
	}

	fmt.Printf("Task enqueued: %s\n", result.TaskID)
	fmt.Printf("Created at: %s\n", result.CreatedAt.Format(time.RFC3339))
	return nil
}

func cmdGet(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: get <task_id>")
	}

	taskID := args[0]
	client := NewClient(baseURL, timeout)

	resp, err := client.Request("GET", "/tasks/"+taskID, nil)
	if err != nil {
		return err
	}

	var task map[string]interface{}
	if err := parseResponse(resp, &task); err != nil {
		return err
	}

	output, _ := json.MarshalIndent(task, "", "  ")
	fmt.Println(string(output))
	return nil
}

func cmdList(args []string) error {
	fs := flag.NewFlagSet("list", flag.ExitOnError)
	state := fs.String("state", "", "Filter by state")
	taskType := fs.String("type", "", "Filter by type")
	limit := fs.Int("limit", 50, "Maximum results")
	fs.Parse(args)

	path := fmt.Sprintf("/tasks?limit=%d", *limit)
	if *state != "" {
		path += "&state=" + *state
	}
	if *taskType != "" {
		path += "&type=" + *taskType
	}

	client := NewClient(baseURL, timeout)
	resp, err := client.Request("GET", path, nil)
	if err != nil {
		return err
	}

	var tasks []map[string]interface{}
	if err := parseResponse(resp, &tasks); err != nil {
		return err
	}

	if len(tasks) == 0 {
		fmt.Println("No tasks found")
		return nil
	}

	// Print as table
	fmt.Printf("%-36s %-15s %-12s %-20s\n", "ID", "TYPE", "STATE", "CREATED")
	fmt.Println(strings.Repeat("-", 85))
	for _, task := range tasks {
		id, _ := task["id"].(string)
		taskType, _ := task["type"].(string)
		state, _ := task["state"].(string)
		createdAt, _ := task["created_at"].(string)

		t, _ := time.Parse(time.RFC3339, createdAt)
		fmt.Printf("%-36s %-15s %-12s %-20s\n", id, taskType, state, t.Format("2006-01-02 15:04:05"))
	}

	fmt.Printf("\nTotal: %d tasks\n", len(tasks))
	return nil
}

func cmdCancel(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: cancel <task_id>")
	}

	taskID := args[0]
	client := NewClient(baseURL, timeout)

	resp, err := client.Request("POST", "/tasks/"+taskID+"/cancel", nil)
	if err != nil {
		return err
	}

	if err := parseResponse(resp, nil); err != nil {
		return err
	}

	fmt.Printf("Task %s cancelled\n", taskID)
	return nil
}

func cmdRetry(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: retry <task_id>")
	}

	taskID := args[0]
	client := NewClient(baseURL, timeout)

	resp, err := client.Request("POST", "/tasks/"+taskID+"/retry", nil)
	if err != nil {
		return err
	}

	if err := parseResponse(resp, nil); err != nil {
		return err
	}

	fmt.Printf("Task %s retried\n", taskID)
	return nil
}

func cmdDelete(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: delete <task_id>")
	}

	taskID := args[0]
	client := NewClient(baseURL, timeout)

	resp, err := client.Request("DELETE", "/tasks/"+taskID, nil)
	if err != nil {
		return err
	}

	if err := parseResponse(resp, nil); err != nil {
		return err
	}

	fmt.Printf("Task %s deleted\n", taskID)
	return nil
}

func cmdStats(args []string) error {
	client := NewClient(baseURL, timeout)

	resp, err := client.Request("GET", "/stats", nil)
	if err != nil {
		return err
	}

	var stats map[string]interface{}
	if err := parseResponse(resp, &stats); err != nil {
		return err
	}

	output, _ := json.MarshalIndent(stats, "", "  ")
	fmt.Println(string(output))
	return nil
}

func cmdHealth(args []string) error {
	client := NewClient(baseURL, timeout)

	resp, err := client.Request("GET", "/health", nil)
	if err != nil {
		return err
	}

	var health map[string]interface{}
	if err := parseResponse(resp, &health); err != nil {
		return err
	}

	status, _ := health["status"].(string)
	queueSize, _ := health["queue_size"].(float64)

	fmt.Printf("Status: %s\n", status)
	fmt.Printf("Queue size: %.0f\n", queueSize)
	return nil
}

func cmdBulk(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: bulk <json_file>")
	}

	filename := args[0]
	data, err := os.ReadFile(filename)
	if err != nil {
		return fmt.Errorf("failed to read file: %w", err)
	}

	var tasks []map[string]interface{}
	if err := json.Unmarshal(data, &tasks); err != nil {
		return fmt.Errorf("invalid JSON: %w", err)
	}

	client := NewClient(baseURL, timeout)
	resp, err := client.Request("POST", "/tasks/bulk", tasks)
	if err != nil {
		return err
	}

	var result struct {
		Created  []interface{} `json:"created"`
		Failures []string      `json:"failures"`
	}
	if err := parseResponse(resp, &result); err != nil {
		return err
	}

	fmt.Printf("Created: %d tasks\n", len(result.Created))
	if len(result.Failures) > 0 {
		fmt.Printf("Failures: %d\n", len(result.Failures))
		for _, f := range result.Failures {
			fmt.Printf("  - %s\n", f)
		}
	}

	return nil
}
