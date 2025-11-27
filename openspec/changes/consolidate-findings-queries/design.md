# Design: Consolidate Findings Queries

**Created**: 2025-11-28
**Status**: PROPOSAL
**Author**: Opus (AI Lead Coder)

---

## Context

TheAuditor is a polyglot security auditing tool that:
1. Indexes codebases (Python, Node, Rust extractors)
2. Runs analysis rules (patterns, taint, linters, etc.)
3. Reports findings to users and AI consumers

**The Problem**: Findings are stored in TWO places:
- `findings_consolidated` table in repo_index.db (source of truth)
- `.pf/raw/*.json` files (human-readable artifacts)

Consumers (final status, summary, ML) read from JSON instead of DB, causing:
- False `[CLEAN]` status when DB has 6,758 findings
- Data inconsistency between what's stored vs what's reported
- AI can't read 1-3MB JSON files

**Constraint**: This is a security tool. False negatives are catastrophic.

---

## Goals / Non-Goals

### Goals
- All findings consumers query `findings_consolidated` table directly
- GitHub workflow findings inserted into `findings_consolidated`
- CVE/vulnerability findings inserted into `findings_consolidated`
- ZERO FALLBACK compliance (no try/except around queries)

### Non-Goals
- Removing JSON file generation (keep for human inspection)
- Changing findings_consolidated schema (use existing columns)
- Adding taint to findings_consolidated (user handling separately)
- Removing tool-specific columns (cfg_*, graph_*, etc.) - future work

---

## Decisions

### Decision 1: Query findings_consolidated Directly

**What**: All findings consumers query the database table instead of reading JSON files.

**Why**:
- Database is populated during analysis phases
- JSON files are derived artifacts, not source of truth
- Database has 6,758 findings; JSON reading yields ~0 (wrong filenames, empty files)
- Single source of truth = no data inconsistency

**Implementation Pattern**:
```python
import sqlite3
from pathlib import Path

def get_findings_by_tool(db_path: Path, tools: tuple[str, ...]) -> dict[str, dict[str, int]]:
    """Query findings_consolidated for counts by tool and severity.

    ZERO FALLBACK: No try/except. If query fails, crash is correct.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tool, severity, COUNT(*)
        FROM findings_consolidated
        WHERE tool IN ({})
        GROUP BY tool, severity
    """.format(','.join('?' * len(tools))), tools)

    results = {}
    for tool, severity, count in cursor.fetchall():
        if tool not in results:
            results[tool] = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        results[tool][severity] = count

    conn.close()
    return results
```

**Alternative Considered**: Fix JSON filenames and keep reading JSON
- **Rejected**: Doesn't address architecture violation. Database is populated correctly; reading JSON is redundant and error-prone.

### Decision 2: Security vs Quality Tool Separation

**What**: Only security tools affect final status exit code.

| Category | Tools | Affects Exit Code |
|----------|-------|-------------------|
| Security | patterns, terraform, github-workflows, vulnerabilities | YES |
| Quality | ruff, mypy, eslint | NO |
| Analysis | cfg-analysis, graph-analysis, churn-analysis | NO |

**Why**:
- Security findings (vulnerabilities, misconfigs) should block deployment
- Quality findings (lint warnings, type errors) are informational
- Mixing them would report 2,851 mypy errors as "security issues"

**Implementation**:
```python
SECURITY_TOOLS = frozenset({
    'patterns',
    'terraform',
    'github-workflows',
    'vulnerabilities',
})
```

**Alternative Considered**: All tools affect exit code
- **Rejected**: Alert fatigue. 5,000+ lint findings drowning out 855 security findings.

### Decision 3: ZERO FALLBACK for All Queries

**What**: No try/except blocks around database queries. If query fails, crash.

**Why**:
- Current try/except blocks hid the `[CLEAN]` bug for unknown duration
- A security tool that silently fails is worse than one that crashes
- Crash exposes configuration/environment issues immediately
- CLAUDE.md Section 4 mandates this pattern

**Implementation**:
```python
# CORRECT - No try/except
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("SELECT ...")  # Crashes if DB missing - CORRECT

# FORBIDDEN - Silent failure
try:
    cursor.execute("SELECT ...")
except Exception:
    return {}  # ZERO FALLBACK VIOLATION
```

### Decision 4: GitHub Workflows → findings_consolidated

**What**: `aud workflows analyze` inserts findings into findings_consolidated after generating them.

**Current Flow**:
```
workflows.py:analyze() → github_workflows.json → END
```

**New Flow**:
```
workflows.py:analyze() → github_workflows.json (keep)
                       → INSERT findings_consolidated (add)
```

**Mapping**:
```python
# commands/workflows.py - after line ~200 where findings are generated
def insert_workflow_findings(findings: list[dict], db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    for f in findings:
        cursor.execute("""
            INSERT INTO findings_consolidated
            (file, line, column, rule, tool, message, severity, category, confidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f['file'],
            f.get('line', 0),
            0,  # column
            f['rule'],
            'github-workflows',
            f['message'],
            f['severity'],
            'security',
            f.get('confidence', 0.8),
            datetime.now().isoformat(),
        ))

    conn.commit()
    conn.close()
```

### Decision 5: Vulnerabilities → findings_consolidated

**What**: `vulnerability_scanner.py` inserts CVEs into findings_consolidated.

**Current Flow**:
```
vulnerability_scanner.py:scan() → vulnerabilities.json → END
```

**New Flow**:
```
vulnerability_scanner.py:scan() → vulnerabilities.json (keep)
                                → INSERT findings_consolidated (add)
```

**CVSS to Severity Mapping**:
```python
def cvss_to_severity(cvss_score: float) -> str:
    """Map CVSS score to standard severity.

    Based on CVSS v3.0 qualitative severity rating scale.
    """
    if cvss_score >= 9.0:
        return 'critical'
    elif cvss_score >= 7.0:
        return 'high'
    elif cvss_score >= 4.0:
        return 'medium'
    else:
        return 'low'
```

### Decision 6: Keep JSON Generation

**What**: Continue writing JSON files to `.pf/raw/` for human inspection.

**Why**:
- Humans may want to inspect raw output
- Debugging tool behavior
- Historical artifacts for comparison
- Low cost to maintain (write-only)

**What Changes**: JSON files become truly write-only. No code reads them for aggregation.

---

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| DB query performance | findings_consolidated has indexes; queries are simple GROUP BY |
| ML training data format change | Same data, different source; test before deploying |
| Missing tool from SECURITY_TOOLS | Constant at top of file, easy to audit and modify |
| Fresh project with no .pf/ | Let it crash - can't report findings without database |

---

## Migration Plan

### Phase 1: Add Missing Tool Inserts (Non-Breaking)

1. Add INSERT to `commands/workflows.py` after JSON write
2. Add INSERT to `vulnerability_scanner.py` after JSON write
3. Re-run `aud full` to populate findings_consolidated
4. Verify new tools appear in DB

### Phase 2: Replace JSON Readers

1. Update `pipelines.py:1594-1660` - query DB instead of JSON
2. Update `commands/summary.py` - query DB
3. Update `insights/ml/intelligence.py` - query DB
4. Update `commands/insights.py` - query DB
5. Update `commands/report.py` - query DB

### Phase 3: Verification

1. Run `aud full --offline`
2. Verify final status shows actual counts
3. Verify summary shows same counts as DB
4. Verify ML training works with new data source

### Rollback

```bash
git revert <commit>
```
Time to rollback: ~2 minutes

---

## Schema Reference

### findings_consolidated (existing, no changes)

```sql
-- Core columns used by this fix
CREATE TABLE findings_consolidated (
    id INTEGER PRIMARY KEY,
    file TEXT,               -- Source file path
    line INTEGER,            -- Line number (0 if N/A)
    column INTEGER,          -- Column number (0 if N/A)
    rule TEXT,               -- Rule ID (e.g., 'sql-injection', 'CVE-2023-1234')
    tool TEXT,               -- Tool name (e.g., 'patterns', 'github-workflows')
    message TEXT,            -- Human-readable description
    severity TEXT,           -- 'critical', 'high', 'medium', 'low', 'info'
    category TEXT,           -- 'security', 'quality', etc.
    confidence REAL,         -- 0.0 to 1.0
    code_snippet TEXT,       -- Relevant code (optional)
    cwe TEXT,                -- CWE ID (optional)
    timestamp TEXT,          -- ISO timestamp
    -- ... additional tool-specific columns (not used by this fix)
);
```

### Tool Values After This Change

| tool | Source | Finding Type |
|------|--------|--------------|
| `patterns` | universal_detector.py | Security patterns (SQLi, XSS, etc.) |
| `terraform` | commands/terraform.py | IaC misconfigurations |
| `github-workflows` | commands/workflows.py | CI/CD security issues |
| `vulnerabilities` | vulnerability_scanner.py | CVEs in dependencies |
| `ruff` | linters/linters.py | Python lint (quality) |
| `mypy` | linters/linters.py | Type errors (quality) |
| `eslint` | linters/linters.py | JS lint (quality) |
| `cfg-analysis` | commands/cfg.py | Complexity metrics |
| `graph-analysis` | commands/graph.py | Coupling metrics |
| `churn-analysis` | commands/metadata.py | Change frequency |

---

## Code References

| File | Line | Purpose |
|------|------|---------|
| `theauditor/pipelines.py` | 1594-1660 | JSON reading (DELETE) |
| `theauditor/pipelines.py` | 1677-1692 | Return dict (PRESERVE) |
| `theauditor/commands/summary.py` | 167-266 | JSON loads (REPLACE) |
| `theauditor/commands/workflows.py` | 76-200 | JSON output (ADD INSERT) |
| `theauditor/vulnerability_scanner.py` | 630-709 | JSON output (ADD INSERT) |
| `theauditor/insights/ml/intelligence.py` | 240-430 | JSON loads (REPLACE) |
| `theauditor/commands/insights.py` | 276, 333 | JSON loads (REPLACE) |
| `theauditor/commands/report.py` | 61-65 | JSON docs (UPDATE) |

---

## Open Questions

1. **Resolved**: Should taint be included?
   - NO - User handling separately, building enhanced taint beyond SAST

2. **Resolved**: Should FCE correlation data go in findings_consolidated?
   - NO - FCE is correlation/analysis results, not findings

3. **Pending Architect**: CVSS severity mapping thresholds correct?
   - Proposed: critical >= 9.0, high >= 7.0, medium >= 4.0, low < 4.0
