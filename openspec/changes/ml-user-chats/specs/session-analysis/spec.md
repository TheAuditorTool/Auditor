# session-analysis Specification

## Purpose
Provide deterministic analysis of AI coding assistant session logs to enable workflow compliance checking, diff risk scoring, and statistical learning of successful vs failed development patterns.

## Requirements

### Requirement: Session Log Parsing

The system SHALL parse Claude Code session logs in JSONL format from `~/.claude/projects/<project>/*.jsonl`.

The system SHALL extract user messages, assistant messages, and tool calls from each session.

The system SHALL extract tool call parameters including file_path, old_string, new_string for Edit and Write tool calls.

The system SHALL handle timezone-aware timestamps for chronological ordering.

The system SHALL skip malformed JSONL entries without failing the entire parse.

#### Scenario: Parse valid session log
- **GIVEN** a JSONL file with 10 message entries (5 user, 5 assistant)
- **WHEN** SessionParser.parse_session() is called
- **THEN** a Session object is returned with 5 user_messages and 5 assistant_messages
- **AND** all tool calls are extracted with correct parameters

#### Scenario: Parse session with Edit tool call
- **GIVEN** a JSONL file with an Edit tool call changing "old_code" to "new_code" in file.py
- **WHEN** SessionParser.parse_session() is called
- **THEN** the tool_call has tool_name='Edit'
- **AND** input_params contains file_path='file.py', old_string='old_code', new_string='new_code'

#### Scenario: Parse session with malformed entry
- **GIVEN** a JSONL file with 10 entries where entry 5 is malformed JSON
- **WHEN** SessionParser.parse_session() is called
- **THEN** parsing continues successfully
- **AND** entries 1-4 and 6-10 are extracted correctly
- **AND** entry 5 is skipped with warning logged

#### Scenario: Parse session with timezone timestamps
- **GIVEN** a JSONL file with timestamps in UTC timezone
- **WHEN** SessionParser.parse_session() is called
- **THEN** all timestamps are timezone-aware datetime objects
- **AND** sessions can be sorted chronologically without errors

---

### Requirement: Diff Risk Scoring

The system SHALL score code diffs from Edit/Write tool calls using TheAuditor's SAST pipeline.

The system SHALL run taint analysis on each diff to detect security vulnerabilities (SQL injection, XSS, command injection).

The system SHALL run pattern detection on each diff to detect anti-patterns (f-strings in SQL, hardcoded secrets).

The system SHALL check FCE correlations for each modified file to detect incomplete refactors.

The system SHALL query RCA statistics for each modified file to assess historical risk.

The system SHALL aggregate scores from all analyses into a single risk_score (0.0-1.0).

The system SHALL write diffs to temporary files with secure permissions (0600) for analysis.

The system SHALL clean up temporary files after scoring.

#### Scenario: Score diff with no findings
- **GIVEN** a diff changing "x = 1" to "x = 2" in math.py
- **WHEN** DiffScorer.score_diff() is called
- **THEN** risk_score is 0.0-0.1 (low risk)
- **AND** findings dict shows no taint, no patterns, no FCE issues

#### Scenario: Score diff with SQL injection
- **GIVEN** a diff adding `cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")`
- **WHEN** DiffScorer.score_diff() is called
- **THEN** risk_score is 0.8-1.0 (critical risk)
- **AND** findings['taint'] contains SQL injection vulnerability
- **AND** findings['patterns'] contains f-string in SQL pattern

#### Scenario: Score diff with incomplete refactor
- **GIVEN** a diff modifying auth.py
- **AND** FCE shows auth_service.py should also be modified but wasn't touched
- **WHEN** DiffScorer.score_diff() is called
- **THEN** risk_score includes FCE penalty (0.4-0.6)
- **AND** findings['fce'] contains incomplete refactor warning

#### Scenario: Score diff in historically risky file
- **GIVEN** a diff modifying api.py
- **AND** RCA stats show api.py has 78% historical failure rate
- **WHEN** DiffScorer.score_diff() is called
- **THEN** risk_score includes RCA penalty (0.5-0.7)
- **AND** findings['rca'] contains historical risk warning

#### Scenario: Temp file cleanup after scoring
- **GIVEN** a diff that requires temp file creation
- **WHEN** DiffScorer.score_diff() is called
- **THEN** temp file is created with 0600 permissions
- **AND** temp file is deleted after scoring completes
- **AND** no temp files remain in temp directory

---

### Requirement: Workflow Compliance Checking

The system SHALL parse workflow definitions from planning.md.

The system SHALL validate that agent execution follows defined workflow sequences.

The system SHALL check that `aud blueprint` runs before file modifications (MANDATORY).

The system SHALL check that `aud query` runs before edit operations (MANDATORY).

The system SHALL check that files are read before being edited (no blind edits).

The system SHALL calculate compliance_score (0.0-1.0) based on checks passed.

The system SHALL report violations with specific check names (blueprint_first, query_before_edit, no_blind_reads).

#### Scenario: Check compliant session
- **GIVEN** a session with tool sequence: [Bash: aud blueprint, Bash: aud query, Read: api.py, Edit: api.py]
- **WHEN** WorkflowChecker.check_compliance() is called
- **THEN** compliant is True
- **AND** compliance_score is 1.0
- **AND** violations is empty list

#### Scenario: Check non-compliant session (skip blueprint)
- **GIVEN** a session with tool sequence: [Read: api.py, Edit: api.py]
- **AND** no `aud blueprint` call
- **WHEN** WorkflowChecker.check_compliance() is called
- **THEN** compliant is False
- **AND** compliance_score is 0.33 (1/3 checks passed)
- **AND** violations contains 'blueprint_first'

#### Scenario: Check non-compliant session (blind edit)
- **GIVEN** a session with tool sequence: [Bash: aud blueprint, Edit: api.py]
- **AND** api.py was never read
- **WHEN** WorkflowChecker.check_compliance() is called
- **THEN** compliant is False
- **AND** violations contains 'no_blind_reads'

#### Scenario: Check session with missing planning.md
- **GIVEN** a project without planning.md file
- **WHEN** WorkflowChecker.__init__() is called
- **THEN** default workflow is used (blueprint_first, query_before_edit, no_blind_reads)
- **AND** no errors are raised

---

### Requirement: Session Execution Persistence

The system SHALL store session execution data in session_executions table.

The system SHALL store session execution data to JSON files in .pf/session_analysis/ (dual-write principle).

The system SHALL create session_executions table with columns: session_id, task_description, workflow_compliant, compliance_score, risk_score, task_completed, corrections_needed, rollback, timestamp, tool_call_count, files_modified, user_message_count, user_engagement_rate, diffs_scored.

The system SHALL calculate user_engagement_rate as user_message_count / tool_call_count.

The system SHALL treat user_engagement_rate as INVERSE METRIC where lower values indicate better performance (agent is self-sufficient).

The system SHALL create indexes on session_id, timestamp, workflow_compliant.

The system SHALL use parameterized queries for all database writes (prevent SQL injection).

The system SHALL query session_executions table for ML feature extraction.

The system SHALL provide correlation analysis queries (compliant vs non-compliant outcomes).

#### Scenario: Store session execution to database
- **GIVEN** a SessionExecution object with all fields populated
- **WHEN** SessionExecutionStore.store_execution() is called
- **THEN** a row is inserted into session_executions table
- **AND** all fields match the SessionExecution object

#### Scenario: Store session execution to JSON (dual-write)
- **GIVEN** a SessionExecution object with all fields populated
- **WHEN** SessionExecutionStore.store_execution() is called
- **THEN** a JSON file is written to .pf/session_analysis/
- **AND** JSON file name is session_<session_id>.json
- **AND** JSON content matches SessionExecution object

#### Scenario: Query executions for file
- **GIVEN** session_executions table with 5 sessions that modified api.py
- **AND** 3 sessions that did not modify api.py
- **WHEN** SessionExecutionStore.query_executions_for_file('api.py') is called
- **THEN** 5 SessionExecution objects are returned
- **AND** all returned sessions have api.py in files_modified

#### Scenario: Correlation analysis query
- **GIVEN** session_executions table with 100 compliant and 50 non-compliant sessions
- **WHEN** correlation query is run: `SELECT workflow_compliant, AVG(risk_score), AVG(user_engagement_rate) FROM session_executions GROUP BY workflow_compliant`
- **THEN** two rows are returned (compliant=1, compliant=0)
- **AND** compliant sessions show lower avg risk_score than non-compliant
- **AND** compliant sessions show lower avg user_engagement_rate (less user intervention needed)

#### Scenario: Prevent SQL injection in queries
- **GIVEN** a file_path containing SQL injection attempt: `api.py'; DROP TABLE session_executions; --`
- **WHEN** SessionExecutionStore.query_executions_for_file(malicious_path) is called
- **THEN** parameterized query is used
- **AND** no SQL injection occurs
- **AND** query returns empty list (no sessions with that exact file path)

---

### Requirement: Session Analysis Orchestration

The system SHALL orchestrate complete session analysis: parse → score → check workflow → store.

The system SHALL score all Edit/Write tool calls in a session.

The system SHALL calculate aggregate risk score from all diff scores.

The system SHALL determine outcome (task completed, corrections needed, rollback) from session data.

The system SHALL extract task description from user messages.

The system SHALL log progress (scoring N diffs, checking workflow, storing results).

The system SHALL handle sessions with no diffs (read-only sessions).

The system SHALL handle sessions with no workflow violations.

#### Scenario: Analyze complete session (end-to-end)
- **GIVEN** a session JSONL file with task "Add user authentication"
- **AND** session contains: Bash: aud blueprint, Read: auth.py, Edit: auth.py, Write: test_auth.py
- **WHEN** SessionAnalysis.analyze_session() is called
- **THEN** all diffs are scored
- **AND** workflow compliance is checked
- **AND** SessionExecution is stored to DB and JSON
- **AND** task_description is "Add user authentication"
- **AND** workflow_compliant is True

#### Scenario: Analyze session with high-risk diffs
- **GIVEN** a session with 3 diffs: 2 low-risk (0.1, 0.15) and 1 high-risk (0.9)
- **WHEN** SessionAnalysis.analyze_session() is called
- **THEN** aggregate risk_score is 0.38 (average of 3 scores)
- **AND** diffs_scored JSON contains all 3 diff scores

#### Scenario: Analyze read-only session (no diffs)
- **GIVEN** a session with only Read and Bash tool calls (no Edit/Write)
- **WHEN** SessionAnalysis.analyze_session() is called
- **THEN** analysis completes successfully
- **AND** risk_score is 0.0 (no diffs to score)
- **AND** diffs_scored is empty array

#### Scenario: Determine outcome (task completed)
- **GIVEN** a session ending with user message "Looks good, thanks!"
- **AND** no subsequent sessions modifying same files
- **WHEN** SessionAnalysis._determine_outcome() is called
- **THEN** task_completed is True
- **AND** corrections_needed is False
- **AND** rollback is False

#### Scenario: Determine outcome (corrections needed)
- **GIVEN** a session modifying auth.py
- **AND** next session starts with user message "The login isn't working, please fix"
- **WHEN** SessionAnalysis._determine_outcome() is called
- **THEN** task_completed is False
- **AND** corrections_needed is True

---

### Requirement: ML Feature Integration

The system SHALL extract Tier 5 features from session_executions table.

The system SHALL return 4 session behavior features: session_workflow_compliance, session_avg_risk_score, session_blind_edit_rate, session_correction_rate.

The system SHALL normalize all features to 0.0-1.0 range.

The system SHALL return zero features for files with no session data.

The system SHALL maintain 97-dimension feature matrix (consistent with/without Tier 5 data).

The system SHALL read features from session_executions table (not ephemeral calculation).

#### Scenario: Extract features for file with session data
- **GIVEN** session_executions table with 5 sessions that modified api.py
- **AND** sessions have avg compliance_score=0.8, avg risk_score=0.3, 2 corrections
- **WHEN** load_agent_behavior_features() is called with ['api.py']
- **THEN** features['api.py']['session_workflow_compliance'] is 0.8
- **AND** features['api.py']['session_avg_risk_score'] is 0.3
- **AND** features['api.py']['session_correction_rate'] is 0.4 (2/5)

#### Scenario: Extract features for file without session data
- **GIVEN** session_executions table with no sessions modifying new_file.py
- **WHEN** load_agent_behavior_features() is called with ['new_file.py']
- **THEN** features['new_file.py']['session_workflow_compliance'] is 0.0
- **AND** features['new_file.py']['session_avg_risk_score'] is 0.0
- **AND** features['new_file.py']['session_blind_edit_rate'] is 0.0
- **AND** features['new_file.py']['session_correction_rate'] is 0.0

#### Scenario: Feature dimension consistency
- **GIVEN** a project with no session data
- **WHEN** ML model trains on features
- **THEN** feature matrix has 97 dimensions (Tier 5 features are 0.0)
- **AND** when session data is added and model retrains
- **THEN** feature matrix still has 97 dimensions (Tier 5 features are non-zero)

#### Scenario: Feature normalization
- **GIVEN** session_executions with extreme values (risk_score=0.95, compliance_score=0.05)
- **WHEN** load_agent_behavior_features() is called
- **THEN** all returned features are in 0.0-1.0 range
- **AND** no features exceed 1.0 or go below 0.0
