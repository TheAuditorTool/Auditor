// Package vulnerable contains intentional security anti-patterns for taint analysis testing.
// DO NOT USE IN PRODUCTION - these patterns demonstrate vulnerabilities.
package vulnerable

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/example/task-queue/internal/queue"
)

// ============================================================================
// SQL INJECTION PATTERNS
// ============================================================================

// SQLInjectionDirect demonstrates direct SQL injection via string concatenation.
// TAINT: req.URL.Query().Get("id") -> fmt.Sprintf -> db.Query (SQL sink)
func SQLInjectionDirect(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	// SOURCE: User input from query parameter
	userID := r.URL.Query().Get("id")

	// SINK: SQL injection via string concatenation
	query := fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", userID)
	rows, err := db.Query(query)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	defer rows.Close()

	json.NewEncoder(w).Encode(rows)
}

// SQLInjectionInterpolated demonstrates SQL injection with string interpolation.
// TAINT: r.FormValue("name") -> query string -> db.Exec (SQL sink)
func SQLInjectionInterpolated(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	// SOURCE: Form value
	name := r.FormValue("name")
	email := r.FormValue("email")

	// SINK: SQL injection via fmt.Sprintf in INSERT
	query := fmt.Sprintf("INSERT INTO users (name, email) VALUES ('%s', '%s')", name, email)
	_, err := db.Exec(query)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	w.WriteHeader(http.StatusCreated)
}

// SQLInjectionViaVariable demonstrates SQL injection through intermediate variable.
// TAINT: r.Header.Get("X-Filter") -> filter -> query -> db.Query
func SQLInjectionViaVariable(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	// SOURCE: HTTP header
	filter := r.Header.Get("X-Filter")

	// Intermediate assignment (taint should propagate)
	whereClause := "WHERE status = '" + filter + "'"

	// Another intermediate
	query := "SELECT * FROM tasks " + whereClause

	// SINK: SQL query
	rows, _ := db.Query(query)
	defer rows.Close()
}

// SQLInjectionOrderBy demonstrates SQL injection in ORDER BY clause.
// TAINT: r.URL.Query().Get("sort") -> ORDER BY -> db.Query
func SQLInjectionOrderBy(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	sortField := r.URL.Query().Get("sort")
	sortOrder := r.URL.Query().Get("order")

	// SINK: SQL injection in ORDER BY (can't use parameterized here)
	query := fmt.Sprintf("SELECT * FROM tasks ORDER BY %s %s", sortField, sortOrder)
	db.Query(query)
}

// ============================================================================
// COMMAND INJECTION PATTERNS
// ============================================================================

// CommandInjectionDirect demonstrates direct command injection.
// TAINT: r.URL.Query().Get("file") -> exec.Command (command sink)
func CommandInjectionDirect(w http.ResponseWriter, r *http.Request) {
	// SOURCE: Query parameter
	filename := r.URL.Query().Get("file")

	// SINK: Command injection via string concatenation
	cmd := exec.Command("bash", "-c", "cat "+filename)
	output, err := cmd.Output()
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	w.Write(output)
}

// CommandInjectionViaBody demonstrates command injection via request body.
// TAINT: json.Decode(r.Body) -> payload.Command -> exec.Command
func CommandInjectionViaBody(w http.ResponseWriter, r *http.Request) {
	var payload struct {
		Command string `json:"command"`
		Args    string `json:"args"`
	}

	// SOURCE: Request body
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}

	// SINK: Command injection
	cmd := exec.Command(payload.Command, payload.Args)
	cmd.Run()
}

// CommandInjectionPipelined demonstrates command through pipe.
// TAINT: r.PostFormValue("script") -> exec.Command with pipe
func CommandInjectionPipelined(w http.ResponseWriter, r *http.Request) {
	script := r.PostFormValue("script")

	// SINK: Piped command execution
	cmd := exec.Command("bash")
	stdin, _ := cmd.StdinPipe()
	go func() {
		defer stdin.Close()
		io.WriteString(stdin, script) // Taint flows through pipe
	}()
	cmd.Run()
}

// ============================================================================
// PATH TRAVERSAL PATTERNS
// ============================================================================

// PathTraversalDirect demonstrates direct path traversal.
// TAINT: r.URL.Query().Get("path") -> filepath.Join -> os.ReadFile
func PathTraversalDirect(w http.ResponseWriter, r *http.Request) {
	// SOURCE: Query parameter
	userPath := r.URL.Query().Get("path")

	// SINK: Path traversal - "../../../etc/passwd" could escape
	fullPath := filepath.Join("/var/data", userPath)
	data, err := os.ReadFile(fullPath)
	if err != nil {
		http.Error(w, err.Error(), 404)
		return
	}

	w.Write(data)
}

// PathTraversalWrite demonstrates path traversal in file write.
// TAINT: r.FormValue("filename") -> os.Create (file write sink)
func PathTraversalWrite(w http.ResponseWriter, r *http.Request) {
	filename := r.FormValue("filename")
	content := r.FormValue("content")

	// SINK: Path traversal in file creation
	path := "/uploads/" + filename
	file, err := os.Create(path)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	defer file.Close()

	file.WriteString(content)
}

// ============================================================================
// TEMPLATE INJECTION PATTERNS
// ============================================================================

// TemplateInjectionHTML demonstrates HTML template injection.
// TAINT: r.FormValue("content") -> template.HTML (XSS sink)
func TemplateInjectionHTML(w http.ResponseWriter, r *http.Request) {
	// SOURCE: Form value
	userContent := r.FormValue("content")

	// SINK: Bypasses HTML escaping
	safeContent := template.HTML(userContent)

	tmpl := template.Must(template.New("page").Parse(`<div>{{.}}</div>`))
	tmpl.Execute(w, safeContent)
}

// TemplateInjectionJS demonstrates JS template injection.
// TAINT: r.URL.Query().Get("callback") -> template.JS (XSS sink)
func TemplateInjectionJS(w http.ResponseWriter, r *http.Request) {
	callback := r.URL.Query().Get("callback")

	// SINK: JavaScript injection
	jsCode := template.JS(callback + "(data)")

	tmpl := template.Must(template.New("js").Parse(`<script>{{.}}</script>`))
	tmpl.Execute(w, jsCode)
}

// ============================================================================
// CROSS-GOROUTINE TAINT PROPAGATION
// ============================================================================

// TaintThroughChannel demonstrates taint flowing through channels.
// TAINT: r.Body -> channel -> db.Exec (cross-goroutine flow)
func TaintThroughChannel(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	// Channel for passing tainted data
	dataChan := make(chan string, 1)

	// SOURCE: Request body
	body, _ := io.ReadAll(r.Body)
	taintedData := string(body)

	// Send tainted data through channel
	go func() {
		dataChan <- taintedData
	}()

	// Receive and use tainted data
	go func() {
		received := <-dataChan
		// SINK: SQL injection from channel data
		query := "INSERT INTO logs (data) VALUES ('" + received + "')"
		db.Exec(query)
	}()
}

// TaintThroughBufferedChannel demonstrates buffered channel taint flow.
// TAINT: query params -> buffered channel -> multiple sinks
func TaintThroughBufferedChannel(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	queries := make(chan string, 10)

	// SOURCE: Multiple query parameters
	for key, values := range r.URL.Query() {
		for _, val := range values {
			// Tainted query construction
			q := fmt.Sprintf("UPDATE config SET %s = '%s'", key, val)
			queries <- q
		}
	}
	close(queries)

	// Worker consumes tainted queries
	for query := range queries {
		// SINK: SQL injection
		db.Exec(query)
	}
}

// ============================================================================
// INTERFACE-BASED TAINT PROPAGATION
// ============================================================================

// DataSource is an interface for taint source abstraction
type DataSource interface {
	GetData() string
}

// HTTPSource implements DataSource from HTTP request
type HTTPSource struct {
	Request *http.Request
}

// GetData returns tainted data from HTTP request
func (s *HTTPSource) GetData() string {
	return s.Request.URL.Query().Get("data")
}

// ProcessSource demonstrates taint through interface dispatch.
// TAINT: DataSource.GetData() -> db.Query (interface method dispatch)
func ProcessSource(db *sql.DB, source DataSource) {
	// Taint flows through interface method
	data := source.GetData()

	// SINK: SQL injection via interface
	query := "SELECT * FROM items WHERE name = '" + data + "'"
	db.Query(query)
}

// ============================================================================
// CLOSURE TAINT CAPTURE
// ============================================================================

// TaintInClosure demonstrates taint captured by closure.
// TAINT: r.FormValue -> closure capture -> db.Exec
func TaintInClosure(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	// SOURCE: Form value
	userInput := r.FormValue("input")

	// Closure captures tainted variable
	process := func() {
		// SINK: Tainted data from closure
		query := "DELETE FROM items WHERE id = '" + userInput + "'"
		db.Exec(query)
	}

	// Execute closure
	process()
}

// TaintInDeferredClosure demonstrates taint in deferred closure.
// TAINT: r.Header -> deferred closure -> os.WriteFile
func TaintInDeferredClosure(w http.ResponseWriter, r *http.Request) {
	// SOURCE: HTTP header
	logData := r.Header.Get("X-Log-Data")

	// Deferred closure with tainted data
	defer func() {
		// SINK: File write with tainted path/content
		os.WriteFile("/var/log/app/"+logData+".log", []byte(logData), 0644)
	}()

	w.Write([]byte("OK"))
}

// ============================================================================
// TASK QUEUE SPECIFIC TAINT PATTERNS
// ============================================================================

// VulnerableTaskHandler demonstrates taint through task queue payload.
// TAINT: task.Payload -> SQL sink (simulates real task processing)
func VulnerableTaskHandler(db *sql.DB, task *queue.Task) error {
	// SOURCE: Task payload from queue (originally from HTTP)
	target := task.Payload["target"].(string)
	action := task.Payload["action"].(string)

	// SINK: SQL injection in task handler
	query := fmt.Sprintf("UPDATE resources SET status = '%s' WHERE name = '%s'", action, target)
	_, err := db.Exec(query)
	return err
}

// VulnerableTaskWithCommand demonstrates command injection in task.
// TAINT: task.Payload["command"] -> exec.Command
func VulnerableTaskWithCommand(task *queue.Task) error {
	command := task.Payload["command"].(string)
	args := task.Payload["args"].(string)

	// SINK: Command injection from task payload
	cmd := exec.Command("sh", "-c", command+" "+args)
	return cmd.Run()
}

// ============================================================================
// MULTI-HOP TAINT PROPAGATION
// ============================================================================

// Helper that passes through taint
func processInput(input string) string {
	// Taint should propagate through
	return "processed: " + input
}

// Another helper in the chain
func formatForQuery(data string) string {
	return "'" + data + "'"
}

// MultiHopTaint demonstrates taint through multiple function calls.
// TAINT: r.FormValue -> processInput -> formatForQuery -> db.Query
func MultiHopTaint(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	// SOURCE: Form input
	raw := r.FormValue("data")

	// Hop 1: Process
	processed := processInput(raw)

	// Hop 2: Format
	formatted := formatForQuery(processed)

	// SINK: SQL with multi-hop tainted data
	query := "SELECT * FROM data WHERE value = " + formatted
	db.Query(query)
}

// ============================================================================
// STRUCT FIELD TAINT PROPAGATION
// ============================================================================

// UserInput holds tainted user data
type UserInput struct {
	Name    string
	Email   string
	Comment string
}

// StructFieldTaint demonstrates taint through struct fields.
// TAINT: json.Decode -> struct fields -> SQL sink
func StructFieldTaint(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	var input UserInput

	// SOURCE: Entire struct from JSON body
	json.NewDecoder(r.Body).Decode(&input)

	// SINK: SQL injection via struct field
	query := fmt.Sprintf("INSERT INTO users (name, email, comment) VALUES ('%s', '%s', '%s')",
		input.Name, input.Email, input.Comment)
	db.Exec(query)
}

// NestedStructTaint demonstrates taint through nested structs.
type Request struct {
	User    UserInput
	Action  string
	Context map[string]string
}

// TAINT: json body -> nested struct -> map access -> SQL
func NestedStructTaint(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	var req Request
	json.NewDecoder(r.Body).Decode(&req)

	// Taint through nested field
	userName := req.User.Name

	// Taint through map access
	filter := req.Context["filter"]

	// SINK: Multiple tainted values
	query := fmt.Sprintf("SELECT * FROM audit WHERE user = '%s' AND filter = '%s'", userName, filter)
	db.Query(query)
}

// ============================================================================
// SAFE PATTERNS (SHOULD NOT FLAG)
// ============================================================================

// SafeParameterizedQuery demonstrates proper parameterized query.
// This should NOT be flagged as SQL injection.
func SafeParameterizedQuery(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("id")

	// SAFE: Parameterized query
	rows, _ := db.Query("SELECT * FROM users WHERE id = ?", userID)
	defer rows.Close()
}

// SafeCommandWithLiteral demonstrates safe command with literal.
// This should NOT be flagged as command injection.
func SafeCommandWithLiteral(w http.ResponseWriter, r *http.Request) {
	// SAFE: Literal command, user input only as argument to safe command
	userID := r.URL.Query().Get("id")
	cmd := exec.Command("echo", userID) // echo is safe, id is just echoed
	cmd.Run()
}

// SafePathWithValidation demonstrates path with validation.
// This should NOT be flagged if sanitization is detected.
func SafePathWithValidation(w http.ResponseWriter, r *http.Request) {
	filename := r.URL.Query().Get("file")

	// SANITIZER: Clean the path
	cleaned := filepath.Clean(filename)

	// Check for traversal
	if filepath.IsAbs(cleaned) || cleaned[0] == '.' {
		http.Error(w, "invalid path", 400)
		return
	}

	// After sanitization, should be safe
	path := filepath.Join("/var/data", cleaned)
	os.ReadFile(path)
}
