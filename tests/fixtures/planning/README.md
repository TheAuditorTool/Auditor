# Planning Fixtures

These fixtures provide realistic codebase scenarios for testing the planning system end-to-end.

## Directory Structure

Each scenario has:
- Source code files (Python/JS)
- Verification spec (YAML)
- Before/after states (for refactoring scenarios)

## Scenarios

### 1. refactor-auth/
**Scenario**: Migrate authentication from Auth0 to AWS Cognito
**Type**: Refactoring existing code
**Files**:
- `before/auth.py` - Original Auth0 implementation
- `after/auth.py` - Target Cognito implementation
- `spec.yaml` - Verification spec for migration

**Testing**:
```bash
# Index the "before" state
aud init refactor-auth/before
aud index

# Create plan
aud planning init --name "Auth Migration"
aud planning add-task 1 --title "Migrate to Cognito" --spec ../spec.yaml

# Verify (should show violations - Auth0 still present)
aud planning verify-task 1 1 --verbose

# Index the "after" state
aud init refactor-auth/after
aud index

# Re-verify (should pass - Cognito implemented)
aud planning verify-task 1 1 --auto-update
```

### 2. greenfield-api/
**Scenario**: Implement new Product CRUD API from scratch
**Type**: Greenfield development
**Files**:
- `src/products.py` - Complete Flask API implementation
- `src/models.py` - SQLAlchemy Product model
- `spec.yaml` - Verification spec for all CRUD operations

**Testing**:
```bash
# Index the implementation
aud init greenfield-api
aud index

# Create plan
aud planning init --name "Product API"
aud planning add-task 1 --title "Implement CRUD" --spec spec.yaml

# Verify (should pass - all endpoints implemented)
aud planning verify-task 1 1 --verbose
```

### 3. migration-database/
**Scenario**: Rename database model (User → Account)
**Type**: Large-scale refactoring/migration
**Files**:
- `before/models.py` - Original User model
- `after/models.py` - Renamed Account model
- `spec.yaml` - Verification spec for rename

**Testing**:
```bash
# Index "before" state
aud init migration-database/before
aud index

# Create plan
aud planning init --name "Model Rename"
aud planning add-task 1 --title "Rename User to Account" --spec ../spec.yaml

# Verify (should show violations - User still exists)
aud planning verify-task 1 1 --verbose

# Index "after" state
aud init migration-database/after
aud index

# Re-verify (should pass - Account model exists, User removed)
aud planning verify-task 1 1 --auto-update
```

## Integration Test Usage

These fixtures can be used to test:
- Full planning workflow (init → add-task → verify → archive)
- Verification spec accuracy
- Database query performance on real code
- Symbol resolution across different patterns
- Regression detection (index before → index after → verify)

## Expected Query Patterns

When indexed, these fixtures test:
- **Symbol extraction**: Classes, functions, variables
- **Import resolution**: auth0, aws_cognito, flask, sqlalchemy
- **API route detection**: Flask Blueprint routes
- **ORM model detection**: SQLAlchemy models and relationships
- **Assignment tracking**: Environment variable access
- **Function call detection**: Method invocations

All queries should use proper JOINs and indexes, never LIKE % patterns.
