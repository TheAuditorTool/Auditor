package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/example/notification-service/internal/interceptors"
	"github.com/example/notification-service/internal/queue"
	"github.com/example/notification-service/internal/server"
	"github.com/example/notification-service/internal/store"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

func main() {
	// Configuration
	port := getEnv("GRPC_PORT", "50051")
	redisAddr := getEnv("REDIS_ADDR", "localhost:6379")

	// Initialize store
	var notificationStore *store.NotificationStore
	var err error

	if redisAddr != "" && redisAddr != "memory" {
		notificationStore, err = store.NewNotificationStore(store.Config{
			Addr: redisAddr,
		})
		if err != nil {
			log.Printf("Failed to connect to Redis, using in-memory store: %v", err)
			notificationStore = store.NewInMemoryStore()
		}
	} else {
		notificationStore = store.NewInMemoryStore()
	}
	defer notificationStore.Close()

	// Initialize notification server
	notifServer := server.NewNotificationServer(
		notificationStore,
		nil, // Queue will be set up below
	)

	// Initialize queue with handler
	notifQueue := queue.NewNotificationQueue(func(n *queue.Notification) error {
		// Convert to server notification and send
		serverNotif := &server.Notification{
			ID:        n.ID,
			UserID:    n.UserID,
			Type:      server.NotificationType(n.Type),
			Title:     n.Title,
			Body:      n.Body,
			Data:      n.Data,
			Priority:  server.Priority(n.Priority),
			CreatedAt: n.CreatedAt,
		}
		_, err := notifServer.SendNotification(context.Background(), &server.SendNotificationRequest{
			UserID:   serverNotif.UserID,
			Type:     serverNotif.Type,
			Title:    serverNotif.Title,
			Body:     serverNotif.Body,
			Data:     serverNotif.Data,
			Priority: serverNotif.Priority,
		})
		return err
	})

	// Start queue processor
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	notifQueue.Start(ctx)
	defer notifQueue.Stop()

	// Create gRPC server with interceptors
	grpcServer := grpc.NewServer(
		grpc.ChainUnaryInterceptor(
			interceptors.RecoveryUnaryInterceptor,
			interceptors.LoggingUnaryInterceptor,
			interceptors.RateLimitUnaryInterceptor(100),
		),
		grpc.ChainStreamInterceptor(
			interceptors.LoggingStreamInterceptor,
		),
	)

	// Register services
	server.RegisterService(grpcServer, notifServer)

	// Enable reflection for debugging
	reflection.Register(grpcServer)

	// Start listening
	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	// Start server in goroutine
	go func() {
		log.Printf("gRPC server listening on port %s", port)
		if err := grpcServer.Serve(lis); err != nil {
			log.Fatalf("Failed to serve: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down gRPC server...")
	grpcServer.GracefulStop()
	log.Println("Server stopped")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
