# Go Task Queue

A distributed task queue system for testing TheAuditor Go extraction capabilities.

## Architecture

```
go-task-queue/
├── cmd/
│   ├── server/     # HTTP API server
│   ├── worker/     # Standalone worker process
│   └── cli/        # Command-line client
├── internal/
│   ├── queue/      # Queue interface and implementations
│   ├── task/       # Task handlers with generics
│   ├── worker/     # Worker pool and processors
│   ├── api/        # HTTP handlers and middleware
│   └── storage/    # Persistence layer
└── pkg/
    └── client/     # Go client library
```

## Running

### Server
```bash
go run ./cmd/server -port 8080 -workers 4
```

### Worker (standalone)
```bash
go run ./cmd/worker -workers 2
```

### CLI
```bash
# Enqueue a task
go run ./cmd/cli enqueue email '{"to":"user@example.com","subject":"Hello"}'

# List tasks
go run ./cmd/cli list --state=pending

# Get task status
go run ./cmd/cli get <task-id>

# Check health
go run ./cmd/cli health
```

## Go Patterns Covered

This fixture tests extraction of:

### Core Language Features
- Package declarations and organization
- Interface definitions and implementations
- Struct types with tags (JSON, GORM)
- Generic types and functions (Go 1.18+)
- Constants and variables
- Method receivers (pointer and value)

### Concurrency Patterns
- Goroutine spawning
- Channel operations (send, receive, close)
- Select statements
- sync.Mutex and sync.RWMutex
- sync/atomic operations
- sync.WaitGroup coordination
- Context cancellation

### Control Flow
- Defer statements
- Panic/recover
- Type assertions
- Type switches
- Error handling patterns

### Architectural Patterns
- Functional options
- Middleware chains
- Interface-based abstraction
- Dependency injection
- Repository pattern

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /tasks | Enqueue a task |
| POST | /tasks/bulk | Bulk enqueue |
| GET | /tasks | List tasks |
| GET | /tasks/{id} | Get task |
| DELETE | /tasks/{id} | Delete task |
| POST | /tasks/{id}/cancel | Cancel task |
| POST | /tasks/{id}/retry | Retry task |
| GET | /stats | Queue stats |
| GET | /health | Health check |

## Task Types

- `email` - Send email notifications
- `process_data` - Data processing jobs
- `generate_report` - Report generation
- `notification` - Push notifications
- `cleanup` - Cleanup jobs
- `compute` - Generic computation
- `transform` - Data transformation
- `aggregate` - Data aggregation
- `index` - Indexing jobs
