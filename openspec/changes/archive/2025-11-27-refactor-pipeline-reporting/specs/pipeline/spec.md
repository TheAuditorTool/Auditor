# Pipeline Specification Delta

## MODIFIED Requirements

### Requirement: Findings Aggregation Source

The pipeline final status SHALL be determined by querying the findings_consolidated database table directly, not by reading JSON artifact files.

#### Scenario: Database query for aggregation
- **WHEN** the pipeline generates final status (pipelines.py around line 1588)
- **THEN** status SHALL be determined by querying findings_consolidated table
- **AND** the query SHALL use `SELECT severity, COUNT(*) FROM findings_consolidated WHERE tool IN (...) GROUP BY severity`
- **AND** no JSON files SHALL be read for status determination
- **AND** no try/except blocks SHALL wrap the database query

#### Scenario: Security vs quality tool separation
- **WHEN** determining final status severity
- **THEN** only SECURITY_TOOLS (patterns, taint, terraform, cdk) SHALL affect status
- **AND** QUALITY_TOOLS (ruff, eslint, mypy) SHALL NOT affect security status
- **AND** ANALYSIS_TOOLS (cfg-analysis, graph-analysis) SHALL NOT affect security status
- **AND** SECURITY_TOOLS SHALL be defined as a frozenset constant near top of pipelines.py

#### Scenario: Critical findings detection
- **WHEN** findings_consolidated contains critical severity findings from security tools
- **THEN** final status SHALL indicate "[CRITICAL]" (not "[CLEAN]")
- **AND** exit code SHALL be CRITICAL_SEVERITY
- **AND** findings breakdown SHALL show actual counts from database (not zeros)

#### Scenario: Return dict structure preserved
- **WHEN** run_full_pipeline() completes (pipelines.py line 1677)
- **THEN** return dict SHALL include findings.critical, findings.high, findings.medium, findings.low
- **AND** findings.total_vulnerabilities SHALL equal sum of severity counts
- **AND** structure SHALL be identical to current structure for full.py and journal.py compatibility

## ADDED Requirements

### Requirement: JSON Artifacts Write-Only

JSON files in .pf/raw/ SHALL be write-only artifacts for human inspection and SHALL NOT be consumed by pipeline aggregation logic.

#### Scenario: JSON files not read for aggregation
- **WHEN** the pipeline generates final status
- **THEN** the pipeline SHALL NOT read patterns.json (formerly misnamed as findings.json)
- **AND** the pipeline SHALL NOT read taint_analysis.json for status aggregation
- **AND** the pipeline SHALL NOT read vulnerabilities.json for status aggregation
- **AND** the pipeline SHALL NOT use json.load() in the aggregation code section (lines 1588-1660)
- **AND** JSON files SHALL continue to be written for human inspection

### Requirement: Zero Fallback Status Logic

The final status determination logic SHALL follow ZERO FALLBACK policy with no try/except fallbacks.

#### Scenario: Database query failure crashes pipeline
- **WHEN** the database query for findings fails (DB missing, corrupted, etc.)
- **THEN** the pipeline SHALL raise an exception and crash
- **AND** the pipeline SHALL NOT fall back to JSON files
- **AND** the pipeline SHALL NOT return a default "[CLEAN]" status
- **AND** the error message SHALL indicate the database issue

#### Scenario: Fresh project with no findings
- **WHEN** findings_consolidated table exists but is empty
- **THEN** return dict SHALL have all severity counts as 0
- **AND** status SHALL be "[CLEAN]" (legitimately no findings)

### Requirement: _get_findings_from_db Helper Function

A helper function SHALL encapsulate the database query logic.

#### Scenario: Function signature and location
- **WHEN** _get_findings_from_db is defined
- **THEN** it SHALL be defined in pipelines.py before run_full_pipeline()
- **AND** it SHALL accept root: Path as argument
- **AND** it SHALL return dict with keys: critical, high, medium, low, total_vulnerabilities

#### Scenario: Function uses SECURITY_TOOLS constant
- **WHEN** _get_findings_from_db queries the database
- **THEN** it SHALL filter by tool IN (SECURITY_TOOLS)
- **AND** SECURITY_TOOLS SHALL be frozenset({'patterns', 'taint', 'terraform', 'cdk'})

## REMOVED Requirements

### Requirement: Graceful Degradation on Missing Files

**Reason**: Violates ZERO FALLBACK policy - silent failures hid the "[CLEAN]" bug for unknown duration

**What was removed**:
- try/except blocks around taint_analysis.json reading (lines 1596-1612)
- try/except blocks around vulnerabilities.json reading (lines 1616-1636)
- try/except blocks around findings.json reading (lines 1640-1660)
- All "continue without stats" fallback comments

**Migration**:
- Database query crashes if DB unavailable (correct ZERO FALLBACK behavior)
- No JSON file reading for aggregation
- Developers must ensure DB exists before calling aggregation

### Requirement: findings.json Reading

**Reason**: File doesn't exist - was always reading non-existent file

**What was removed**:
- Line 1638: `patterns_path = Path(root) / ".pf" / "raw" / "findings.json"`
- The actual file is `patterns.json` but this code path never worked
- No migration needed - this was dead code producing zero findings
