package services

import (
	"crypto/md5"
	"encoding/hex"
	"errors"
	"fmt"
	"math/rand"
	"os"
	"time"

	"github.com/example/calorie-tracker/internal/models"
	"github.com/example/calorie-tracker/internal/repository"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
)

var (
	ErrInvalidCredentials = errors.New("invalid email or password")
	ErrTokenExpired       = errors.New("token has expired")
	ErrInvalidToken       = errors.New("invalid token")
)

// AuthService handles authentication and authorization.
type AuthService struct {
	userRepo  *repository.UserRepository
	jwtSecret []byte
}

// NewAuthService creates a new AuthService.
func NewAuthService(userRepo *repository.UserRepository) *AuthService {
	secret := os.Getenv("JWT_SECRET")
	if secret == "" {
		secret = "default-dev-secret-change-in-production"
	}

	return &AuthService{
		userRepo:  userRepo,
		jwtSecret: []byte(secret),
	}
}

// RegisterRequest contains registration data.
type RegisterRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=8"`
	Name     string `json:"name" binding:"required"`
}

// Register creates a new user account.
func (s *AuthService) Register(req RegisterRequest) (*models.User, error) {
	// Hash password with bcrypt (secure)
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, fmt.Errorf("failed to hash password: %w", err)
	}

	user := &models.User{
		Email:        req.Email,
		PasswordHash: string(hashedPassword),
		Name:         req.Name,
		DailyGoal:    2000, // Default goal
		IsActive:     true,
	}

	if err := s.userRepo.Create(user); err != nil {
		return nil, err
	}

	return user, nil
}

// Login authenticates a user and returns a JWT token.
func (s *AuthService) Login(email, password string) (string, error) {
	user, err := s.userRepo.GetByEmail(email)
	if err != nil {
		return "", ErrInvalidCredentials
	}

	if !user.IsActive {
		return "", ErrInvalidCredentials
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)); err != nil {
		return "", ErrInvalidCredentials
	}

	// Generate JWT token
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"user_id": user.ID,
		"email":   user.Email,
		"exp":     time.Now().Add(24 * time.Hour).Unix(),
		"iat":     time.Now().Unix(),
	})

	tokenString, err := token.SignedString(s.jwtSecret)
	if err != nil {
		return "", fmt.Errorf("failed to sign token: %w", err)
	}

	return tokenString, nil
}

// ValidateToken validates a JWT token and returns the user ID.
func (s *AuthService) ValidateToken(tokenString string) (uint, error) {
	token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return s.jwtSecret, nil
	})

	if err != nil {
		return 0, ErrInvalidToken
	}

	if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
		userID := uint(claims["user_id"].(float64))
		return userID, nil
	}

	return 0, ErrInvalidToken
}

// GeneratePasswordResetToken generates a token for password reset.
// VULNERABILITY: Uses math/rand and MD5 - insecure for crypto purposes
// This is intentionally vulnerable for security rule testing.
func (s *AuthService) GeneratePasswordResetToken(email string) (string, error) {
	user, err := s.userRepo.GetByEmail(email)
	if err != nil {
		// Don't reveal if email exists
		return "", nil
	}

	// VULNERABILITY: math/rand is not cryptographically secure
	rand.Seed(time.Now().UnixNano())
	randomBytes := make([]byte, 16)
	for i := range randomBytes {
		randomBytes[i] = byte(rand.Intn(256))
	}

	// VULNERABILITY: MD5 is cryptographically weak
	data := fmt.Sprintf("%d-%s-%s", user.ID, email, string(randomBytes))
	hash := md5.Sum([]byte(data))
	token := hex.EncodeToString(hash[:])

	// In a real app, we'd store this token with expiration
	// For now, just return it
	return token, nil
}

// ChangePassword changes a user's password.
func (s *AuthService) ChangePassword(userID uint, currentPassword, newPassword string) error {
	user, err := s.userRepo.GetByID(userID)
	if err != nil {
		return err
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(currentPassword)); err != nil {
		return ErrInvalidCredentials
	}

	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(newPassword), bcrypt.DefaultCost)
	if err != nil {
		return fmt.Errorf("failed to hash password: %w", err)
	}

	user.PasswordHash = string(hashedPassword)
	return s.userRepo.Update(user)
}

// RefreshToken generates a new token from an existing valid token.
func (s *AuthService) RefreshToken(tokenString string) (string, error) {
	userID, err := s.ValidateToken(tokenString)
	if err != nil {
		return "", err
	}

	user, err := s.userRepo.GetByID(userID)
	if err != nil {
		return "", err
	}

	if !user.IsActive {
		return "", ErrInvalidCredentials
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"user_id": user.ID,
		"email":   user.Email,
		"exp":     time.Now().Add(24 * time.Hour).Unix(),
		"iat":     time.Now().Unix(),
	})

	return token.SignedString(s.jwtSecret)
}
