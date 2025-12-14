# TheAuditor Session Analyzer

## Overview

A **Tier 5 (ML training) pipeline** that:
1. Parses Claude Code and Codex session logs (JSONL)
2. Analyzes AI agent behavior patterns
3. Detects anti-patterns and quality issues
4. Stores metrics for ML training

**Core Question**: "How efficiently did the AI work? Did it follow instructions?"

---

## Key Components

### 1. Session Parser (`parser.py`)
- Reads `.jsonl` session files
- Extracts: user messages, assistant messages, tool calls
- Creates `Session` dataclass with chronological turns
- Default locations: `~/.claude/projects/` or `~/.codex/sessions/`
- Custom path: Use `--session-dir` flag

### 2. Activity Classifier (`activity_metrics.py`)

**4 Activity Types:**

| Type | Definition | Tools |
|------|------------|-------|
| **PLANNING** | Discussion & design | Text >200 chars, no tools |
| **WORKING** | Code changes | Edit, Write, Bash, NotebookEdit |
| **RESEARCH** | Info gathering | Read, Grep, Glob, Task, WebFetch |
| **CONVERSATION** | Questions, clarifications | User messages, short responses |

**Metrics:**
- `work_to_talk_ratio`: Working tokens / (Planning + Conversation)
- `research_to_work_ratio`: Research tokens / Working tokens
- `tokens_per_edit`: Total tokens / (Edit + Write count)

### 3. Workflow Compliance Checker (`workflow_checker.py`)

**Checks:**
- `blueprint_first`: Run `aud blueprint` before modifications
- `query_before_edit`: Use `aud query` before editing
- `no_blind_reads`: Read files before editing them

**Output:**
```python
@dataclass
class WorkflowCompliance:
    compliant: bool
    score: float      # 0-1
    violations: list[str]
```

### 4. Diff Risk Scorer (`diff_scorer.py`)

**Risk Factors (0-1):**
- **Taint analysis (40%)**: SQL injection, command injection, eval()
- **Pattern detection (30%)**: Hardcoded credentials, TODO/FIXME
- **FCE completeness (20%)**: File completion estimate
- **RCA historical (10%)**: Prior failure rates

**Detects Blind Edits**: Edit without prior Read

---

## Finding Categories

| Finding | Severity | Meaning |
|---------|----------|---------|
| `blind_edit` | WARNING | Edit without Read |
| `duplicate_read` | INFO | File read >3 times |
| `missing_search` | INFO | Write without Grep/Glob |
| `comment_hallucination` | WARNING | AI references non-existent comments |
| `duplicate_implementation` | WARNING | Creates symbols already in DB |

---

## Activity Classification Logic

```
Turn Classification:
├─ User message? → CONVERSATION
├─ No tools?
│  └─ Text >200 chars? → PLANNING, else CONVERSATION
├─ Only META tools? (TodoWrite, AskUserQuestion)
│  └─ Text >200 chars? → PLANNING, else CONVERSATION
├─ Has WORKING tools? (Edit, Write, Bash)
│  └─ WORKING
└─ Has RESEARCH tools? (Read, Grep, Glob)
   └─ RESEARCH
```

---

## Storage Layer (`store.py`)

**Database**: `.pf/ml/session_history.db`

**Table**: `session_executions`
```sql
session_id TEXT,
workflow_compliant BOOL,
compliance_score FLOAT,
risk_score FLOAT,
task_completed BOOL,
corrections_needed BOOL,
user_engagement_rate FLOAT,
diffs_scored JSON
```

---

## ML Integration

**Tier 5 Features** (from `features.py`):
```python
load_session_execution_features(db_path, file_paths) → {
    "session_workflow_compliance": 0.85,
    "session_avg_risk_score": 0.32,
    "session_blind_edit_rate": 0.0,
    "session_user_engagement": 1.5
}
```

**Correlation Statistics:**
```
Compliant sessions:
  - Avg risk score: 0.28
  - Correction rate: 12%

Non-compliant sessions:
  - Avg risk score: 0.42 (50% higher)
  - Correction rate: 34% (3x higher)
```

---

## CLI Commands

```bash
aud session analyze    # Parse and store to DB
aud session report     # Aggregate findings
aud session inspect    # Deep-dive single session
aud session activity   # Work/talk/planning ratios
aud session list       # List available sessions
```

---

## Sample Output

```json
{
  "session_count": 47,
  "token_distribution": {
    "planning": 450000,
    "working": 1200000,    // 60% = highly productive
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

## Why This Matters

1. **Quality Feedback Loop**: Detect when AI doesn't follow instructions
2. **Productivity Metrics**: Quantify work vs overhead
3. **Risk Prediction**: Learn which patterns correlate with failures
4. **Behavioral Learning**: Train models on successful execution patterns
5. **Compliance Verification**: Ensure workflows are followed
