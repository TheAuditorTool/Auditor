package server

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/example/notification-service/internal/queue"
	"github.com/example/notification-service/internal/store"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// NotificationType mirrors the proto enum.
type NotificationType int32

const (
	NotificationTypeUnspecified NotificationType = 0
	NotificationTypeEmail       NotificationType = 1
	NotificationTypePush        NotificationType = 2
	NotificationTypeSMS         NotificationType = 3
	NotificationTypeInApp       NotificationType = 4
)

// Priority mirrors the proto enum.
type Priority int32

const (
	PriorityUnspecified Priority = 0
	PriorityLow         Priority = 1
	PriorityNormal      Priority = 2
	PriorityHigh        Priority = 3
	PriorityUrgent      Priority = 4
)

// Notification represents a notification.
type Notification struct {
	ID        string
	UserID    string
	Type      NotificationType
	Title     string
	Body      string
	Data      map[string]string
	Priority  Priority
	CreatedAt int64
	SentAt    int64
	IsRead    bool
}

// SendNotificationRequest is the request to send a notification.
type SendNotificationRequest struct {
	UserID     string
	Type       NotificationType
	Title      string
	Body       string
	Data       map[string]string
	Priority   Priority
	ScheduleAt int64
}

// SendNotificationResponse is the response.
type SendNotificationResponse struct {
	NotificationID string
	Success        bool
	ErrorMessage   string
}

// NotificationServer implements the NotificationService gRPC service.
type NotificationServer struct {
	store       *store.NotificationStore
	queue       *queue.NotificationQueue
	subscribers map[string][]chan *Notification
	mu          sync.RWMutex
}

// NewNotificationServer creates a new NotificationServer.
func NewNotificationServer(store *store.NotificationStore, queue *queue.NotificationQueue) *NotificationServer {
	return &NotificationServer{
		store:       store,
		queue:       queue,
		subscribers: make(map[string][]chan *Notification),
	}
}

// SendNotification sends a single notification.
func (s *NotificationServer) SendNotification(ctx context.Context, req *SendNotificationRequest) (*SendNotificationResponse, error) {
	if req.UserID == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	if req.Title == "" && req.Body == "" {
		return nil, status.Error(codes.InvalidArgument, "title or body is required")
	}

	notification := &Notification{
		ID:        generateID(),
		UserID:    req.UserID,
		Type:      req.Type,
		Title:     req.Title,
		Body:      req.Body,
		Data:      req.Data,
		Priority:  req.Priority,
		CreatedAt: time.Now().Unix(),
	}

	// If scheduled for later, queue it
	if req.ScheduleAt > 0 && req.ScheduleAt > time.Now().Unix() {
		if err := s.queue.Schedule(notification, time.Unix(req.ScheduleAt, 0)); err != nil {
			return &SendNotificationResponse{
				Success:      false,
				ErrorMessage: fmt.Sprintf("failed to schedule: %v", err),
			}, nil
		}

		return &SendNotificationResponse{
			NotificationID: notification.ID,
			Success:        true,
		}, nil
	}

	// Send immediately
	if err := s.sendNow(ctx, notification); err != nil {
		return &SendNotificationResponse{
			Success:      false,
			ErrorMessage: err.Error(),
		}, nil
	}

	return &SendNotificationResponse{
		NotificationID: notification.ID,
		Success:        true,
	}, nil
}

// sendNow sends a notification immediately.
func (s *NotificationServer) sendNow(ctx context.Context, notification *Notification) error {
	// Store the notification
	if err := s.store.Save(notification); err != nil {
		return fmt.Errorf("failed to save notification: %w", err)
	}

	// Send based on type
	switch notification.Type {
	case NotificationTypeEmail:
		return s.sendEmail(notification)
	case NotificationTypePush:
		return s.sendPush(notification)
	case NotificationTypeSMS:
		return s.sendSMS(notification)
	case NotificationTypeInApp:
		return s.sendInApp(notification)
	default:
		return s.sendInApp(notification)
	}
}

// sendEmail sends an email notification.
func (s *NotificationServer) sendEmail(n *Notification) error {
	// In a real app, this would use an email service
	log.Printf("Sending email to user %s: %s", n.UserID, n.Title)
	n.SentAt = time.Now().Unix()
	return s.store.Update(n)
}

// sendPush sends a push notification.
func (s *NotificationServer) sendPush(n *Notification) error {
	// In a real app, this would use FCM/APNS
	log.Printf("Sending push to user %s: %s", n.UserID, n.Title)
	n.SentAt = time.Now().Unix()
	return s.store.Update(n)
}

// sendSMS sends an SMS notification.
func (s *NotificationServer) sendSMS(n *Notification) error {
	// In a real app, this would use Twilio/SMS gateway
	log.Printf("Sending SMS to user %s: %s", n.UserID, n.Body)
	n.SentAt = time.Now().Unix()
	return s.store.Update(n)
}

// sendInApp sends an in-app notification.
func (s *NotificationServer) sendInApp(n *Notification) error {
	n.SentAt = time.Now().Unix()

	// Update store
	if err := s.store.Update(n); err != nil {
		return err
	}

	// Notify subscribers
	s.notifySubscribers(n)

	return nil
}

// notifySubscribers sends notification to all subscribed clients.
func (s *NotificationServer) notifySubscribers(n *Notification) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	channels, ok := s.subscribers[n.UserID]
	if !ok {
		return
	}

	for _, ch := range channels {
		select {
		case ch <- n:
		default:
			// Channel full, skip
		}
	}
}

// StreamNotifications streams notifications to a client.
func (s *NotificationServer) StreamNotifications(userID string, types []NotificationType, stream chan *Notification) error {
	// Register subscriber
	s.mu.Lock()
	if s.subscribers[userID] == nil {
		s.subscribers[userID] = make([]chan *Notification, 0)
	}
	s.subscribers[userID] = append(s.subscribers[userID], stream)
	s.mu.Unlock()

	// Cleanup on exit
	defer func() {
		s.mu.Lock()
		channels := s.subscribers[userID]
		for i, ch := range channels {
			if ch == stream {
				s.subscribers[userID] = append(channels[:i], channels[i+1:]...)
				break
			}
		}
		s.mu.Unlock()
		close(stream)
	}()

	// Keep connection alive
	select {}
}

// SendBulkNotifications sends notifications to multiple users.
func (s *NotificationServer) SendBulkNotifications(ctx context.Context, userIDs []string, notificationType NotificationType, title, body string, data map[string]string, priority Priority) (int, int, []string) {
	var (
		totalSent   int
		totalFailed int
		failedIDs   []string
		wg          sync.WaitGroup
		mu          sync.Mutex
	)

	// VULNERABILITY: Unbounded concurrency - could exhaust resources
	for _, userID := range userIDs {
		wg.Add(1)
		go func(uid string) {
			defer wg.Done()

			req := &SendNotificationRequest{
				UserID:   uid,
				Type:     notificationType,
				Title:    title,
				Body:     body,
				Data:     data,
				Priority: priority,
			}

			resp, err := s.SendNotification(ctx, req)
			mu.Lock()
			defer mu.Unlock()

			if err != nil || !resp.Success {
				totalFailed++
				failedIDs = append(failedIDs, uid)
			} else {
				totalSent++
			}
		}(userID)
	}

	wg.Wait()
	return totalSent, totalFailed, failedIDs
}

// GetNotificationStatus gets the status of a notification.
func (s *NotificationServer) GetNotificationStatus(ctx context.Context, notificationID string) (*Notification, error) {
	if notificationID == "" {
		return nil, status.Error(codes.InvalidArgument, "notification_id is required")
	}

	n, err := s.store.Get(notificationID)
	if err != nil {
		return nil, status.Error(codes.NotFound, "notification not found")
	}

	return n, nil
}

// SubscribeToTopic subscribes a user to topics.
func (s *NotificationServer) SubscribeToTopic(ctx context.Context, userID string, topics []string) ([]string, error) {
	if userID == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	if len(topics) == 0 {
		return nil, status.Error(codes.InvalidArgument, "topics are required")
	}

	// Store subscriptions
	for _, topic := range topics {
		if err := s.store.Subscribe(userID, topic); err != nil {
			return nil, status.Error(codes.Internal, fmt.Sprintf("failed to subscribe to %s: %v", topic, err))
		}
	}

	return topics, nil
}

// generateID generates a simple unique ID.
func generateID() string {
	return fmt.Sprintf("notif_%d", time.Now().UnixNano())
}

// RegisterService registers the notification service with a gRPC server.
func RegisterService(grpcServer *grpc.Server, notifServer *NotificationServer) {
	// In a real app, this would use the generated RegisterNotificationServiceServer
	log.Println("Registered NotificationService")
}
