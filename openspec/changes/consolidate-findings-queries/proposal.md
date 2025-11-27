# Consolidate All Findings to Database Queries

**Status**: PROPOSAL - Awaiting Architect Approval
**Change ID**: `consolidate-findings-queries`
**Complexity**: HIGH (~15 files, ~500 lines changed)
**Breaking**: NO - External API unchanged, internal data source changes
**Risk Level**: HIGH - Touches reporting, ML training, and summary commands

---

## Why

### Problem Statement

TheAuditor has a split-brain architecture for findings:
1. **Engines write to database** - patterns, terraform, linters all INSERT into `findings_consolidated`
2. **Consumers read from JSON** - final status, summary, ML, insights all read `.pf/raw/*.json` files

This causes:
- **False reporting**: Pipeline says `[CLEAN]` when database has 6,758 findings
- **Data loss**: JSON files are incomplete (wrong filenames, empty files)
- **Maintenance hell**: Two code paths to maintain for same data
- **AI-unfriendly**: JSON files are 1-3MB, impossible for AI to read

### Root Cause (VERIFIED 2025-11-28)

**JSON Readers (THE CANCER)**:

| File | Lines | What it reads | Should query |
|------|-------|---------------|--------------|
| `pipelines.py` | 1594-1660 | taint_analysis.json, vulnerabilities.json, findings.json (WRONG!) | findings_consolidated |
| `commands/summary.py` | 167-266 | lint.json, patterns.json, taint_analysis.json, terraform_findings.json, fce.json | findings_consolidated |
| `insights/ml/intelligence.py` | 240-430 | taint_analysis.json, vulnerabilities.json, patterns.json, fce.json | findings_consolidated |
| `commands/insights.py` | 276, 333 | graph_analysis.json, taint_analysis.json | findings_consolidated |
| `commands/report.py` | 61-65 | lint.json, fce.json, terraform_findings.json | findings_consolidated |

**Missing from findings_consolidated**:

| Tool | Current Location | Finding Count | Should be in findings_consolidated |
|------|------------------|---------------|-----------------------------------|
| github_workflows | github_workflows.json only | ~80KB of findings | YES |
| vulnerabilities (CVEs) | vulnerabilities.json only | ~442B (nearly empty) | YES |
| taint | taint_flows table | 0 (separate schema) | NO - User handling separately |

### Database Reality (VERIFIED 2025-11-28)

```sql
-- What's ALREADY in findings_consolidated (GOOD):
SELECT tool, COUNT(*) FROM findings_consolidated GROUP BY tool ORDER BY COUNT(*) DESC;

  mypy            2,851
  ruff            2,490
  patterns          855
  eslint            461
  graph-analysis     50
  cfg-analysis       43
  terraform           7
  churn-analysis      1
  TOTAL:          6,758 findings
```

### What JSON Files Exist (for reference)

```
.pf/raw/
  lint.json              1.9MB  (ruff/mypy/eslint - ALREADY in DB)
  fce.json               2.9MB  (correlation data - NOT findings)
  patterns.json          307KB  (patterns - ALREADY in DB)
  github_workflows.json   80KB  (workflow findings - MISSING from DB)
  churn_analysis.json    442KB  (churn - ALREADY in DB)
  terraform_findings.json  4KB  (terraform - ALREADY in DB)
  taint_analysis.json    694B   (taint - SEPARATE TABLE, user handling)
  vulnerabilities.json   442B   (CVEs - MISSING from DB)
  ...others (non-findings: deps, frameworks, graphs)
```

---

## What Changes

### Summary

| Change Type | Files | Lines |
|-------------|-------|-------|
| JSON readers → DB queries | 5 | ~200 deleted, ~100 added |
| Add github_workflows to DB | 2 | ~50 added |
| Add vulnerabilities to DB | 2 | ~30 added |
| **TOTAL** | ~9 unique files | ~380 lines changed |

### Part A: Fix JSON Readers (Query DB Instead)

#### A.1: pipelines.py Final Status (CRITICAL)
**Location**: `theauditor/pipelines.py:1594-1660`

**Current (BROKEN)**:
```python
# Lines 1594-1660 - Reads JSON files that don't exist or are wrong
taint_path = Path(root) / ".pf" / "raw" / "taint_analysis.json"
if taint_path.exists():
    try:
        # ... reads JSON, ZERO FALLBACK VIOLATION
    except Exception as e:
        print(f"[WARNING] ...")  # Silent failure

vuln_path = Path(root) / ".pf" / "raw" / "vulnerabilities.json"
# ... same pattern

patterns_path = Path(root) / ".pf" / "raw" / "findings.json"  # WRONG FILENAME!
# ... same pattern
```

**Replacement (CORRECT)**:
```python
def _get_findings_from_db(db_path: Path) -> dict[str, int]:
    """Query findings_consolidated for severity counts.

    ZERO FALLBACK: No try/except. Crashes if DB missing (correct behavior).
    """
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Security tools only - quality tools (ruff/mypy) don't affect security status
    SECURITY_TOOLS = ('patterns', 'terraform', 'github-workflows', 'vulnerabilities')

    cursor.execute("""
        SELECT severity, COUNT(*)
        FROM findings_consolidated
        WHERE tool IN (?, ?, ?, ?)
        GROUP BY severity
    """, SECURITY_TOOLS)

    counts = dict(cursor.fetchall())
    conn.close()

    return {
        'critical': counts.get('critical', 0),
        'high': counts.get('high', 0),
        'medium': counts.get('medium', 0),
        'low': counts.get('low', 0),
    }

# Usage - replaces 70 lines of JSON reading
findings = _get_findings_from_db(Path(root) / ".pf" / "repo_index.db")
critical_findings = findings['critical']
high_findings = findings['high']
# ...
```

#### A.2: commands/summary.py
**Location**: `theauditor/commands/summary.py:167-266`

**Current**: Loads 5 different JSON files with `load_json()` helper
**Fix**: Query findings_consolidated grouped by tool and severity

#### A.3: insights/ml/intelligence.py
**Location**: `theauditor/insights/ml/intelligence.py:240-430`

**Current**: 4 functions reading JSON for ML training data
**Fix**: Query findings_consolidated, keep fce.json (not findings)

#### A.4: commands/insights.py
**Location**: `theauditor/commands/insights.py:276, 333`

**Current**: Reads graph_analysis.json, taint_analysis.json
**Fix**: Query findings_consolidated for graph-analysis (taint stays JSON for now)

#### A.5: commands/report.py
**Location**: `theauditor/commands/report.py:61-65`

**Current**: Mentions reading JSON in docstring
**Fix**: Update to query DB, update docstring

### Part B: Add Missing Tools to findings_consolidated

#### B.1: GitHub Workflows Findings
**Location**: `theauditor/commands/workflows.py`

**Current behavior** (line 76):
- Writes to `.pf/raw/github_workflows.json` only
- Does NOT insert into findings_consolidated

**Required change**:
- After generating findings, INSERT into findings_consolidated
- Tool name: `github-workflows`
- Map workflow finding severity to standard severity levels

**Workflow finding dict (VERIFIED from workflows.py:394-403)**:
```python
# Actual keys in workflow findings:
{
    "file": str,           # Workflow file path
    "line": int,           # Line number
    "rule": str,           # Rule ID (e.g., 'script-injection')
    "tool": str,           # Always 'github-workflows'
    "message": str,        # Description
    "severity": str,       # 'critical', 'high', 'medium', 'low'
    "category": str,       # Category
    "confidence": float,   # 0.0-1.0
    "code_snippet": str,   # Code context
}
```

**Schema mapping** (direct - all keys exist):
```python
# Workflow finding → findings_consolidated
cursor.execute("""
    INSERT INTO findings_consolidated
    (file, line, column, rule, tool, message, severity, category, confidence, code_snippet, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    f['file'],
    f['line'],
    0,  # column not in workflow findings
    f['rule'],
    'github-workflows',
    f['message'],
    f['severity'],
    f['category'],
    f['confidence'],
    f.get('code_snippet', ''),
    datetime.now().isoformat(),
))
```

#### B.2: Vulnerability Scanner (CVEs)
**Location**: `theauditor/vulnerability_scanner.py`

**Current behavior** (line 630):
- Writes to `.pf/raw/vulnerabilities.json` only
- Does NOT insert into findings_consolidated

**Required change**:
- After scanning, INSERT into findings_consolidated
- Tool name: `vulnerabilities`
- Map CVE severity (CVSS) to standard severity levels

**Vulnerability dict (VERIFIED from vulnerability_scanner.py:530-540)**:
```python
# Actual keys in validated vulnerability findings:
{
    "package": str,           # Package name
    "version": str,           # Package version
    "manager": str,           # 'npm', 'pip', etc.
    "file": str,              # 'package.json', 'requirements.txt'
    "vulnerability_id": str,  # CVE-XXXX or GHSA-XXXX
    "severity": str,          # 'critical', 'high', 'medium', 'low'
    "title": str,             # Short title
    "summary": str,           # Description
    "details": str,           # Full details
    "confidence": float,      # 0.0-1.0
    # ... plus aliases, cwe, ghsa_id, etc.
}
```

**Schema mapping** (VERIFIED - uses actual keys):
```python
# CVE → findings_consolidated
cursor.execute("""
    INSERT INTO findings_consolidated
    (file, line, column, rule, tool, message, severity, category, confidence, cwe, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    v.get('file', 'package.json'),  # manifest file
    0,  # CVEs don't have line numbers
    0,
    v['vulnerability_id'],  # e.g., 'CVE-2023-12345'
    'vulnerabilities',
    f"{v['package']}@{v['version']}: {v.get('summary', v.get('title', ''))}",
    v['severity'],  # Already mapped by scanner
    'security',
    v.get('confidence', 0.7),
    ','.join(v.get('cwe', [])) if isinstance(v.get('cwe'), list) else v.get('cwe', ''),
    datetime.now().isoformat(),
))
```

### Part C: NOT In Scope (User Handling Separately)

| Item | Why excluded |
|------|--------------|
| Taint findings | User building enhanced taint beyond SAST, will add rules to findings_consolidated later |
| FCE correlation | Not findings - correlation/analysis results, different purpose |
| Schema cleanup (cfg_*, graph_* columns) | Separate refactor, doesn't block this work |
| JSON file deprecation | Keep writing JSON for human inspection, just stop READING them |

---

## Impact

### What Fixes

1. **Final status accuracy** - Reports actual findings from DB, not `[CLEAN]` lies
2. **Summary command** - Shows real data from single source
3. **ML training** - Trains on complete, accurate data
4. **GitHub workflow findings** - Now queryable in findings_consolidated
5. **CVE findings** - Now queryable in findings_consolidated
6. **ZERO FALLBACK compliance** - Removes 5+ try/except JSON-reading blocks

### What Does NOT Change

| Component | Status | Why |
|-----------|--------|-----|
| JSON file generation | UNCHANGED | Still written for human inspection |
| findings_consolidated schema | UNCHANGED | Using existing columns |
| Taint analysis | UNCHANGED | User handling separately |
| FCE correlation | UNCHANGED | Not findings data |
| Exit codes | UNCHANGED | Same logic, different data source |

### Files Modified

| File | Change Type | Risk |
|------|-------------|------|
| `theauditor/pipelines.py` | Delete JSON reads, add DB query | MEDIUM |
| `theauditor/commands/summary.py` | Replace JSON loads with DB queries | LOW |
| `theauditor/commands/insights.py` | Replace JSON loads with DB queries | LOW |
| `theauditor/commands/report.py` | Replace JSON loads with DB queries | LOW |
| `theauditor/insights/ml/intelligence.py` | Replace JSON loads with DB queries | MEDIUM |
| `theauditor/commands/workflows.py` | Add INSERT to findings_consolidated | MEDIUM |
| `theauditor/vulnerability_scanner.py` | Add INSERT to findings_consolidated | MEDIUM |

---

## Polyglot Assessment

**Q: Does this need Python + Node + Rust implementations?**

**A: NO - Python only.**

Rationale:
- This change is about the REPORTING/AGGREGATION layer
- All findings generators (linters, patterns, terraform, workflows, vulnerabilities) are Python
- Node extractors write to repo_index.db via Python orchestrator (indexer)
- Rust components are tree-sitter parsing, not findings generation
- The "orchestrator" is `pipelines.py` which is already in scope

**No polyglot changes required.**

---

## Risk Assessment

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| DB query returns different counts than JSON | MEDIUM | LOW | This is the POINT - DB is correct |
| Missing findings_consolidated columns | LOW | HIGH | Verified schema has all needed columns |
| ML training breaks with new data format | MEDIUM | MEDIUM | Same data, different source - test first |
| workflow/vuln INSERT fails | LOW | MEDIUM | Use same pattern as existing tools |

### Edge Cases

1. **Empty findings_consolidated**: Return zeros (legitimate - no findings)
2. **Missing .pf/repo_index.db**: Let it crash - ZERO FALLBACK
3. **Workflow file with no findings**: Don't INSERT anything (correct)
4. **CVE with no severity**: Map to 'medium' as default

---

## Success Criteria

All criteria MUST pass before marking complete:

- [ ] `aud full` shows actual finding counts (not `[CLEAN]` when DB has findings)
- [ ] `aud summary` queries DB, not JSON files
- [ ] `aud workflows analyze` inserts findings into findings_consolidated
- [ ] `aud deps --audit` inserts CVEs into findings_consolidated
- [ ] No `json.load()` calls for findings aggregation in modified files
- [ ] No try/except blocks around findings queries (ZERO FALLBACK)
- [ ] All existing tests pass

---

## Testing Strategy

### Manual Verification

```bash
# 1. Run full pipeline
aud full --offline

# 2. Check findings_consolidated has data
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT tool, COUNT(*) FROM findings_consolidated GROUP BY tool')
for row in c.fetchall():
    print(f'{row[0]}: {row[1]}')
conn.close()
"

# 3. Verify final status shows actual counts
# Expected: STATUS: [CRITICAL] or [HIGH] with real numbers

# 4. Verify new tools appear
# Expected: github-workflows and vulnerabilities in tool list
```

---

## Approval Required

### Architect Decision Points

1. **Security tool list** - Confirm which tools affect exit code:
   - INCLUDE: patterns, terraform, github-workflows, vulnerabilities
   - EXCLUDE: ruff, mypy, eslint (quality, not security)

2. **CVSS severity mapping**:
   - critical: CVSS >= 9.0
   - high: CVSS >= 7.0
   - medium: CVSS >= 4.0
   - low: CVSS < 4.0

3. **JSON files remain** - Confirm we keep writing JSON for human inspection

---

## Related Files (VERIFIED 2025-11-28)

| File | Line | Purpose |
|------|------|---------|
| `theauditor/pipelines.py` | 1594-1660 | JSON reading code (TO DELETE) |
| `theauditor/pipelines.py` | 1677-1692 | Return dict structure (PRESERVE) |
| `theauditor/commands/summary.py` | 167-266 | JSON reading for summary |
| `theauditor/commands/workflows.py` | 76 | JSON output path |
| `theauditor/commands/workflows.py` | 32 | Docstring mentions JSON |
| `theauditor/vulnerability_scanner.py` | 630-709 | JSON output methods |
| `theauditor/insights/ml/intelligence.py` | 240-430 | JSON reading for ML |
| `theauditor/commands/insights.py` | 276, 333 | JSON reading for insights |
| `theauditor/commands/report.py` | 61-65 | JSON reading docs |

---

**Next Step**: Architect reviews and approves/denies this proposal
