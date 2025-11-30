package handlers

import (
	"net/http"
	"strings"

	"github.com/example/calorie-tracker/internal/services"
	"github.com/gin-gonic/gin"
)

// AuthHandler handles authentication endpoints.
type AuthHandler struct {
	authService *services.AuthService
}

// NewAuthHandler creates a new AuthHandler.
func NewAuthHandler(authService *services.AuthService) *AuthHandler {
	return &AuthHandler{authService: authService}
}

// Register handles user registration.
// @Summary Register a new user
// @Tags auth
// @Accept json
// @Produce json
// @Param request body services.RegisterRequest true "Registration data"
// @Success 201 {object} map[string]interface{}
// @Failure 400 {object} map[string]string
// @Router /auth/register [post]
func (h *AuthHandler) Register(c *gin.Context) {
	var req services.RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	user, err := h.authService.Register(req)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"message": "Registration successful",
		"user": gin.H{
			"id":    user.ID,
			"email": user.Email,
			"name":  user.Name,
		},
	})
}

// LoginRequest contains login credentials.
type LoginRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required"`
}

// Login handles user login.
// @Summary Login user
// @Tags auth
// @Accept json
// @Produce json
// @Param request body LoginRequest true "Login credentials"
// @Success 200 {object} map[string]string
// @Failure 401 {object} map[string]string
// @Router /auth/login [post]
func (h *AuthHandler) Login(c *gin.Context) {
	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	token, err := h.authService.Login(req.Email, req.Password)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid credentials"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"token":   token,
		"message": "Login successful",
	})
}

// RefreshToken handles token refresh.
// @Summary Refresh JWT token
// @Tags auth
// @Security Bearer
// @Produce json
// @Success 200 {object} map[string]string
// @Failure 401 {object} map[string]string
// @Router /auth/refresh [post]
func (h *AuthHandler) RefreshToken(c *gin.Context) {
	authHeader := c.GetHeader("Authorization")
	if authHeader == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Missing authorization header"})
		return
	}

	tokenString := strings.TrimPrefix(authHeader, "Bearer ")
	newToken, err := h.authService.RefreshToken(tokenString)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid or expired token"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"token": newToken,
	})
}

// ForgotPasswordRequest contains email for password reset.
type ForgotPasswordRequest struct {
	Email string `json:"email" binding:"required,email"`
}

// ForgotPassword initiates password reset.
// @Summary Request password reset
// @Tags auth
// @Accept json
// @Produce json
// @Param request body ForgotPasswordRequest true "Email address"
// @Success 200 {object} map[string]string
// @Router /auth/forgot-password [post]
func (h *AuthHandler) ForgotPassword(c *gin.Context) {
	var req ForgotPasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Generate reset token (vulnerable implementation for testing)
	token, _ := h.authService.GeneratePasswordResetToken(req.Email)

	// In production, you'd send this via email
	// For demo purposes, we'll include it in the response (don't do this in production!)
	c.JSON(http.StatusOK, gin.H{
		"message": "If your email exists, you will receive a password reset link",
		"token":   token, // Remove this in production
	})
}

// ChangePasswordRequest contains password change data.
type ChangePasswordRequest struct {
	CurrentPassword string `json:"current_password" binding:"required"`
	NewPassword     string `json:"new_password" binding:"required,min=8"`
}

// ChangePassword handles password change for authenticated users.
// @Summary Change password
// @Tags auth
// @Security Bearer
// @Accept json
// @Produce json
// @Param request body ChangePasswordRequest true "Password change data"
// @Success 200 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /auth/change-password [post]
func (h *AuthHandler) ChangePassword(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	var req ChangePasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.authService.ChangePassword(userID.(uint), req.CurrentPassword, req.NewPassword); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Password changed successfully",
	})
}
