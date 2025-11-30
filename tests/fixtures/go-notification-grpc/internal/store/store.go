package store

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

var (
	ErrNotFound = errors.New("notification not found")
)

// Notification represents a stored notification (duplicated for package isolation).
type Notification struct {
	ID        string            `json:"id"`
	UserID    string            `json:"user_id"`
	Type      int32             `json:"type"`
	Title     string            `json:"title"`
	Body      string            `json:"body"`
	Data      map[string]string `json:"data"`
	Priority  int32             `json:"priority"`
	CreatedAt int64             `json:"created_at"`
	SentAt    int64             `json:"sent_at"`
	IsRead    bool              `json:"is_read"`
}

// NotificationStore handles notification persistence.
type NotificationStore struct {
	client      *redis.Client
	localCache  map[string]*Notification
	cacheMu     sync.RWMutex
	subscribers map[string][]string // userID -> topics
	subMu       sync.RWMutex
}

// Config holds Redis configuration.
type Config struct {
	Addr     string
	Password string
	DB       int
}

// NewNotificationStore creates a new NotificationStore.
func NewNotificationStore(cfg Config) (*NotificationStore, error) {
	client := redis.NewClient(&redis.Options{
		Addr:     cfg.Addr,
		Password: cfg.Password,
		DB:       cfg.DB,
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &NotificationStore{
		client:      client,
		localCache:  make(map[string]*Notification),
		subscribers: make(map[string][]string),
	}, nil
}

// NewInMemoryStore creates an in-memory store for testing.
func NewInMemoryStore() *NotificationStore {
	return &NotificationStore{
		localCache:  make(map[string]*Notification),
		subscribers: make(map[string][]string),
	}
}

// Save saves a notification.
func (s *NotificationStore) Save(n *Notification) error {
	// Save to local cache
	s.cacheMu.Lock()
	s.localCache[n.ID] = n
	s.cacheMu.Unlock()

	// If Redis is available, persist there
	if s.client != nil {
		return s.saveToRedis(n)
	}

	return nil
}

// saveToRedis persists notification to Redis.
func (s *NotificationStore) saveToRedis(n *Notification) error {
	ctx := context.Background()

	data, err := json.Marshal(n)
	if err != nil {
		return fmt.Errorf("failed to marshal notification: %w", err)
	}

	// Store notification
	key := fmt.Sprintf("notification:%s", n.ID)
	if err := s.client.Set(ctx, key, data, 7*24*time.Hour).Err(); err != nil {
		return fmt.Errorf("failed to save to Redis: %w", err)
	}

	// Add to user's notification list
	userKey := fmt.Sprintf("user:%s:notifications", n.UserID)
	if err := s.client.LPush(ctx, userKey, n.ID).Err(); err != nil {
		return fmt.Errorf("failed to update user list: %w", err)
	}

	// Trim to keep only recent notifications
	s.client.LTrim(ctx, userKey, 0, 999)

	return nil
}

// Get retrieves a notification by ID.
func (s *NotificationStore) Get(id string) (*Notification, error) {
	// Check local cache first
	s.cacheMu.RLock()
	if n, ok := s.localCache[id]; ok {
		s.cacheMu.RUnlock()
		return n, nil
	}
	s.cacheMu.RUnlock()

	// Try Redis if available
	if s.client != nil {
		return s.getFromRedis(id)
	}

	return nil, ErrNotFound
}

// getFromRedis retrieves notification from Redis.
func (s *NotificationStore) getFromRedis(id string) (*Notification, error) {
	ctx := context.Background()
	key := fmt.Sprintf("notification:%s", id)

	data, err := s.client.Get(ctx, key).Bytes()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("failed to get from Redis: %w", err)
	}

	var n Notification
	if err := json.Unmarshal(data, &n); err != nil {
		return nil, fmt.Errorf("failed to unmarshal notification: %w", err)
	}

	// Update cache
	s.cacheMu.Lock()
	s.localCache[id] = &n
	s.cacheMu.Unlock()

	return &n, nil
}

// Update updates a notification.
func (s *NotificationStore) Update(n *Notification) error {
	return s.Save(n)
}

// GetUserNotifications retrieves notifications for a user.
func (s *NotificationStore) GetUserNotifications(userID string, limit int) ([]*Notification, error) {
	if s.client == nil {
		// Return from local cache
		var results []*Notification
		s.cacheMu.RLock()
		for _, n := range s.localCache {
			if n.UserID == userID {
				results = append(results, n)
				if len(results) >= limit {
					break
				}
			}
		}
		s.cacheMu.RUnlock()
		return results, nil
	}

	ctx := context.Background()
	userKey := fmt.Sprintf("user:%s:notifications", userID)

	ids, err := s.client.LRange(ctx, userKey, 0, int64(limit-1)).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get user notifications: %w", err)
	}

	var notifications []*Notification
	for _, id := range ids {
		n, err := s.Get(id)
		if err != nil {
			continue // Skip missing notifications
		}
		notifications = append(notifications, n)
	}

	return notifications, nil
}

// MarkAsRead marks a notification as read.
func (s *NotificationStore) MarkAsRead(id string) error {
	n, err := s.Get(id)
	if err != nil {
		return err
	}

	n.IsRead = true
	return s.Update(n)
}

// Subscribe adds a user subscription to a topic.
func (s *NotificationStore) Subscribe(userID, topic string) error {
	s.subMu.Lock()
	defer s.subMu.Unlock()

	if s.subscribers[userID] == nil {
		s.subscribers[userID] = make([]string, 0)
	}

	// Check if already subscribed
	for _, t := range s.subscribers[userID] {
		if t == topic {
			return nil
		}
	}

	s.subscribers[userID] = append(s.subscribers[userID], topic)

	// Persist to Redis if available
	if s.client != nil {
		ctx := context.Background()
		key := fmt.Sprintf("user:%s:topics", userID)
		s.client.SAdd(ctx, key, topic)
	}

	return nil
}

// Unsubscribe removes a user subscription from a topic.
func (s *NotificationStore) Unsubscribe(userID, topic string) error {
	s.subMu.Lock()
	defer s.subMu.Unlock()

	topics := s.subscribers[userID]
	for i, t := range topics {
		if t == topic {
			s.subscribers[userID] = append(topics[:i], topics[i+1:]...)
			break
		}
	}

	// Remove from Redis if available
	if s.client != nil {
		ctx := context.Background()
		key := fmt.Sprintf("user:%s:topics", userID)
		s.client.SRem(ctx, key, topic)
	}

	return nil
}

// GetSubscriptions returns all topics a user is subscribed to.
func (s *NotificationStore) GetSubscriptions(userID string) ([]string, error) {
	s.subMu.RLock()
	topics := s.subscribers[userID]
	s.subMu.RUnlock()

	if len(topics) > 0 {
		return topics, nil
	}

	// Try Redis if available
	if s.client != nil {
		ctx := context.Background()
		key := fmt.Sprintf("user:%s:topics", userID)
		return s.client.SMembers(ctx, key).Result()
	}

	return []string{}, nil
}

// GetTopicSubscribers returns all users subscribed to a topic.
func (s *NotificationStore) GetTopicSubscribers(topic string) ([]string, error) {
	s.subMu.RLock()
	defer s.subMu.RUnlock()

	var subscribers []string
	for userID, topics := range s.subscribers {
		for _, t := range topics {
			if t == topic {
				subscribers = append(subscribers, userID)
				break
			}
		}
	}

	return subscribers, nil
}

// Close closes the store connection.
func (s *NotificationStore) Close() error {
	if s.client != nil {
		return s.client.Close()
	}
	return nil
}
