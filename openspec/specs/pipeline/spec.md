# pipeline Specification

## Purpose
Pipeline orchestration for TheAuditor, including final status reporting and findings aggregation after all analysis phases complete.

## Requirements

### Requirement: Final Status Reporting
The pipeline SHALL report final status after all analysis phases complete, indicating security findings severity.

#### Scenario: Status reflects findings severity
- **WHEN** the pipeline completes all analysis phases
- **THEN** final status SHALL indicate whether critical/high severity issues were found
- **AND** status SHALL be displayed to the user via full.py

#### Scenario: Clean status when no security issues
- **WHEN** the pipeline completes with no critical or high severity security findings
- **THEN** final status SHALL indicate "[CLEAN]"

#### Scenario: Critical status when critical issues found
- **WHEN** the pipeline completes with critical severity security findings
- **THEN** final status SHALL indicate "[CRITICAL]"
- **AND** exit code SHALL be CRITICAL_SEVERITY

### Requirement: Findings Aggregation Source
The pipeline final status SHALL be determined by reading JSON artifact files from .pf/raw/ directory.

#### Scenario: JSON files read for aggregation
- **WHEN** the pipeline generates final status
- **THEN** the pipeline SHALL read taint_analysis.json, vulnerabilities.json, and findings.json
- **AND** severity counts SHALL be aggregated from these files

### Requirement: Graceful Degradation on Missing Files
The pipeline SHALL gracefully handle missing or malformed JSON files during aggregation.

#### Scenario: Missing JSON file handling
- **WHEN** a JSON artifact file does not exist
- **THEN** the pipeline SHALL treat that file's findings as empty
- **AND** the pipeline SHALL continue processing other files

### Requirement: Findings Return Structure
The pipeline SHALL return findings counts in a dict consumed by full.py and journal.py.

#### Scenario: Findings dict structure
- **WHEN** the pipeline completes
- **THEN** return dict SHALL include findings.critical, findings.high, findings.medium, findings.low
- **AND** findings.total_vulnerabilities SHALL be included for journal.py
