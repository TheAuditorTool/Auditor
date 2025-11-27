# Design: Pipeline Reporting Refactor

**Created**: 2025-11-28
**Status**: PROPOSAL

---

## Context

The pipeline final status (`[CLEAN]`/`[CRITICAL]`/`[HIGH]`) is the primary output users see after running `aud full`. This status drives:
- Developer decisions on whether code is safe to deploy
- CI/CD pipeline gates (exit codes)
- ML training data via journal recording

**Current State**: The status reports `[CLEAN]` even when the database contains 226 critical + 4,177 high severity findings. This is because:
1. The aggregation code reads from JSON files (wrong architecture)
2. One JSON filename is wrong (`findings.json` doesn't exist, should be `patterns.json`)
3. Try/except blocks silently swallow all errors

**Constraint**: This is a security auditing tool. False negatives (reporting clean when vulnerabilities exist) are catastrophic.

---

## Goals / Non-Goals

### Goals
- Final status reflects actual findings from database (source of truth)
- ZERO FALLBACK - errors crash pipeline instead of hiding behind `[CLEAN]`
- Clear separation of security tools vs quality tools

### Non-Goals
- Changing JSON artifact generation (still written for human inspection)
- Modifying database writes (already correct)
- Changing return dict structure (consumers depend on it)

---

## Decisions

### Decision 1: Database-First Architecture

**What**: Query `findings_consolidated` table directly instead of reading JSON files.

**Why**:
- Database is populated by all analysis phases during pipeline execution
- JSON files are write-only artifacts for human inspection
- Database has all 5,208 security findings; JSON reading yielded 0

**Alternative Considered**: Fix the JSON filename (`findings.json` -> `patterns.json`)
- Rejected: Doesn't address architecture violation. JSON files are derived from database, so reading JSON instead of database is redundant and error-prone.

### Decision 2: Tool Categorization

**What**: Split tools into categories that determine final status behavior.

| Category | Tools | Affects Exit Code? |
|----------|-------|-------------------|
| SECURITY_TOOLS | patterns, taint, terraform, cdk | YES |
| QUALITY_TOOLS | ruff, eslint, mypy | NO |
| ANALYSIS_TOOLS | cfg-analysis, graph-analysis | NO |

**Why**:
- Security findings (vulnerabilities, misconfigurations) should block deployment
- Quality findings (lint warnings, type errors) are informational
- Mixing them inflates "critical" counts with non-security issues

**Implementation**: `SECURITY_TOOLS = frozenset({'patterns', 'taint', 'terraform', 'cdk'})`

**Alternative Considered**: Include all tools in security status
- Rejected: Would report 11,246 ruff warnings as "high severity security issues", causing alert fatigue

### Decision 3: ZERO FALLBACK Policy

**What**: No try/except blocks around database query. If query fails, pipeline crashes.

**Why**:
- Current try/except blocks hid the bug for unknown duration
- A security tool that silently fails is worse than one that crashes
- Crash exposes configuration/environment issues immediately

**Implementation**:
```python
# NO try/except - let it crash
conn = sqlite3.connect(str(db_path))
cursor.execute("SELECT severity, COUNT(*) FROM findings_consolidated ...")
```

**Alternative Considered**: Graceful degradation with warning
- Rejected: CLAUDE.md Section 4 explicitly bans this pattern. "NO FALLBACKS. NO EXCEPTIONS."

---

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Tool miscategorization hides real vulnerabilities | SECURITY_TOOLS is a constant at top of file, easy to audit and modify |
| Fresh project crashes (no .pf/repo_index.db) | Expected behavior - can't report findings without database |
| Breaking change to final status values | Return dict structure unchanged, only data source changes |

---

## Migration Plan

### Phase 1: Add New Code (Non-Breaking)
1. Add `SECURITY_TOOLS` constant near top of pipelines.py
2. Add `_get_findings_from_db()` helper function
3. Both additions are dead code until Phase 2

### Phase 2: Replace Old Code
1. Delete JSON reading code (lines 1588-1660)
2. Replace with single call to `_get_findings_from_db()`
3. Same variable names (`critical_findings`, etc.) so downstream code unchanged

### Rollback
```bash
git revert <commit>
```
Time to rollback: ~2 minutes

---

## Open Questions

1. **Resolved**: Should terraform/cdk tools be in SECURITY_TOOLS?
   - YES - Infrastructure misconfigurations are security vulnerabilities

2. **Resolved**: What about info severity?
   - Excluded from final status (only critical/high/medium/low affect display)
   - Still stored in database for detailed reports

---

## Schema Reference

### findings_consolidated table

The table has 35 columns (expanded during 2025-11 schema refactors). This fix only queries two columns:

| Column | Type | Used By This Fix |
|--------|------|------------------|
| `tool` | TEXT | YES - Filter by SECURITY_TOOLS |
| `severity` | TEXT | YES - Group and count |

**Query used by fix** (does not depend on other columns):
```sql
SELECT severity, COUNT(*)
FROM findings_consolidated
WHERE tool IN ('patterns', 'taint', 'terraform', 'cdk')
GROUP BY severity
```

---

## Code References

| File | Line | Purpose |
|------|------|---------|
| `theauditor/pipelines.py` | 245 | `run_full_pipeline()` function |
| `theauditor/pipelines.py` | 1588-1660 | JSON reading code (TO DELETE) |
| `theauditor/pipelines.py` | 1677-1692 | Return dict (PRESERVE structure) |
| `theauditor/commands/full.py` | 155-189 | Status display consumer |
| `theauditor/journal.py` | 439 | Journal recording consumer |
