# TheAuditor Session Analyzer

## Overview

The **SESSION Analyzer** analyzes AI agent (Claude Code, Codex) session interactions to extract quality insights and enable ML training.

**Core Question**: "How much do we talk to the AI vs how much does it work vs plan?"

**Input**: Session JSONL files from `~/.claude/projects/` or `~/.codex/sessions/` (default locations, use `--session-dir` for custom paths)
**Output**: `.pf/ml/session_history.db`, activity metrics, findings, ML training data

---

## Activity Classification

### 4 Activity Types

| Type | Definition | Tools |
|------|------------|-------|
| **PLANNING** | Discussion & design | Text >200 chars, no tools |
| **WORKING** | Code changes | Edit, Write, Bash, NotebookEdit |
| **RESEARCH** | Info gathering | Read, Grep, Glob, Task, WebFetch |
| **CONVERSATION** | Questions, clarifications | User messages, short responses |

### Key Metrics

```python
work_to_talk_ratio      # Working tokens / (Planning + Conversation)
research_to_work_ratio  # Research tokens / Working tokens
tokens_per_edit         # Total tokens / (Edit + Write count)
```

### Efficiency Interpretation

| Metric | Good | Poor |
|--------|------|------|
| work_to_talk_ratio | > 1.5 (productive) | < 0.5 (overhead-heavy) |
| research_to_work_ratio | < 1.0 (efficient) | > 1.0 (research-heavy) |
| tokens_per_edit | < 500 (efficient) | > 2000 (verbose) |

---

## Workflow Compliance Checking

### Default Checks

```python
"blueprint_first"     # Run aud blueprint before modifications
"query_before_edit"   # Use aud query before editing
"no_blind_reads"      # Read files before editing
```

### Compliance Score
```
score = passed_checks / total_checks
compliant = all(checks.values())
```

---

## Diff Risk Scoring

4-dimension risk assessment:

| Factor | Weight | Detects |
|--------|--------|---------|
| Taint Analysis | 40% | SQL injection, command injection, eval() |
| Pattern Detection | 30% | Hardcoded secrets, TODOs |
| FCE Completeness | 20% | File completion estimate |
| RCA Historical | 10% | Prior failure rates |

### Blind Edit Detection
A "blind edit" = Edit/Write without prior Read on that file.

---

## Pattern Detection (Anti-Patterns)

| Pattern | Severity | Detection |
|---------|----------|-----------|
| `blind_edit` | WARNING | Edit without prior Read |
| `duplicate_read` | INFO | File read >3 times |
| `missing_search` | INFO | Write without Grep/Glob |
| `comment_hallucination` | WARNING | References non-existent comments |
| `duplicate_implementation` | WARNING | Creates existing symbols |

---

## CLI Commands

```bash
# List available sessions
aud session list

# Parse and store to DB
aud session analyze

# Single session deep-dive
aud session inspect path/to/session.jsonl

# Work/talk/planning ratios
aud session activity

# Aggregate findings report
aud session report
```

---

## Session Activity Output

```json
{
  "session_count": 47,
  "token_distribution": {
    "planning": 450000,
    "working": 1200000,     // 60% = highly productive
    "research": 600000,
    "conversation": 200000
  },
  "ratios": {
    "work_to_talk_ratio": 2.1,     // Higher is better
    "tokens_per_edit": 3500        // Lower is better
  }
}
```

---

## ML Integration

### Tier 5 Features (Agent Behavior)

```python
"workflow_compliance"       # 3-layer scoring
"avg_risk_score"            # Diff risk average
"blind_edit_rate"           # Fraction of blind edits
"user_engagement_rate"      # Higher = more corrections needed
"duplicate_impl_rate"       # Duplicate implementation frequency
```

### Correlation Statistics

```
Compliant sessions:
  - Avg risk score: 0.28
  - Correction rate: 12%

Non-compliant sessions:
  - Avg risk score: 0.42 (50% higher)
  - Correction rate: 34% (3x higher)
```

---

## Extensibility (features.py)

The system is designed for extension via `features.py`:

1. **Add New Entry Type**: Handle new agent formats
2. **Add New Tool Types**: Dynamic tool name handling
3. **Add New Metrics**: Extend dataclasses with new fields
4. **Add New Checks**: Register in workflow compliance

---

## Storage Layer

**Database**: `.pf/ml/session_history.db`

```sql
CREATE TABLE session_executions (
    session_id TEXT,
    workflow_compliant BOOL,
    compliance_score FLOAT,
    risk_score FLOAT,
    task_completed BOOL,
    corrections_needed BOOL,
    user_engagement_rate FLOAT,
    diffs_scored JSON
);
```
