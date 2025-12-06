package api

import (
	"context"
	"log"
	"net/http"
	"runtime/debug"
	"sync"
	"time"

	"github.com/google/uuid"
)

// ContextKey is a type for context keys
type ContextKey string

const (
	RequestIDKey   ContextKey = "request_id"
	RequestTimeKey ContextKey = "request_time"
)

// Middleware is a function that wraps an http.Handler
type Middleware func(http.Handler) http.Handler

// Chain chains multiple middlewares together
func Chain(h http.Handler, middlewares ...Middleware) http.Handler {
	for i := len(middlewares) - 1; i >= 0; i-- {
		h = middlewares[i](h)
	}
	return h
}

// RequestID adds a unique request ID to each request
func RequestID() Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			id := r.Header.Get("X-Request-ID")
			if id == "" {
				id = uuid.New().String()
			}

			ctx := context.WithValue(r.Context(), RequestIDKey, id)
			w.Header().Set("X-Request-ID", id)

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// GetRequestID retrieves the request ID from context
func GetRequestID(ctx context.Context) string {
	if id, ok := ctx.Value(RequestIDKey).(string); ok {
		return id
	}
	return ""
}

// Logger logs each request
func Logger(logger *log.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()

			// Wrap response writer to capture status code
			wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}

			next.ServeHTTP(wrapped, r)

			duration := time.Since(start)

			logger.Printf(
				"[%s] %s %s %d %v",
				GetRequestID(r.Context()),
				r.Method,
				r.URL.Path,
				wrapped.statusCode,
				duration,
			)
		})
	}
}

// responseWriter wraps http.ResponseWriter to capture status code
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// Recover recovers from panics and returns a 500 error
func Recover(logger *log.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if err := recover(); err != nil {
					logger.Printf(
						"[%s] PANIC: %v\n%s",
						GetRequestID(r.Context()),
						err,
						debug.Stack(),
					)
					writeError(w, http.StatusInternalServerError, "internal server error")
				}
			}()

			next.ServeHTTP(w, r)
		})
	}
}

// Timeout adds a timeout to requests
func Timeout(d time.Duration) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx, cancel := context.WithTimeout(r.Context(), d)
			defer cancel()

			done := make(chan struct{})
			go func() {
				next.ServeHTTP(w, r.WithContext(ctx))
				close(done)
			}()

			select {
			case <-done:
				return
			case <-ctx.Done():
				writeError(w, http.StatusGatewayTimeout, "request timeout")
			}
		})
	}
}

// RateLimiter limits requests per client
type RateLimiter struct {
	mu       sync.Mutex
	requests map[string][]time.Time
	rate     int
	window   time.Duration
}

// NewRateLimiter creates a new rate limiter
func NewRateLimiter(rate int, window time.Duration) *RateLimiter {
	rl := &RateLimiter{
		requests: make(map[string][]time.Time),
		rate:     rate,
		window:   window,
	}

	// Cleanup goroutine
	go rl.cleanup()

	return rl
}

// cleanup removes old entries
func (rl *RateLimiter) cleanup() {
	ticker := time.NewTicker(rl.window)
	defer ticker.Stop()

	for range ticker.C {
		rl.mu.Lock()
		now := time.Now()
		for key, times := range rl.requests {
			var valid []time.Time
			for _, t := range times {
				if now.Sub(t) < rl.window {
					valid = append(valid, t)
				}
			}
			if len(valid) == 0 {
				delete(rl.requests, key)
			} else {
				rl.requests[key] = valid
			}
		}
		rl.mu.Unlock()
	}
}

// Allow checks if a request is allowed
func (rl *RateLimiter) Allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()

	// Remove old requests
	var valid []time.Time
	for _, t := range rl.requests[key] {
		if now.Sub(t) < rl.window {
			valid = append(valid, t)
		}
	}

	if len(valid) >= rl.rate {
		return false
	}

	rl.requests[key] = append(valid, now)
	return true
}

// Middleware creates a rate limiting middleware
func (rl *RateLimiter) Middleware() Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Use client IP as key
			key := r.RemoteAddr

			if !rl.Allow(key) {
				w.Header().Set("Retry-After", rl.window.String())
				writeError(w, http.StatusTooManyRequests, "rate limit exceeded")
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// CORS adds CORS headers
func CORS(allowedOrigins []string) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := r.Header.Get("Origin")

			// Check if origin is allowed
			allowed := false
			for _, o := range allowedOrigins {
				if o == "*" || o == origin {
					allowed = true
					break
				}
			}

			if allowed {
				w.Header().Set("Access-Control-Allow-Origin", origin)
				w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
				w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID")
				w.Header().Set("Access-Control-Max-Age", "86400")
			}

			// Handle preflight
			if r.Method == http.MethodOptions {
				w.WriteHeader(http.StatusNoContent)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// Auth is a simple authentication middleware
type Auth struct {
	tokens map[string]bool
	mu     sync.RWMutex
}

// NewAuth creates a new Auth middleware
func NewAuth(tokens []string) *Auth {
	a := &Auth{
		tokens: make(map[string]bool),
	}
	for _, t := range tokens {
		a.tokens[t] = true
	}
	return a
}

// AddToken adds a valid token
func (a *Auth) AddToken(token string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.tokens[token] = true
}

// RemoveToken removes a token
func (a *Auth) RemoveToken(token string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	delete(a.tokens, token)
}

// Middleware creates an authentication middleware
func (a *Auth) Middleware() Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			token := r.Header.Get("Authorization")
			if token == "" {
				token = r.URL.Query().Get("token")
			}

			a.mu.RLock()
			valid := a.tokens[token]
			a.mu.RUnlock()

			if !valid {
				writeError(w, http.StatusUnauthorized, "unauthorized")
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// ContentType ensures correct content type
func ContentType(contentType string) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.Method == http.MethodPost || r.Method == http.MethodPut {
				ct := r.Header.Get("Content-Type")
				if ct != contentType {
					writeError(w, http.StatusUnsupportedMediaType,
						"content type must be "+contentType)
					return
				}
			}

			next.ServeHTTP(w, r)
		})
	}
}

// MaxBodySize limits request body size
func MaxBodySize(n int64) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			r.Body = http.MaxBytesReader(w, r.Body, n)
			next.ServeHTTP(w, r)
		})
	}
}

// SecureHeaders adds security headers
func SecureHeaders() Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("X-Content-Type-Options", "nosniff")
			w.Header().Set("X-Frame-Options", "DENY")
			w.Header().Set("X-XSS-Protection", "1; mode=block")
			w.Header().Set("Content-Security-Policy", "default-src 'self'")

			next.ServeHTTP(w, r)
		})
	}
}

// Metrics collects request metrics
type Metrics struct {
	mu             sync.RWMutex
	totalRequests  int64
	totalErrors    int64
	requestsByPath map[string]int64
	latencies      []time.Duration
}

// NewMetrics creates a new Metrics collector
func NewMetrics() *Metrics {
	return &Metrics{
		requestsByPath: make(map[string]int64),
		latencies:      make([]time.Duration, 0),
	}
}

// Middleware creates a metrics middleware
func (m *Metrics) Middleware() Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()

			wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
			next.ServeHTTP(wrapped, r)

			duration := time.Since(start)

			m.mu.Lock()
			m.totalRequests++
			m.requestsByPath[r.URL.Path]++
			m.latencies = append(m.latencies, duration)
			if wrapped.statusCode >= 400 {
				m.totalErrors++
			}
			m.mu.Unlock()
		})
	}
}

// Stats returns current metrics
func (m *Metrics) Stats() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var avgLatency time.Duration
	if len(m.latencies) > 0 {
		var total time.Duration
		for _, l := range m.latencies {
			total += l
		}
		avgLatency = total / time.Duration(len(m.latencies))
	}

	return map[string]interface{}{
		"total_requests":   m.totalRequests,
		"total_errors":     m.totalErrors,
		"requests_by_path": m.requestsByPath,
		"avg_latency":      avgLatency.String(),
	}
}
