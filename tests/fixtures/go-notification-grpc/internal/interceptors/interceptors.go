package interceptors

import (
	"context"
	"log"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// LoggingUnaryInterceptor logs all unary RPC calls.
func LoggingUnaryInterceptor(
	ctx context.Context,
	req interface{},
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (interface{}, error) {
	start := time.Now()

	// Extract request ID from metadata
	requestID := "unknown"
	if md, ok := metadata.FromIncomingContext(ctx); ok {
		if ids := md.Get("x-request-id"); len(ids) > 0 {
			requestID = ids[0]
		}
	}

	// Call the handler
	resp, err := handler(ctx, req)

	// Log the call
	duration := time.Since(start)
	code := codes.OK
	if err != nil {
		if st, ok := status.FromError(err); ok {
			code = st.Code()
		}
	}

	log.Printf("[gRPC] %s | %s | %s | %v",
		info.FullMethod,
		requestID,
		code.String(),
		duration,
	)

	return resp, err
}

// LoggingStreamInterceptor logs all streaming RPC calls.
func LoggingStreamInterceptor(
	srv interface{},
	ss grpc.ServerStream,
	info *grpc.StreamServerInfo,
	handler grpc.StreamHandler,
) error {
	start := time.Now()

	err := handler(srv, ss)

	duration := time.Since(start)
	code := codes.OK
	if err != nil {
		if st, ok := status.FromError(err); ok {
			code = st.Code()
		}
	}

	log.Printf("[gRPC Stream] %s | %s | %v",
		info.FullMethod,
		code.String(),
		duration,
	)

	return err
}

// AuthUnaryInterceptor validates authentication for unary calls.
func AuthUnaryInterceptor(
	ctx context.Context,
	req interface{},
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (interface{}, error) {
	// Skip auth for health check
	if info.FullMethod == "/grpc.health.v1.Health/Check" {
		return handler(ctx, req)
	}

	// Extract token from metadata
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return nil, status.Error(codes.Unauthenticated, "missing metadata")
	}

	tokens := md.Get("authorization")
	if len(tokens) == 0 {
		return nil, status.Error(codes.Unauthenticated, "missing authorization token")
	}

	token := tokens[0]
	if !validateToken(token) {
		return nil, status.Error(codes.Unauthenticated, "invalid token")
	}

	// Extract user ID from token and add to context
	userID := extractUserID(token)
	ctx = context.WithValue(ctx, "user_id", userID)

	return handler(ctx, req)
}

// AuthStreamInterceptor validates authentication for streaming calls.
func AuthStreamInterceptor(
	srv interface{},
	ss grpc.ServerStream,
	info *grpc.StreamServerInfo,
	handler grpc.StreamHandler,
) error {
	ctx := ss.Context()

	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return status.Error(codes.Unauthenticated, "missing metadata")
	}

	tokens := md.Get("authorization")
	if len(tokens) == 0 {
		return status.Error(codes.Unauthenticated, "missing authorization token")
	}

	token := tokens[0]
	if !validateToken(token) {
		return status.Error(codes.Unauthenticated, "invalid token")
	}

	return handler(srv, ss)
}

// validateToken validates the authentication token.
// In a real app, this would verify JWT signature, expiration, etc.
func validateToken(token string) bool {
	// Simple validation for demo
	return len(token) > 10
}

// extractUserID extracts user ID from token.
// In a real app, this would decode the JWT.
func extractUserID(token string) string {
	// Simple extraction for demo
	return "user_from_token"
}

// RateLimitUnaryInterceptor implements rate limiting.
func RateLimitUnaryInterceptor(requestsPerSecond int) grpc.UnaryServerInterceptor {
	// Simple token bucket implementation
	tokens := make(chan struct{}, requestsPerSecond)

	// Fill the bucket
	go func() {
		ticker := time.NewTicker(time.Second / time.Duration(requestsPerSecond))
		defer ticker.Stop()
		for range ticker.C {
			select {
			case tokens <- struct{}{}:
			default:
			}
		}
	}()

	// Fill initial tokens
	for i := 0; i < requestsPerSecond; i++ {
		tokens <- struct{}{}
	}

	return func(
		ctx context.Context,
		req interface{},
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (interface{}, error) {
		select {
		case <-tokens:
			return handler(ctx, req)
		case <-ctx.Done():
			return nil, status.Error(codes.Canceled, "request canceled")
		default:
			return nil, status.Error(codes.ResourceExhausted, "rate limit exceeded")
		}
	}
}

// RecoveryUnaryInterceptor recovers from panics.
func RecoveryUnaryInterceptor(
	ctx context.Context,
	req interface{},
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (resp interface{}, err error) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[gRPC] Panic recovered: %v", r)
			err = status.Error(codes.Internal, "internal server error")
		}
	}()

	return handler(ctx, req)
}

// ChainUnaryInterceptors chains multiple unary interceptors.
func ChainUnaryInterceptors(interceptors ...grpc.UnaryServerInterceptor) grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req interface{},
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (interface{}, error) {
		chain := handler
		for i := len(interceptors) - 1; i >= 0; i-- {
			interceptor := interceptors[i]
			next := chain
			chain = func(ctx context.Context, req interface{}) (interface{}, error) {
				return interceptor(ctx, req, info, next)
			}
		}
		return chain(ctx, req)
	}
}
