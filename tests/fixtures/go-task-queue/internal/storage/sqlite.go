package storage

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	_ "github.com/mattn/go-sqlite3"

	"github.com/example/task-queue/internal/queue"
)

// SQLiteStorage implements Storage using SQLite
type SQLiteStorage struct {
	db         *sql.DB
	serializer Serializer
}

// SQLiteConfig holds SQLite configuration
type SQLiteConfig struct {
	Path            string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
}

// DefaultSQLiteConfig returns default SQLite configuration
func DefaultSQLiteConfig() SQLiteConfig {
	return SQLiteConfig{
		Path:            "tasks.db",
		MaxOpenConns:    10,
		MaxIdleConns:    5,
		ConnMaxLifetime: time.Hour,
	}
}

// NewSQLiteStorage creates a new SQLite storage
func NewSQLiteStorage(cfg SQLiteConfig) (*SQLiteStorage, error) {
	dsn := fmt.Sprintf("file:%s?cache=shared&mode=rwc", cfg.Path)

	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	db.SetMaxOpenConns(cfg.MaxOpenConns)
	db.SetMaxIdleConns(cfg.MaxIdleConns)
	db.SetConnMaxLifetime(cfg.ConnMaxLifetime)

	s := &SQLiteStorage{
		db:         db,
		serializer: &JSONSerializer{},
	}

	if err := s.migrate(); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to run migrations: %w", err)
	}

	return s, nil
}

// migrate runs database migrations
func (s *SQLiteStorage) migrate() error {
	schema := `
		CREATE TABLE IF NOT EXISTS tasks (
			id TEXT PRIMARY KEY,
			type TEXT NOT NULL,
			payload TEXT NOT NULL,
			priority INTEGER DEFAULT 0,
			state TEXT NOT NULL DEFAULT 'pending',
			created_at DATETIME NOT NULL,
			started_at DATETIME,
			completed_at DATETIME,
			retries INTEGER DEFAULT 0,
			max_retries INTEGER DEFAULT 3,
			error TEXT,
			result TEXT,
			metadata TEXT
		);

		CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
		CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type);
		CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
		CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
	`

	_, err := s.db.Exec(schema)
	return err
}

// SaveTask saves a task to the database
func (s *SQLiteStorage) SaveTask(ctx context.Context, task *queue.Task) error {
	payload, err := json.Marshal(task.Payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	metadata, err := json.Marshal(task.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `
		INSERT INTO tasks (id, type, payload, priority, state, created_at, retries, max_retries, metadata)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(id) DO UPDATE SET
			state = excluded.state,
			started_at = excluded.started_at,
			completed_at = excluded.completed_at,
			retries = excluded.retries,
			error = excluded.error,
			result = excluded.result
	`

	_, err = s.db.ExecContext(ctx, query,
		task.ID,
		task.Type,
		string(payload),
		task.Priority,
		task.State,
		task.CreatedAt,
		task.Retries,
		task.MaxRetries,
		string(metadata),
	)

	if err != nil {
		return fmt.Errorf("failed to save task: %w", err)
	}

	return nil
}

// GetTask retrieves a task by ID
func (s *SQLiteStorage) GetTask(ctx context.Context, id string) (*queue.Task, error) {
	query := `
		SELECT id, type, payload, priority, state, created_at, started_at, completed_at,
		       retries, max_retries, error, result, metadata
		FROM tasks WHERE id = ?
	`

	row := s.db.QueryRowContext(ctx, query, id)
	return s.scanTask(row)
}

// scanTask scans a row into a Task
func (s *SQLiteStorage) scanTask(row *sql.Row) (*queue.Task, error) {
	var task queue.Task
	var payload, metadata, result sql.NullString
	var startedAt, completedAt sql.NullTime
	var errorStr sql.NullString

	err := row.Scan(
		&task.ID,
		&task.Type,
		&payload,
		&task.Priority,
		&task.State,
		&task.CreatedAt,
		&startedAt,
		&completedAt,
		&task.Retries,
		&task.MaxRetries,
		&errorStr,
		&result,
		&metadata,
	)

	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("failed to scan task: %w", err)
	}

	// Parse JSON fields
	if payload.Valid {
		if err := json.Unmarshal([]byte(payload.String), &task.Payload); err != nil {
			return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
		}
	}

	if metadata.Valid {
		if err := json.Unmarshal([]byte(metadata.String), &task.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}
	}

	if result.Valid {
		if err := json.Unmarshal([]byte(result.String), &task.Result); err != nil {
			return nil, fmt.Errorf("failed to unmarshal result: %w", err)
		}
	}

	if startedAt.Valid {
		task.StartedAt = &startedAt.Time
	}
	if completedAt.Valid {
		task.CompletedAt = &completedAt.Time
	}
	if errorStr.Valid {
		task.Error = errorStr.String
	}

	return &task, nil
}

// UpdateTask updates a task
func (s *SQLiteStorage) UpdateTask(ctx context.Context, task *queue.Task) error {
	result, err := json.Marshal(task.Result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	query := `
		UPDATE tasks SET
			state = ?,
			started_at = ?,
			completed_at = ?,
			retries = ?,
			error = ?,
			result = ?
		WHERE id = ?
	`

	res, err := s.db.ExecContext(ctx, query,
		task.State,
		task.StartedAt,
		task.CompletedAt,
		task.Retries,
		task.Error,
		string(result),
		task.ID,
	)

	if err != nil {
		return fmt.Errorf("failed to update task: %w", err)
	}

	rows, err := res.RowsAffected()
	if err != nil {
		return err
	}

	if rows == 0 {
		return ErrNotFound
	}

	return nil
}

// DeleteTask deletes a task
func (s *SQLiteStorage) DeleteTask(ctx context.Context, id string) error {
	res, err := s.db.ExecContext(ctx, "DELETE FROM tasks WHERE id = ?", id)
	if err != nil {
		return fmt.Errorf("failed to delete task: %w", err)
	}

	rows, err := res.RowsAffected()
	if err != nil {
		return err
	}

	if rows == 0 {
		return ErrNotFound
	}

	return nil
}

// ListTasks lists tasks with filters
func (s *SQLiteStorage) ListTasks(ctx context.Context, filter TaskFilter) ([]*queue.Task, error) {
	var conditions []string
	var args []interface{}

	if filter.State != "" {
		conditions = append(conditions, "state = ?")
		args = append(args, filter.State)
	}
	if filter.Type != "" {
		conditions = append(conditions, "type = ?")
		args = append(args, filter.Type)
	}
	if !filter.CreatedAfter.IsZero() {
		conditions = append(conditions, "created_at > ?")
		args = append(args, filter.CreatedAfter)
	}
	if !filter.CreatedBefore.IsZero() {
		conditions = append(conditions, "created_at < ?")
		args = append(args, filter.CreatedBefore)
	}

	query := `
		SELECT id, type, payload, priority, state, created_at, started_at, completed_at,
		       retries, max_retries, error, result, metadata
		FROM tasks
	`

	if len(conditions) > 0 {
		query += " WHERE " + strings.Join(conditions, " AND ")
	}

	// Order
	orderBy := "created_at"
	if filter.OrderBy != "" {
		orderBy = filter.OrderBy
	}
	order := "ASC"
	if filter.OrderDesc {
		order = "DESC"
	}
	query += fmt.Sprintf(" ORDER BY %s %s", orderBy, order)

	// Pagination
	if filter.Limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", filter.Limit)
	}
	if filter.Offset > 0 {
		query += fmt.Sprintf(" OFFSET %d", filter.Offset)
	}

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list tasks: %w", err)
	}
	defer rows.Close()

	var tasks []*queue.Task
	for rows.Next() {
		task, err := s.scanTaskRows(rows)
		if err != nil {
			return nil, err
		}
		tasks = append(tasks, task)
	}

	return tasks, rows.Err()
}

// scanTaskRows scans a rows result into a Task
func (s *SQLiteStorage) scanTaskRows(rows *sql.Rows) (*queue.Task, error) {
	var task queue.Task
	var payload, metadata, result sql.NullString
	var startedAt, completedAt sql.NullTime
	var errorStr sql.NullString

	err := rows.Scan(
		&task.ID,
		&task.Type,
		&payload,
		&task.Priority,
		&task.State,
		&task.CreatedAt,
		&startedAt,
		&completedAt,
		&task.Retries,
		&task.MaxRetries,
		&errorStr,
		&result,
		&metadata,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to scan task: %w", err)
	}

	// Parse JSON fields
	if payload.Valid {
		json.Unmarshal([]byte(payload.String), &task.Payload)
	}
	if metadata.Valid {
		json.Unmarshal([]byte(metadata.String), &task.Metadata)
	}
	if result.Valid {
		json.Unmarshal([]byte(result.String), &task.Result)
	}

	if startedAt.Valid {
		task.StartedAt = &startedAt.Time
	}
	if completedAt.Valid {
		task.CompletedAt = &completedAt.Time
	}
	if errorStr.Valid {
		task.Error = errorStr.String
	}

	return &task, nil
}

// SaveTasks saves multiple tasks in a transaction
func (s *SQLiteStorage) SaveTasks(ctx context.Context, tasks []*queue.Task) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO tasks (id, type, payload, priority, state, created_at, retries, max_retries, metadata)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare statement: %w", err)
	}
	defer stmt.Close()

	for _, task := range tasks {
		payload, _ := json.Marshal(task.Payload)
		metadata, _ := json.Marshal(task.Metadata)

		_, err := stmt.ExecContext(ctx,
			task.ID,
			task.Type,
			string(payload),
			task.Priority,
			task.State,
			task.CreatedAt,
			task.Retries,
			task.MaxRetries,
			string(metadata),
		)
		if err != nil {
			return fmt.Errorf("failed to insert task %s: %w", task.ID, err)
		}
	}

	return tx.Commit()
}

// DeleteTasks deletes multiple tasks
func (s *SQLiteStorage) DeleteTasks(ctx context.Context, ids []string) error {
	if len(ids) == 0 {
		return nil
	}

	placeholders := make([]string, len(ids))
	args := make([]interface{}, len(ids))
	for i, id := range ids {
		placeholders[i] = "?"
		args[i] = id
	}

	query := fmt.Sprintf("DELETE FROM tasks WHERE id IN (%s)", strings.Join(placeholders, ","))
	_, err := s.db.ExecContext(ctx, query, args...)
	return err
}

// CountTasks counts tasks matching filter
func (s *SQLiteStorage) CountTasks(ctx context.Context, filter TaskFilter) (int, error) {
	var conditions []string
	var args []interface{}

	if filter.State != "" {
		conditions = append(conditions, "state = ?")
		args = append(args, filter.State)
	}
	if filter.Type != "" {
		conditions = append(conditions, "type = ?")
		args = append(args, filter.Type)
	}

	query := "SELECT COUNT(*) FROM tasks"
	if len(conditions) > 0 {
		query += " WHERE " + strings.Join(conditions, " AND ")
	}

	var count int
	err := s.db.QueryRowContext(ctx, query, args...).Scan(&count)
	return count, err
}

// GetTasksByState gets all tasks in a specific state
func (s *SQLiteStorage) GetTasksByState(ctx context.Context, state queue.TaskState) ([]*queue.Task, error) {
	return s.ListTasks(ctx, TaskFilter{State: state})
}

// GetStaleTasks gets tasks older than duration
func (s *SQLiteStorage) GetStaleTasks(ctx context.Context, olderThan time.Duration) ([]*queue.Task, error) {
	threshold := time.Now().Add(-olderThan)
	return s.ListTasks(ctx, TaskFilter{
		CreatedBefore: threshold,
	})
}

// Close closes the database connection
func (s *SQLiteStorage) Close() error {
	return s.db.Close()
}

// Ping checks database health
func (s *SQLiteStorage) Ping(ctx context.Context) error {
	return s.db.PingContext(ctx)
}

// Begin starts a transaction
func (s *SQLiteStorage) Begin(ctx context.Context) (Transaction, error) {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	return &SQLiteTransaction{tx: tx, storage: s}, nil
}

// SQLiteTransaction implements Transaction
type SQLiteTransaction struct {
	tx      *sql.Tx
	storage *SQLiteStorage
}

// SaveTask saves a task in the transaction
func (t *SQLiteTransaction) SaveTask(ctx context.Context, task *queue.Task) error {
	payload, _ := json.Marshal(task.Payload)
	metadata, _ := json.Marshal(task.Metadata)

	query := `
		INSERT INTO tasks (id, type, payload, priority, state, created_at, retries, max_retries, metadata)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err := t.tx.ExecContext(ctx, query,
		task.ID,
		task.Type,
		string(payload),
		task.Priority,
		task.State,
		task.CreatedAt,
		task.Retries,
		task.MaxRetries,
		string(metadata),
	)

	return err
}

// Other transaction methods delegate to storage with tx context
func (t *SQLiteTransaction) GetTask(ctx context.Context, id string) (*queue.Task, error) {
	return t.storage.GetTask(ctx, id)
}

func (t *SQLiteTransaction) UpdateTask(ctx context.Context, task *queue.Task) error {
	return t.storage.UpdateTask(ctx, task)
}

func (t *SQLiteTransaction) DeleteTask(ctx context.Context, id string) error {
	_, err := t.tx.ExecContext(ctx, "DELETE FROM tasks WHERE id = ?", id)
	return err
}

func (t *SQLiteTransaction) ListTasks(ctx context.Context, filter TaskFilter) ([]*queue.Task, error) {
	return t.storage.ListTasks(ctx, filter)
}

func (t *SQLiteTransaction) SaveTasks(ctx context.Context, tasks []*queue.Task) error {
	for _, task := range tasks {
		if err := t.SaveTask(ctx, task); err != nil {
			return err
		}
	}
	return nil
}

func (t *SQLiteTransaction) DeleteTasks(ctx context.Context, ids []string) error {
	for _, id := range ids {
		if err := t.DeleteTask(ctx, id); err != nil {
			return err
		}
	}
	return nil
}

func (t *SQLiteTransaction) CountTasks(ctx context.Context, filter TaskFilter) (int, error) {
	return t.storage.CountTasks(ctx, filter)
}

func (t *SQLiteTransaction) GetTasksByState(ctx context.Context, state queue.TaskState) ([]*queue.Task, error) {
	return t.storage.GetTasksByState(ctx, state)
}

func (t *SQLiteTransaction) GetStaleTasks(ctx context.Context, olderThan time.Duration) ([]*queue.Task, error) {
	return t.storage.GetStaleTasks(ctx, olderThan)
}

func (t *SQLiteTransaction) Close() error {
	return nil
}

func (t *SQLiteTransaction) Ping(ctx context.Context) error {
	return nil
}

func (t *SQLiteTransaction) Commit() error {
	return t.tx.Commit()
}

func (t *SQLiteTransaction) Rollback() error {
	return t.tx.Rollback()
}
