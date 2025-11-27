## ADDED Requirements

### Requirement: Polyglot Taint Registry

The taint analysis system SHALL support language-aware pattern loading from database tables.

The TaintRegistry SHALL provide methods to retrieve source, sink, and sanitizer patterns for specific languages (Python, JavaScript, Rust).

The system SHALL load patterns from:
- `framework_safe_sinks` table for sanitizer patterns
- `validation_framework_usage` table for validation patterns
- `api_endpoints` table for entry point detection

#### Scenario: Python source pattern retrieval
- **WHEN** `registry.get_source_patterns('python')` is called
- **THEN** returns patterns including `['request.args', 'request.form', 'request.json']`

#### Scenario: JavaScript source pattern retrieval
- **WHEN** `registry.get_source_patterns('javascript')` is called
- **THEN** returns patterns including `['req.body', 'req.params', 'req.query']`

#### Scenario: Rust source pattern retrieval
- **WHEN** `registry.get_source_patterns('rust')` is called
- **THEN** returns patterns including `['web::Json', 'web::Query', 'web::Path']`

---

### Requirement: Type Resolver for ORM Aliasing

The taint analysis system SHALL provide a TypeResolver component that determines if two variables represent the same Data Model type without requiring a direct graph edge.

The TypeResolver SHALL read model metadata from graph nodes populated by ORM strategies.

#### Scenario: Same model detection
- **WHEN** two variables in different files both have metadata `model: 'User'`
- **AND** `type_resolver.is_same_type(node_a, node_b)` is called
- **THEN** returns `True`

#### Scenario: Different model detection
- **WHEN** variable A has metadata `model: 'User'` and variable B has metadata `model: 'Post'`
- **AND** `type_resolver.is_same_type(node_a, node_b)` is called
- **THEN** returns `False`

#### Scenario: Controller file detection
- **WHEN** a file path is checked with `type_resolver.is_controller_file(path)`
- **AND** the file is registered in `api_endpoints` table
- **THEN** returns `True`

---

### Requirement: Database-Driven Sanitizer Detection

The SanitizerRegistry SHALL load validation patterns from the TaintRegistry instead of hardcoded lists.

The system SHALL NOT contain duplicate pattern lists in the same file.

#### Scenario: Zod validation detection
- **WHEN** a taint path passes through a Zod schema validation
- **AND** the schema is registered in `validation_framework_usage` table
- **THEN** the path is marked as sanitized

#### Scenario: Express-validator detection
- **WHEN** a taint path passes through express-validator middleware
- **AND** the validator is registered in `framework_safe_sinks` table
- **THEN** the path is marked as sanitized

#### Scenario: Pydantic validation detection (Python)
- **WHEN** a taint path passes through a Pydantic model validation
- **AND** the model is registered in `validation_framework_usage` table
- **THEN** the path is marked as sanitized

---

## MODIFIED Requirements

### Requirement: Entry Point Detection

The taint analyzer SHALL detect entry points using database queries and registry lookups instead of hardcoded patterns.

The system SHALL query the `api_endpoints` table to determine if a function is an API handler.

The system SHALL use `TaintRegistry.get_source_patterns(language)` to identify taint sources.

#### Scenario: Express endpoint detection
- **WHEN** analyzing a file containing Express route handlers
- **AND** the handlers are registered in `express_middleware_chains` table
- **THEN** `req.body`, `req.params`, `req.query` are identified as taint sources

#### Scenario: Flask endpoint detection
- **WHEN** analyzing a file containing Flask route handlers
- **AND** the handlers are registered in `api_endpoints` table
- **THEN** `request.args`, `request.form`, `request.json` are identified as taint sources

#### Scenario: Django endpoint detection
- **WHEN** analyzing a file containing Django view functions
- **AND** the views are registered in `python_django_views` table
- **THEN** `request.GET`, `request.POST`, `request.body` are identified as taint sources

---

## REMOVED Requirements

### Requirement: Hardcoded Express Patterns

**Reason**: Replaced with database-driven pattern lookup supporting multiple languages.

**Migration**: All Express patterns moved to `framework_safe_sinks` and `validation_framework_usage` tables. Existing Express detection continues to work through database queries.
