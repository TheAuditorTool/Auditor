# Database Schema Specification Delta

## MODIFIED Requirements

### Requirement: findings_consolidated Table Schema

The findings_consolidated table SHALL store all security findings with tool-specific metadata in normalized columns instead of JSON blobs.

The table SHALL include:
- 13 base columns (id, file, line, column, rule, tool, message, severity, category, confidence, code_snippet, cwe, timestamp)
- 3 mypy-specific columns (mypy_severity, mypy_code, mypy_hint)
- 8 cfg-analysis columns (cfg_complexity, cfg_block_count, cfg_edge_count, cfg_start_line, cfg_end_line, cfg_function, cfg_has_loops, cfg_max_nesting)
- 7 graph-analysis columns (graph_centrality, graph_churn, graph_in_degree, graph_out_degree, graph_loc, graph_score, graph_node_id)
- 4 terraform columns (tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context)
- 1 fallback column (misc_json) for complex nested data that cannot be normalized

The table SHALL NOT include a `details_json` column for tool-specific metadata.

#### Scenario: Tool-specific columns populated correctly

- **WHEN** a mypy finding is written to findings_consolidated
- **THEN** the mypy_severity, mypy_code, and mypy_hint columns SHALL contain the appropriate values
- **AND** all other tool-specific columns SHALL be NULL

#### Scenario: Sparse column storage efficiency

- **WHEN** a finding is written for a tool that does not use certain columns
- **THEN** those columns SHALL be NULL
- **AND** the NULL values SHALL NOT consume storage space in the row payload

#### Scenario: FCE queries use direct column access

- **WHEN** FCE queries findings for correlation analysis
- **THEN** queries SHALL use direct column access (e.g., `SELECT cfg_complexity`)
- **AND** queries SHALL NOT use json.loads() on any column
- **AND** queries SHALL NOT use try/except for JSON parsing

#### Scenario: Partial indexes for sparse columns

- **WHEN** the database schema is created
- **THEN** partial indexes SHALL exist for cfg_complexity, graph_score, graph_centrality, mypy_code
- **AND** each partial index SHALL include a WHERE clause filtering for IS NOT NULL

## ADDED Requirements

### Requirement: Taint Data Source Separation

FCE taint analysis SHALL query the taint_flows table directly instead of parsing findings_consolidated.misc_json.

#### Scenario: Taint data loaded from taint_flows

- **WHEN** FCE loads taint data for correlation
- **THEN** data SHALL be queried from the taint_flows table
- **AND** the query SHALL NOT access findings_consolidated.misc_json
- **AND** taint path details SHALL be reconstructed from taint_flows columns

## REMOVED Requirements

### Requirement: details_json Column Storage

**Reason**: Replaced by tool-specific columns and misc_json fallback

**Migration**:
- details_json column renamed to misc_json
- Only complex nested data (taint paths) uses misc_json
- All scalar tool metadata stored in dedicated columns
- Database regenerates fresh on `aud full`, no migration needed
