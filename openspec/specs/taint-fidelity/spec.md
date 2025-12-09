# taint-fidelity Specification

## Purpose
TBD - created by archiving change add-taint-fidelity. Update Purpose after archive.
## Requirements
### Requirement: Taint Pipeline Fidelity Verification

The taint analysis pipeline SHALL verify data integrity at each stage using manifest/receipt reconciliation to ensure no vulnerability paths are silently lost.

#### Scenario: Discovery checkpoint catches zero sources

- **WHEN** the discovery phase completes with 0 sources found
- **AND** the repository contains HTTP endpoint handlers
- **THEN** the system SHALL log a warning: "Discovery found 0 sources - is this expected?"
- **AND** continue processing (not fail)

#### Scenario: Discovery checkpoint catches zero sinks

- **WHEN** the discovery phase completes with 0 sinks found
- **AND** the repository contains SQL/exec/eval calls
- **THEN** the system SHALL log a warning: "Discovery found 0 sinks - is this expected?"
- **AND** continue processing (not fail)

#### Scenario: Analysis checkpoint catches stalled pipeline

- **WHEN** the IFDS analysis phase processes 0 sinks
- **AND** the discovery phase found >0 sinks to analyze
- **THEN** the system SHALL raise `TaintFidelityError` in strict mode
- **AND** log the error: "Analysis processed 0/N sinks - pipeline stalled"

#### Scenario: Dedup checkpoint warns on aggressive removal

- **WHEN** deduplication removes >50% of paths
- **THEN** the system SHALL log a warning with removal count and ratio
- **AND** suggest checking for hash collisions
- **AND** continue processing (not fail)

#### Scenario: DB output checkpoint catches silent failure

- **WHEN** the manifest indicates N paths to write
- **AND** the DB insert results in 0 rows
- **THEN** the system SHALL raise `TaintFidelityError` in strict mode
- **AND** log: "DB Output: N paths to write, 0 written (100% LOSS)"

#### Scenario: JSON output checkpoint catches data loss

- **WHEN** the manifest indicates N vulnerabilities
- **AND** the JSON file contains 0 vulnerabilities
- **THEN** the system SHALL raise `TaintFidelityError` in strict mode
- **AND** log: "JSON Output: N paths to write, 0 in JSON (100% LOSS)"

---

### Requirement: Fidelity Strict Mode Control

The fidelity system SHALL support strict and non-strict modes to allow debugging without blocking pipeline execution.

#### Scenario: Strict mode raises on error

- **WHEN** `reconcile_taint_fidelity()` is called with `strict=True`
- **AND** a fidelity error is detected
- **THEN** the system SHALL raise `TaintFidelityError` with details

#### Scenario: Non-strict mode logs but continues

- **WHEN** `reconcile_taint_fidelity()` is called with `strict=False`
- **AND** a fidelity error is detected
- **THEN** the system SHALL log the error
- **AND** return a result dict with `status="FAILED"`
- **AND** NOT raise an exception

#### Scenario: Environment variable disables strict mode

- **WHEN** `TAINT_FIDELITY_STRICT=0` is set in environment
- **AND** `reconcile_taint_fidelity()` is called with `strict=True`
- **THEN** the system SHALL override to non-strict mode
- **AND** log errors but NOT raise exceptions

---

### Requirement: Fidelity Logging Integration

The fidelity system SHALL log status at each checkpoint using the existing logger infrastructure.

#### Scenario: Successful fidelity check logs OK

- **WHEN** a fidelity checkpoint passes
- **THEN** the system SHALL log at INFO level: "[Stage]: [counts] [Fidelity: OK]"

#### Scenario: Warning fidelity check logs WARNING

- **WHEN** a fidelity checkpoint has warnings but no errors
- **THEN** the system SHALL log at WARNING level with details
- **AND** return `status="WARNING"` in the result

#### Scenario: Failed fidelity check logs ERROR

- **WHEN** a fidelity checkpoint fails
- **THEN** the system SHALL log at ERROR level with details
- **AND** return `status="FAILED"` in the result

