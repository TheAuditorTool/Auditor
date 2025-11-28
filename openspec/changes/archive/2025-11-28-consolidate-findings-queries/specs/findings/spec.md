# Findings Specification Delta

## ADDED Requirements

### Requirement: Unified Findings Data Source

All findings consumers SHALL query the `findings_consolidated` database table as the single source of truth. JSON files in `.pf/raw/` SHALL be write-only artifacts for human inspection.

#### Scenario: Final status queries database
- **WHEN** the pipeline generates final status (pipelines.py)
- **THEN** status SHALL be determined by querying findings_consolidated table
- **AND** the query SHALL filter by SECURITY_TOOLS (patterns, terraform, github-workflows, vulnerabilities)
- **AND** no JSON files SHALL be read for status determination
- **AND** no try/except blocks SHALL wrap the database query (ZERO FALLBACK)

#### Scenario: Summary command queries database
- **WHEN** the summary command aggregates findings (commands/summary.py)
- **THEN** findings SHALL be queried from findings_consolidated grouped by tool and severity
- **AND** no JSON files SHALL be read for findings aggregation

#### Scenario: ML training queries database
- **WHEN** ML functions parse findings data (insights/ml/intelligence.py)
- **THEN** pattern findings SHALL be queried from findings_consolidated WHERE tool = 'patterns'
- **AND** vulnerability findings SHALL be queried from findings_consolidated WHERE tool = 'vulnerabilities'
- **AND** taint and FCE data MAY continue reading from JSON (separate data types)

### Requirement: GitHub Workflows in findings_consolidated

GitHub Actions workflow security findings SHALL be inserted into the findings_consolidated table.

#### Scenario: Workflow analysis inserts findings
- **WHEN** `aud workflows analyze` completes analysis
- **THEN** all workflow findings SHALL be inserted into findings_consolidated
- **AND** tool column SHALL be 'github-workflows'
- **AND** category column SHALL be 'security'
- **AND** JSON file SHALL continue to be written (write-only artifact)

#### Scenario: Workflow findings queryable
- **WHEN** querying findings_consolidated WHERE tool = 'github-workflows'
- **THEN** all workflow security findings SHALL be returned
- **AND** findings SHALL include file, line, rule, message, severity

### Requirement: Vulnerabilities in findings_consolidated

CVE/vulnerability findings from dependency scanning SHALL be inserted into the findings_consolidated table.

#### Scenario: Vulnerability scan inserts findings
- **WHEN** vulnerability scanner completes (vulnerability_scanner.py)
- **THEN** all CVE findings SHALL be inserted into findings_consolidated
- **AND** tool column SHALL be 'vulnerabilities'
- **AND** rule column SHALL contain CVE ID (e.g., 'CVE-2023-12345')
- **AND** severity SHALL be mapped from CVSS score
- **AND** JSON file SHALL continue to be written (write-only artifact)

#### Scenario: CVSS to severity mapping
- **WHEN** a CVE has CVSS score >= 9.0
- **THEN** severity SHALL be 'critical'
- **WHEN** a CVE has CVSS score >= 7.0 and < 9.0
- **THEN** severity SHALL be 'high'
- **WHEN** a CVE has CVSS score >= 4.0 and < 7.0
- **THEN** severity SHALL be 'medium'
- **WHEN** a CVE has CVSS score < 4.0
- **THEN** severity SHALL be 'low'

### Requirement: Security vs Quality Tool Separation

Final status exit codes SHALL only be affected by security tools, not quality tools.

#### Scenario: Security tools affect exit code
- **WHEN** findings_consolidated contains critical/high findings from SECURITY_TOOLS
- **THEN** exit code SHALL reflect the highest severity found
- **AND** SECURITY_TOOLS SHALL include: patterns, terraform, github-workflows, vulnerabilities

#### Scenario: Quality tools do not affect exit code
- **WHEN** findings_consolidated contains findings from quality tools (ruff, mypy, eslint)
- **THEN** these findings SHALL NOT affect the final status exit code
- **AND** these findings SHALL be displayed in summary for informational purposes

## MODIFIED Requirements

### Requirement: ZERO FALLBACK for Findings Queries

All database queries for findings aggregation SHALL follow ZERO FALLBACK policy with no silent failures.

#### Scenario: Database query failure crashes
- **WHEN** a database query for findings fails (DB missing, corrupted, etc.)
- **THEN** the operation SHALL raise an exception and crash
- **AND** the operation SHALL NOT fall back to JSON files
- **AND** the operation SHALL NOT return a default empty result
- **AND** the error message SHALL indicate the database issue

#### Scenario: Empty results are valid
- **WHEN** findings_consolidated table exists but query returns zero rows
- **THEN** this SHALL be treated as a valid result (no findings)
- **AND** operation SHALL NOT crash
- **AND** status SHALL indicate clean/no findings (legitimately)

## REMOVED Requirements

### Requirement: JSON File Reading for Aggregation

**Reason**: Violates single source of truth. JSON files are derived artifacts, not authoritative data.

**What was removed**:
- Reading taint_analysis.json for final status (pipelines.py:1594-1612)
- Reading vulnerabilities.json for final status (pipelines.py:1614-1636)
- Reading findings.json for final status (pipelines.py:1638-1660) - file didn't even exist
- Reading lint.json for summary aggregation (commands/summary.py)
- Reading patterns.json for summary aggregation (commands/summary.py)
- All try/except fallback patterns around JSON loading

**Migration**:
- All queries now go to findings_consolidated table
- JSON files continue to be written but are never read for aggregation
- Consumers that need findings data query the database
