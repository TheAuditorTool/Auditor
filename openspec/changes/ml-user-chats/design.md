# Design Document: ml-user-chats

## Context

TheAuditor's ML Intelligence System currently has 4 tiers of data sources providing comprehensive code-centric analysis. However, it lacks **process quality signals** - data about how code changes were made and whether the development workflow followed best practices.

AI coding assistants (Claude Code, GitHub Copilot) generate detailed session logs containing complete execution traces. This data is currently unused but contains deterministic evidence of development process quality.

## Core Principle: Deterministic Feedback Loop

**NOT analyzing user intent** (user messages are vague, contradictory, useless).
**YES analyzing agent execution** (tool calls, diffs, outcomes are deterministic and measurable).

This is not "vibe coding" - it's creating labeled training data through deterministic correlation of:
1. What agent DID (execution trace)
2. How risky it WAS (SAST scoring)
3. Whether workflow COMPLIED (planning.md validation)
4. What OUTCOME resulted (completed, correction, rollback)

## Architecture Decisions

### Decision 1: Three-Layer Stack (Not Simple ML Features)

**Options Considered**:
1. Simple ML features (count blind edits, duplicates) - REJECTED
2. User intent analysis (parse user messages) - REJECTED
3. Three-layer stack (execution + scoring + correlation) - SELECTED

**Rationale**:
Initial "vibe coding" implementation created 4 simple agent behavior features:
- agent_blind_edit_count
- agent_duplicate_impl_rate
- agent_missed_search_count
- agent_read_efficiency

**Problem**: These features were zero for most files (no correlation with actual code quality).

**Solution**: Three-layer stack connects execution patterns to code quality:
- **Layer 1** (Execution): Extract what agent did
- **Layer 2** (Scoring): Run diffs through SAST pipeline to measure code quality
- **Layer 3** (Correlation): Link execution patterns to outcomes

This creates **labeled training data** showing which execution patterns lead to high-risk code and task failures.

**Trade-offs**:
- ✅ Pros: Deterministic, correlates process with quality, generates high-quality labeled data
- ❌ Cons: More complex than simple features, requires SAST pipeline integration
- **Verdict**: Complexity justified by value - simple features provided zero signal

### Decision 2: Reuse Existing SAST Pipeline (Not New Analysis)

**Options Considered**:
1. Create new lightweight diff analyzer - REJECTED
2. Reuse existing SAST pipeline (taint, patterns, FCE, RCA) - SELECTED

**Rationale**:
TheAuditor already has comprehensive SAST pipeline:
- Taint analysis (SQL injection, XSS, command injection)
- Pattern detection (f-strings in SQL, hardcoded secrets)
- FCE correlation (incomplete refactors, architectural hotspots)
- RCA historical risk (file's failure rate from git history)

**Reusing this pipeline**:
- Maintains consistency (same scoring for real-time and historical analysis)
- Leverages battle-tested analysis (no new bugs)
- Enables comparison (session diffs vs full codebase)

**Implementation**:
```python
def score_diff(session, tool_call, db_path):
    """Score a diff using existing SAST pipeline."""

    # Extract diff from tool call
    file_path = tool_call.input_params['file_path']
    old_code = tool_call.input_params.get('old_string', '')
    new_code = tool_call.input_params['new_string']

    # Write diff to temp file
    temp_file = write_temp_diff(file_path, old_code, new_code)

    # Run existing SAST pipeline
    scores = {
        'taint': run_taint_on_diff(temp_file, db_path),
        'patterns': run_patterns_on_diff(temp_file, db_path),
        'fce': check_completeness(file_path, db_path),
        'rca': get_file_risk_history(file_path, db_path),
    }

    # Aggregate risk score
    risk_score = calculate_aggregate_risk(scores)

    return risk_score  # 0.0-1.0
```

**Trade-offs**:
- ✅ Pros: Reuses existing code, consistent scoring, comprehensive analysis
- ❌ Cons: Requires temp file handling, slower than simple heuristics
- **Verdict**: Consistency and comprehensiveness outweigh performance cost

### Decision 3: Workflow Compliance from planning.md (Not Hardcoded Rules)

**Options Considered**:
1. Hardcode workflow rules in Python - REJECTED
2. Read workflow definitions from planning.md - SELECTED

**Rationale**:
`planning.md` already defines mandatory workflows (lines 1217-1241):
- Phase 2 Step 1: Foundation - Run `aud blueprint` FIRST (MANDATORY)
- Phase 2 Step 2: Query patterns from blueprint output
- Phase 2 Step 3: Synthesis anchored in query results
- FORBIDDEN: File reading without blueprint, guessing relationships

Hardcoding these rules would:
- Duplicate source of truth (planning.md and Python code)
- Create maintenance burden (update both places)
- Prevent users from customizing workflows

**Implementation**:
```python
def check_workflow_compliance(session, workflow_def):
    """Check if agent followed defined workflow."""

    # Extract actual tool call sequence
    actual_steps = extract_tool_sequence(session)

    # Check mandatory steps from workflow_def
    compliance = {
        'blueprint_first': actual_steps[0].contains('aud blueprint'),
        'query_before_edit': has_query_before_edits(actual_steps),
        'no_blind_reads': all_edits_have_prior_reads(actual_steps),
    }

    return {
        'compliant': all(compliance.values()),
        'score': sum(compliance.values()) / len(compliance),
        'violations': [k for k, v in compliance.items() if not v]
    }
```

**Trade-offs**:
- ✅ Pros: Single source of truth, user-customizable, explicit workflow definitions
- ❌ Cons: Requires parsing planning.md, workflows must be structured
- **Verdict**: Single source of truth principle outweighs parsing complexity

### Decision 4: session_executions Table (Not Ephemeral Features)

**Options Considered**:
1. Extract features on-demand during ML training - REJECTED
2. Persist session data in session_executions table - SELECTED

**Rationale**:
Initial implementation violated **dual-write principle** - ML features were extracted from session logs but not persisted to database or JSON. This made them:
- Ephemeral (lost after training)
- Unreproducible (different results on re-run)
- Unqueryable (can't analyze correlations directly)

**Solution**: Create `session_executions` table mirroring other analysis tables:
```sql
CREATE TABLE session_executions (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    task_description TEXT,
    workflow_compliant INTEGER,  -- 0/1
    compliance_score REAL,       -- 0.0-1.0
    risk_score REAL,             -- 0.0-1.0 from SAST scoring
    task_completed INTEGER,      -- 0/1 from task state
    corrections_needed INTEGER,  -- 0/1 from next session
    rollback INTEGER,            -- 0/1 from git history
    timestamp TEXT,
    tool_call_count INTEGER,
    files_modified INTEGER,
    diffs_scored TEXT            -- JSON array of diff scores
);
```

This enables:
- Correlation queries: `SELECT AVG(risk_score) WHERE workflow_compliant = 1 vs 0`
- Historical analysis: Track workflow compliance over time
- Reproducibility: Same session always produces same scores
- Integration: ML features read from database (like all other tiers)

**Trade-offs**:
- ✅ Pros: Persistent, queryable, reproducible, follows dual-write principle
- ❌ Cons: Storage overhead (~1KB per session), requires database migration
- **Verdict**: Storage overhead negligible compared to value

### Decision 5: Integrate with Existing ML System (Not Standalone Tool)

**Options Considered**:
1. Create standalone `aud session` command for users - REJECTED
2. Integrate as Tier 5 of ML system - SELECTED

**Rationale**:
Session analysis provides most value when integrated with ML system:
- Tier 5 features join 50+ existing features (pipeline, journal, artifacts, git)
- ML models learn **combined patterns**: "Complex code + workflow violations + blind edits = 95% failure"
- Enables cross-tier correlation: "Files with high cyclomatic complexity edited without blueprint → highest risk"

Standalone tool would:
- Provide less actionable insights (just session stats, no code quality correlation)
- Duplicate functionality (separate CLI, separate analysis logic)
- Reduce adoption (users would need to learn new command)

**Implementation**:
- Session parsing is library-only (not exposed in main CLI)
- ML `learn` command accepts `--session-dir` flag
- Features integrate into existing 97-dimension feature matrix
- Models trained on combined data (all 5 tiers)

**Trade-offs**:
- ✅ Pros: Seamless integration, cross-tier correlation, single workflow
- ❌ Cons: Session analysis not useful without ML system
- **Verdict**: Integration maximizes value

## Data Flow Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ LAYER 1: EXECUTION CAPTURE                                     │
├────────────────────────────────────────────────────────────────┤
│ Input: Claude Code session logs (*.jsonl)                      │
│ Process:                                                        │
│   - Parse JSONL with SessionParser                             │
│   - Extract tool calls (Read, Edit, Write, Bash)               │
│   - Extract diffs (old_string → new_string)                    │
│   - Build execution timeline                                   │
│ Output: Session object with structured data                    │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ LAYER 2: DETERMINISTIC SCORING                                 │
├────────────────────────────────────────────────────────────────┤
│ Input: Diffs from Layer 1                                      │
│ Process:                                                        │
│   For each diff:                                               │
│     - Write to temp file                                       │
│     - Run aud taint-analyze --diff                             │
│     - Run aud detect-patterns --diff                           │
│     - Run aud fce --check-completeness                         │
│     - Query RCA stats from repo_index.db                       │
│     - Aggregate scores → risk_score (0.0-1.0)                  │
│ Output: Scored diffs with risk metrics                         │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ LAYER 3: WORKFLOW CORRELATION                                  │
├────────────────────────────────────────────────────────────────┤
│ Input: Session execution + planning.md workflows               │
│ Process:                                                        │
│   - Extract actual tool sequence                               │
│   - Check: blueprint first? query before edit? blind reads?    │
│   - Calculate compliance_score (0.0-1.0)                       │
│   - Determine outcome (completed, correction, rollback)        │
│ Output: Workflow compliance + outcome labels                   │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ DATABASE PERSISTENCE                                           │
├────────────────────────────────────────────────────────────────┤
│ Write to session_executions table:                             │
│   - session_id, task_description                               │
│   - workflow_compliant, compliance_score                       │
│   - risk_score, diffs_scored                                   │
│   - task_completed, corrections_needed, rollback               │
│ Also write JSON to .pf/session_analysis/:                      │
│   - session_<id>.json with complete analysis                   │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ ML FEATURE EXTRACTION                                          │
├────────────────────────────────────────────────────────────────┤
│ theauditor/insights/ml/features.py:                            │
│   load_agent_behavior_features():                              │
│     - Query session_executions for file                        │
│     - Extract features for ML training:                        │
│         * session_workflow_compliance (0.0-1.0)                │
│         * session_avg_risk_score (0.0-1.0)                     │
│         * session_blind_edit_rate (0.0-1.0)                    │
│         * session_correction_rate (0.0-1.0)                    │
│     - Add to 97-dimension feature matrix (Tier 5)              │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ ML MODEL TRAINING                                              │
├────────────────────────────────────────────────────────────────┤
│ theauditor/insights/ml/models.py:                              │
│   train_risk_scorer():                                         │
│     - Combine all 5 tiers (97 features)                        │
│     - Learn: workflow violations + blind edits → high risk     │
│     - Model outputs: risk score (0.0-1.0)                      │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ CORRELATION ANALYSIS                                           │
├────────────────────────────────────────────────────────────────┤
│ Statistical queries on session_executions:                     │
│                                                                 │
│ SELECT workflow_compliant,                                     │
│        AVG(risk_score) as avg_risk,                            │
│        SUM(corrections_needed)/COUNT(*) as correction_rate     │
│ FROM session_executions                                        │
│ GROUP BY workflow_compliant;                                   │
│                                                                 │
│ Result:                                                         │
│   compliant=1: avg_risk=0.15, correction_rate=0.11            │
│   compliant=0: avg_risk=0.67, correction_rate=0.73            │
│                                                                 │
│ Insight: Workflow compliance reduces risk by 78%!              │
└────────────────────────────────────────────────────────────────┘
```

## Component Design

### SessionParser (Existing - theauditor/session/parser.py)
**Status**: Already implemented (229 lines)

**Responsibilities**:
- Parse JSONL session logs
- Extract user messages, assistant messages, tool calls
- Handle timezone-aware timestamps
- Build structured Session objects

**Design Patterns**:
- Dataclass-based model (Session, ToolCall, Message)
- Generator pattern for memory efficiency
- Defensive parsing (skip malformed entries)

### DiffScorer (New - theauditor/session/diff_scorer.py)
**Status**: To be implemented

**Responsibilities**:
- Extract diffs from Edit/Write tool calls
- Run diffs through SAST pipeline
- Aggregate scores into risk metric
- Handle temp file cleanup

**Interface**:
```python
class DiffScorer:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def score_diff(self, tool_call: ToolCall) -> DiffScore:
        """Score a single diff."""
        # Extract diff
        file_path = tool_call.input_params['file_path']
        old_code = tool_call.input_params.get('old_string', '')
        new_code = tool_call.input_params['new_string']

        # Run SAST scoring
        taint_score = self._run_taint(file_path, new_code)
        pattern_score = self._run_patterns(file_path, new_code)
        fce_score = self._check_completeness(file_path)
        rca_score = self._get_historical_risk(file_path)

        # Aggregate
        risk_score = self._aggregate_scores(
            taint_score, pattern_score, fce_score, rca_score
        )

        return DiffScore(
            file=file_path,
            risk_score=risk_score,
            findings={'taint': taint_score, 'patterns': pattern_score}
        )
```

### WorkflowChecker (New - theauditor/session/workflow_checker.py)
**Status**: To be implemented

**Responsibilities**:
- Parse planning.md workflow definitions
- Extract tool call sequence from session
- Validate sequence against workflow
- Return compliance score and violations

**Interface**:
```python
class WorkflowChecker:
    def __init__(self, workflow_path: Path):
        self.workflows = self._parse_workflows(workflow_path)

    def check_compliance(self, session: Session) -> WorkflowCompliance:
        """Check if session followed workflow."""
        tool_sequence = self._extract_sequence(session)

        checks = {
            'blueprint_first': self._check_blueprint_first(tool_sequence),
            'query_before_edit': self._check_query_usage(tool_sequence),
            'no_blind_reads': self._check_blind_edits(tool_sequence),
        }

        return WorkflowCompliance(
            compliant=all(checks.values()),
            score=sum(checks.values()) / len(checks),
            violations=[k for k, v in checks.items() if not v]
        )
```

### SessionExecutionStore (New - theauditor/session/store.py)
**Status**: To be implemented

**Responsibilities**:
- Write session data to session_executions table
- Write JSON files to .pf/session_analysis/
- Query session data for ML features
- Implement dual-write principle

**Interface**:
```python
class SessionExecutionStore:
    def __init__(self, db_path: Path, json_dir: Path):
        self.db_path = db_path
        self.json_dir = json_dir

    def store_execution(self, session: Session, scores: List[DiffScore],
                       compliance: WorkflowCompliance, outcome: Outcome):
        """Store session execution data."""
        # Write to database
        self._write_to_db(session, scores, compliance, outcome)

        # Write to JSON (dual-write principle)
        self._write_to_json(session, scores, compliance, outcome)
```

## Testing Strategy

### Unit Tests
- **SessionParser**: Parse malformed JSONL, handle timezones, skip invalid entries
- **DiffScorer**: Score simple diffs, handle missing SAST tools, aggregate scores
- **WorkflowChecker**: Parse workflows, validate sequences, compute compliance
- **SessionExecutionStore**: Write to DB and JSON, query for features

### Integration Tests
- **End-to-end flow**: Parse session → score diffs → check workflow → store → extract features
- **SAST pipeline integration**: Run real taint/pattern analysis on diffs
- **ML training**: Train models with Tier 5 features, verify accuracy improvement

### Fixtures
- `tests/fixtures/sessions/sample_session.jsonl` - Example session log
- `tests/fixtures/sessions/compliant_session.jsonl` - Follows workflow
- `tests/fixtures/sessions/non_compliant_session.jsonl` - Violates workflow

## Migration Strategy

### Backward Compatibility
- Existing ML features continue to work without session data
- Session analysis is opt-in via `--session-dir` flag
- No breaking changes to existing commands

### Database Migration
```sql
-- Add session_executions table to repo_index.db
CREATE TABLE IF NOT EXISTS session_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    task_description TEXT,
    workflow_compliant INTEGER DEFAULT 0,
    compliance_score REAL DEFAULT 0.0,
    risk_score REAL DEFAULT 0.0,
    task_completed INTEGER DEFAULT 0,
    corrections_needed INTEGER DEFAULT 0,
    rollback INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL,
    tool_call_count INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0,
    diffs_scored TEXT  -- JSON array
);

CREATE INDEX idx_session_executions_session_id ON session_executions(session_id);
CREATE INDEX idx_session_executions_timestamp ON session_executions(timestamp);
CREATE INDEX idx_session_executions_compliant ON session_executions(workflow_compliant);
```

### Feature Flag
```python
# theauditor/config.py
ENABLE_SESSION_ANALYSIS = os.getenv('THEAUDITOR_ENABLE_SESSIONS', 'true').lower() == 'true'
```

## Performance Considerations

### Session Parsing
- **Current**: 194 sessions (~44,000 lines) parsed in ~5 seconds
- **Bottleneck**: JSON parsing (unavoidable)
- **Optimization**: Use generator pattern to avoid loading all sessions in memory

### Diff Scoring
- **Cost**: Run SAST pipeline on each diff (N diffs × 4 tools × ~1 second)
- **Bottleneck**: SAST pipeline (reusing existing code, can't optimize further)
- **Optimization**: Batch scoring (parallel processing), cache results

### Database Queries
- **Cost**: ~2-3 seconds for duplicate detection across 20 sessions
- **Bottleneck**: SQLite full-table scans
- **Optimization**: Add indexes on session_id, timestamp, workflow_compliant

### Storage Overhead
- **Session logs**: ~2-5MB per day (unavoidable - stored by Claude Code)
- **session_executions table**: ~1KB per session (~100KB per month)
- **JSON files**: ~2-3KB per session (~200KB per month)
- **Total**: Negligible compared to repo_index.db (91MB)

## Security Considerations

### Data Privacy
- Session logs contain user code and prompts
- All analysis is local-only (no external API calls)
- Users should add `.claude/` to `.gitignore`
- Documentation must warn about code in session logs

### SQL Injection
- Use parameterized queries for all database writes
- Never concatenate user input into SQL

### File System Access
- Session logs read from user-specified directory (validate path)
- Temp files created with secure permissions (0600)
- Clean up temp files after scoring

## Monitoring and Observability

### Logging
```python
logger.info(f"[SESSION] Parsed {len(sessions)} sessions in {elapsed:.2f}s")
logger.info(f"[DIFF_SCORER] Scored {len(diffs)} diffs, avg risk: {avg_risk:.2f}")
logger.info(f"[WORKFLOW] Compliance: {compliance_rate:.1%} ({compliant}/{total})")
logger.warning(f"[SESSION] Skipped malformed session: {session_id}")
```

### Metrics
- Session parse success rate
- Diff scoring success rate
- Workflow compliance rate (over time)
- ML accuracy improvement with Tier 5

## Open Technical Questions

1. **Temp file handling**: Create one temp dir per session or per diff? (Performance vs cleanup complexity)
2. **Scoring parallelization**: Use multiprocessing for diff scoring? (Speedup vs complexity)
3. **Database choice**: session_executions in repo_index.db or separate session_analysis.db? (Single source vs separation of concerns)
4. **Outcome detection**: How to detect corrections/rollbacks? (Parse next session vs git history)
5. **Workflow customization**: Allow users to define custom workflows or only support planning.md? (Flexibility vs complexity)

## Success Metrics

- Parse 1000+ sessions without errors (robustness)
- Score diffs in <2 seconds each (performance)
- Achieve 5-10% ML accuracy improvement (value)
- Show statistical significance: compliant vs non-compliant (correlation)
- Zero false positives in workflow violation detection (precision)
