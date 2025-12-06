# Calorie Tracker API

A RESTful API for tracking daily calorie intake, built with Go, Gin, and GORM.

## Features

- User registration and JWT authentication
- Food database with nutritional information
- Meal and food entry logging
- Daily calorie tracking and summaries
- Weekly progress reports
- Background jobs for notifications and cleanup

## Project Structure

```
go-calorie-tracker/
├── cmd/
│   └── server/
│       └── main.go           # Application entry point
├── internal/
│   ├── database/
│   │   └── database.go       # Database connection and migrations
│   ├── handlers/
│   │   ├── auth_handler.go   # Authentication endpoints
│   │   ├── food_handler.go   # Food CRUD endpoints
│   │   └── tracking_handler.go # Tracking endpoints
│   ├── middleware/
│   │   ├── auth.go           # JWT authentication middleware
│   │   └── logging.go        # Request logging middleware
│   ├── models/
│   │   ├── user.go           # User model
│   │   ├── food.go           # Food and FoodEntry models
│   │   └── meal.go           # Meal and DailyLog models
│   ├── repository/
│   │   ├── user_repository.go
│   │   └── food_repository.go
│   └── services/
│       ├── auth_service.go   # Authentication logic
│       ├── tracking_service.go # Food tracking logic
│       └── jobs_service.go   # Background jobs
├── pkg/
│   └── config/
│       └── config.go         # Configuration management
├── go.mod
└── README.md
```

## Running the Application

### Prerequisites

- Go 1.21 or later
- SQLite3

### Quick Start

```bash
# Clone and navigate to the project
cd go-calorie-tracker

# Download dependencies
go mod download

# Run the server
go run cmd/server/main.go
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| PORT | 8080 | Server port |
| DATABASE_PATH | calorie_tracker.db | SQLite database path |
| JWT_SECRET | change-this-in-production | JWT signing secret |
| DEBUG | false | Enable debug logging |

### API Endpoints

#### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get JWT token
- `POST /api/v1/auth/refresh` - Refresh JWT token (protected)
- `POST /api/v1/auth/change-password` - Change password (protected)
- `POST /api/v1/auth/forgot-password` - Request password reset

#### Foods
- `GET /api/v1/foods/:id` - Get food by ID
- `GET /api/v1/foods/search?q=query` - Search foods
- `GET /api/v1/foods/barcode/:barcode` - Get food by barcode
- `GET /api/v1/foods/popular` - Get popular foods
- `POST /api/v1/foods` - Create food (protected)
- `PUT /api/v1/foods/:id` - Update food (protected)
- `DELETE /api/v1/foods/:id` - Delete food (protected)

#### Tracking
- `POST /api/v1/tracking/entries` - Log food entry (protected)
- `GET /api/v1/tracking/entries?date=YYYY-MM-DD` - Get entries for date (protected)
- `DELETE /api/v1/tracking/entries/:id` - Delete entry (protected)
- `POST /api/v1/tracking/meals` - Create meal (protected)
- `GET /api/v1/tracking/meals/:id` - Get meal details (protected)
- `GET /api/v1/tracking/today` - Get today's summary (protected)
- `GET /api/v1/tracking/daily?date=YYYY-MM-DD` - Get daily log (protected)
- `GET /api/v1/tracking/weekly` - Get weekly progress (protected)

### Example Usage

```bash
# Register a user
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123","name":"John Doe"}'

# Login
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'

# Create a food item (with token)
curl -X POST http://localhost:8080/api/v1/foods \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "Apple",
    "serving_size": 182,
    "serving_unit": "g",
    "calories": 95,
    "protein": 0.5,
    "carbs": 25,
    "fat": 0.3,
    "fiber": 4.4
  }'

# Log a food entry
curl -X POST http://localhost:8080/api/v1/tracking/entries \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"food_id": 1, "quantity": 1.0}'

# Get today's summary
curl http://localhost:8080/api/v1/tracking/today \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Testing

This project serves as a test fixture for TheAuditor security scanner. It contains intentional vulnerabilities for testing purposes:

1. **SQL Injection** - `food_repository.go:Search()` has vulnerable query building
2. **Weak Crypto** - `auth_service.go:GeneratePasswordResetToken()` uses MD5 and math/rand
3. **Race Condition** - `tracking_service.go` has unprotected global counter
4. **Captured Loop Variable** - `jobs_service.go` demonstrates the classic Go race condition

**DO NOT USE IN PRODUCTION** - This code contains intentional security vulnerabilities.

## License

MIT License - For testing purposes only.
