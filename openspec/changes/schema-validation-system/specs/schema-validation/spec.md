# Schema Validation Capability

## ADDED Requirements

### Requirement: Staleness Detection
The system SHALL detect when generated code is out of sync with schema definitions using SHA-256 hash comparison.

#### Scenario: Schema change detected
- **WHEN** schema is modified and hash no longer matches
- **THEN** validation detects staleness and reports mismatch

#### Scenario: Generated files missing
- **WHEN** one or more generated files do not exist
- **THEN** validation detects missing files and reports which files are absent

### Requirement: Development Mode Auto-Regeneration
The system SHALL automatically regenerate stale code in development mode without requiring manual intervention.

#### Scenario: Auto-fix in dev mode
- **WHEN** running in development mode (git repo exists)
- **AND** generated code is stale
- **THEN** system auto-regenerates code and logs warning
- **AND** execution continues normally

### Requirement: Production Mode Fail-Safe
The system SHALL fail immediately in production mode when stale code is detected to prevent runtime errors.

#### Scenario: Hard fail in production
- **WHEN** running in production mode (pip installed)
- **AND** generated code is stale
- **THEN** system exits with error code
- **AND** displays clear remediation instructions

### Requirement: CLI Commands
The system SHALL provide manual validation and regeneration commands for developer control.

#### Scenario: Check command validates
- **WHEN** developer runs `aud schema --check`
- **THEN** system validates integrity and reports status
- **AND** does not modify any files (dry-run)

#### Scenario: Regen command forces regeneration
- **WHEN** developer runs `aud schema --regen`
- **THEN** system regenerates all 4 generated files
- **AND** updates schema hash
- **AND** reports success

### Requirement: Validation Bypass
The system SHALL allow validation bypass via environment variable for emergency situations.

#### Scenario: Emergency bypass
- **WHEN** THEAUDITOR_NO_VALIDATION=1 environment variable is set
- **THEN** validation is skipped entirely
- **AND** execution continues without checks

### Requirement: CI/CD Enforcement
The system SHALL enforce schema integrity in test suite to catch staleness before merge.

#### Scenario: Test suite catches staleness
- **WHEN** test suite runs in CI/CD
- **AND** generated code is stale
- **THEN** tests fail with clear error message
- **AND** merge is blocked

### Requirement: Performance Constraint
The validation system SHALL complete in less than 50 milliseconds to avoid noticeable import overhead.

#### Scenario: Fast validation
- **WHEN** validation runs on import
- **THEN** total time is less than 50ms
- **AND** result is cached for session
