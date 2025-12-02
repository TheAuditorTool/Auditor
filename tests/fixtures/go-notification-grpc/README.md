# Notification Service (gRPC)

A gRPC-based notification microservice for sending push notifications, emails, SMS, and in-app notifications.

## Features

- Multiple notification types (email, push, SMS, in-app)
- Scheduled notifications with priority queue
- Real-time streaming for in-app notifications
- Topic-based subscriptions
- Redis-backed storage with in-memory fallback
- gRPC interceptors for logging, auth, rate limiting

## Project Structure

```
go-notification-grpc/
├── cmd/
│   └── server/
│       └── main.go           # Application entry point
├── internal/
│   ├── interceptors/
│   │   └── interceptors.go   # gRPC interceptors (auth, logging, rate limit)
│   ├── queue/
│   │   └── queue.go          # Priority queue for scheduled notifications
│   ├── server/
│   │   └── server.go         # gRPC service implementation
│   └── store/
│       └── store.go          # Redis/in-memory notification storage
├── proto/
│   └── notification.proto    # Protocol buffer definitions
├── go.mod
└── README.md
```

## Running the Service

### Prerequisites

- Go 1.21 or later
- Redis (optional, uses in-memory store if not available)
- protoc (for regenerating proto files)

### Quick Start

```bash
cd go-notification-grpc

# Download dependencies
go mod download

# Run the server
go run cmd/server/main.go
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| GRPC_PORT | 50051 | gRPC server port |
| REDIS_ADDR | localhost:6379 | Redis address (use "memory" for in-memory) |

### gRPC API

#### Services

**NotificationService**

| Method | Description |
|--------|-------------|
| SendNotification | Send a single notification |
| SendBulkNotifications | Send to multiple users |
| GetNotificationStatus | Get delivery status |
| StreamNotifications | Stream notifications to client |
| SubscribeToTopic | Subscribe user to topics |

### Example Client Usage

```go
package main

import (
    "context"
    "log"

    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
)

func main() {
    conn, err := grpc.Dial("localhost:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))
    if err != nil {
        log.Fatalf("Failed to connect: %v", err)
    }
    defer conn.Close()

    // Use the generated client...
}
```

### Interceptors

The service uses several gRPC interceptors:

1. **RecoveryInterceptor** - Recovers from panics and returns Internal error
2. **LoggingInterceptor** - Logs all RPC calls with timing
3. **RateLimitInterceptor** - Token bucket rate limiting (100 req/s)
4. **AuthInterceptor** - Validates authorization tokens (optional)

## Testing

This project serves as a test fixture for TheAuditor security scanner to test gRPC detection:

1. **gRPC Import Detection** - `google.golang.org/grpc` imports
2. **Interceptor Chain Detection** - ChainUnaryInterceptor/ChainStreamInterceptor
3. **Stream Handling** - Streaming RPC patterns
4. **Concurrency Patterns** - Goroutines, channels, sync primitives

**DO NOT USE IN PRODUCTION** - This is a test fixture with simplified authentication.

## License

MIT License - For testing purposes only.
