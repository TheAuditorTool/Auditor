# Implementation Tasks: Pipeline Reporting Refactor

**VERIFIED**: 2025-11-25 against live database and codebase
**Verifier**: Opus (AI Lead Coder)
**Protocol**: teamsop.md Prime Directive

---

## Prerequisites (MANDATORY - READ BEFORE ANY CODE)

1. [ ] Read `proposal.md` - Understand why, what, and impact
2. [ ] Read `CLAUDE.md:207-262` - Understand ZERO FALLBACK policy
3. [ ] Read `teamsop.md` - Understand Prime Directive
4. [ ] Verify line numbers still match (code may have changed since this was written)

---

## VERIFIED DATA (2025-11-25)

### Database Schema
```
findings_consolidated columns:
  id, file, line, column, rule, tool, message, severity,
  category, confidence, code_snippet, cwe, timestamp, details_json
```

### Security Tool Severity Counts
```sql
SELECT severity, COUNT(*) FROM findings_consolidated
WHERE tool IN ('patterns', 'taint', 'terraform', 'cdk')
GROUP BY severity ORDER BY COUNT(*) DESC

Result:
  high: 4,177
  medium: 644
  critical: 226
  info: 138
  low: 23
```

### JSON Files in .pf/raw/
```
patterns.json     - 1.7MB - EXISTS (but code reads wrong filename!)
findings.json     - DOES NOT EXIST (bug: code tries to read this)
taint_analysis.json - 19KB - EXISTS
vulnerabilities.json - 442B - EXISTS (nearly empty)
```

### Code Locations (VERIFIED)
```
pipelines.py:273      - async def run_full_pipeline()
pipelines.py:1645     - Start of aggregation code (initialize counters)
pipelines.py:1652-1668 - Read taint_analysis.json (try/except VIOLATION)
pipelines.py:1670-1690 - Read vulnerabilities.json (try/except VIOLATION)
pipelines.py:1692-1713 - Read findings.json WRONG FILENAME (try/except VIOLATION)
pipelines.py:1731-1746 - Return dict with findings
full.py:171           - Displays "[CLEAN]" based on findings dict
journal.py:436        - Uses total_vulnerabilities from findings dict
```

---

## Phase 0: Pre-Implementation Verification

### Task 0.1: Verify Code Locations Match
**Why**: Line numbers may have drifted since this spec was written

**Commands**:
```bash
# Verify line 1645 is start of aggregation
grep -n "Collect findings summary" theauditor/pipelines.py
# Expected: 1645:    # Collect findings summary from generated reports

# Verify line 1694 has wrong filename
grep -n "findings.json" theauditor/pipelines.py
# Expected: 1694:    patterns_path = Path(root) / ".pf" / "raw" / "findings.json"

# Verify return structure at 1731
grep -n "return {" theauditor/pipelines.py | tail -5
# Expected: 1731:    return {
```

**If lines don't match**: Update this tasks.md with correct line numbers before proceeding.

- [ ] Line 1645 confirmed as aggregation start
- [ ] Line 1694 confirmed as wrong filename
- [ ] Line 1731 confirmed as return statement

### Task 0.2: Verify Database Has Expected Data
**Why**: Ensure DB query will return expected results

**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

# Verify table exists
c.execute('SELECT COUNT(*) FROM findings_consolidated')
total = c.fetchone()[0]
print(f'Total findings: {total}')

# Verify security tools have findings
c.execute('''
    SELECT tool, COUNT(*) FROM findings_consolidated
    WHERE tool IN ('patterns', 'taint', 'terraform', 'cdk')
    GROUP BY tool
''')
print('Security tool counts:')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
"
```

**Expected output**:
```
Total findings: ~19934
Security tool counts:
  cdk: 14
  patterns: 5179
  taint: 1
  terraform: 7
```

- [ ] findings_consolidated table exists
- [ ] Security tools have findings

---

## Phase 1: Add New Function (BEFORE deleting old code)

### Task 1.1: Add SECURITY_TOOLS Constant
**File**: `theauditor/pipelines.py`
**Location**: After imports, near line 50-60 (with other constants)

**Code to ADD**:
```python
# Tool categories for final status determination
# Security tools produce actual vulnerabilities (affect exit code)
# Quality tools (ruff, eslint, mypy) are informational only
SECURITY_TOOLS = frozenset({'patterns', 'taint', 'terraform', 'cdk'})
```

**Verification**:
```bash
grep -n "SECURITY_TOOLS" theauditor/pipelines.py
# Expected: Shows line number with frozenset definition
```

- [ ] SECURITY_TOOLS constant added

### Task 1.2: Add _get_findings_from_db Function
**File**: `theauditor/pipelines.py`
**Location**: After SECURITY_TOOLS constant (before run_full_pipeline)

**Code to ADD**:
```python
def _get_findings_from_db(root: Path) -> dict:
    """Query findings_consolidated for severity counts.

    ZERO FALLBACK: No try/except. If DB query fails, pipeline crashes.
    This exposes bugs instead of hiding them with false "[CLEAN]" status.

    Args:
        root: Project root path containing .pf/ directory

    Returns:
        Dict with critical, high, medium, low, total_vulnerabilities counts.
        Only counts SECURITY_TOOLS (patterns, taint, terraform, cdk).
        Quality tools (ruff, eslint, mypy) are excluded from security status.
    """
    import sqlite3

    db_path = root / ".pf" / "repo_index.db"

    # ZERO FALLBACK: If DB doesn't exist, this crashes with FileNotFoundError
    # That's correct behavior - can't report findings without a database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Query security tools only
    # Uses parameterized query to avoid SQL injection (even though we control the values)
    placeholders = ','.join('?' * len(SECURITY_TOOLS))
    cursor.execute(f"""
        SELECT severity, COUNT(*)
        FROM findings_consolidated
        WHERE tool IN ({placeholders})
        GROUP BY severity
    """, tuple(SECURITY_TOOLS))

    counts = dict(cursor.fetchall())
    conn.close()

    return {
        'critical': counts.get('critical', 0),
        'high': counts.get('high', 0),
        'medium': counts.get('medium', 0),
        'low': counts.get('low', 0),
        'total_vulnerabilities': sum(counts.values())
    }
```

**Verification**:
```bash
# Verify function exists
grep -n "def _get_findings_from_db" theauditor/pipelines.py
# Expected: Shows line number

# Test function works
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from pathlib import Path
import sys
sys.path.insert(0, '.')
# Import after adding to path
exec(open('theauditor/pipelines.py').read().split('async def run_full_pipeline')[0])
result = _get_findings_from_db(Path('.'))
print(result)
"
# Expected: {'critical': 226, 'high': 4177, 'medium': 644, 'low': 23, 'total_vulnerabilities': 5208}
```

- [ ] _get_findings_from_db function added
- [ ] Function returns expected counts when tested

---

## Phase 2: Replace Old Code

### Task 2.1: Delete JSON Reading Code
**File**: `theauditor/pipelines.py`
**Location**: Lines 1645-1713 (approximately 70 lines)

**What to DELETE** (verify line numbers first!):
- Lines 1645-1650: Counter initialization (critical_findings = 0, etc.)
- Lines 1652-1668: taint_analysis.json reading with try/except
- Lines 1670-1690: vulnerabilities.json reading with try/except
- Lines 1692-1713: findings.json reading with try/except (WRONG FILENAME)

**BEFORE deletion, verify**:
```bash
# Count lines to delete
sed -n '1645,1713p' theauditor/pipelines.py | wc -l
# Expected: ~69 lines
```

- [ ] Verified line range before deletion
- [ ] JSON reading code deleted (lines 1645-1713)

### Task 2.2: Add Database Query Code
**File**: `theauditor/pipelines.py`
**Location**: Where old code was (around line 1645)

**Code to ADD**:
```python
    # Query findings from database (source of truth)
    # ZERO FALLBACK: No try/except - if DB missing, crash is correct behavior
    findings_data = _get_findings_from_db(Path(root))
    critical_findings = findings_data['critical']
    high_findings = findings_data['high']
    medium_findings = findings_data['medium']
    low_findings = findings_data['low']
    total_vulnerabilities = findings_data['total_vulnerabilities']
```

**Verification**:
```bash
# Verify no json.load in aggregation section
grep -n "json.load" theauditor/pipelines.py
# Expected: Should NOT show lines 1645-1713

# Verify no try/except in aggregation section
sed -n '1640,1720p' theauditor/pipelines.py | grep -n "try:\|except"
# Expected: No matches (or only matches outside aggregation code)
```

- [ ] Database query code added
- [ ] No json.load in aggregation section
- [ ] No try/except in aggregation section

---

## Phase 3: Verification

### Task 3.1: Verify Return Dict Structure Unchanged
**Why**: full.py and journal.py depend on exact structure

**Command**:
```bash
grep -A 20 "return {" theauditor/pipelines.py | tail -25
```

**Expected structure preserved**:
```python
return {
    ...
    "findings": {
        "critical": critical_findings,
        "high": high_findings,
        "medium": medium_findings,
        "low": low_findings,
        "total_vulnerabilities": total_vulnerabilities,
    }
}
```

- [ ] Return dict structure unchanged

### Task 3.2: Run Full Pipeline Test
**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && aud full --offline
```

**Expected output** (at end):
```
AUDIT FINAL STATUS
==============================================================
STATUS: [CRITICAL] - Audit complete. Found 226 critical vulnerabilities.
Immediate action required - deployment should be blocked.

Findings breakdown:
  - Critical: 226
  - High: 4177
  - Medium: 644
  - Low: 23
```

**NOT expected** (this was the bug):
```
STATUS: [CLEAN] - No critical or high-severity issues found.
```

- [ ] Pipeline runs without errors
- [ ] Status shows [CRITICAL] with ~226 critical findings
- [ ] Findings breakdown shows actual counts

### Task 3.3: Verify Journal Recording
**Command**:
```bash
# Check journal received correct total_vulnerabilities
grep -r "total_findings" .pf/journal*.jsonl | tail -1
```

**Expected**: total_findings should be ~5208 (sum of security tool findings)

- [ ] Journal receives correct total_vulnerabilities

---

## Phase 4: Cleanup

### Task 4.1: Remove Unused Imports (if any)
**Check**:
```bash
# If json is no longer used in aggregation, check if it's used elsewhere
grep -n "^import json\|^from.*json" theauditor/pipelines.py
```

**If json import is only used for deleted code**: Remove import

- [ ] Unused imports removed (or confirmed still needed)

### Task 4.2: Update Line 1578 Comment
**Current** (line 1578):
```python
write_summary(f"  * .pf/findings.json - Pattern detection results")
```

**This is documentation only** - patterns.json is still written, but the filename in the summary message is wrong. This is a separate cosmetic issue.

**Decision**: Fix now or defer?
- If fix now: Change to `patterns.json`
- If defer: Add to backlog

- [ ] Line 1578 addressed (fixed or deferred)

---

## Checklist Summary

### Phase 0: Pre-Implementation Verification
- [ ] 0.1 Line numbers verified
- [ ] 0.2 Database has expected data

### Phase 1: Add New Function
- [ ] 1.1 SECURITY_TOOLS constant added
- [ ] 1.2 _get_findings_from_db function added and tested

### Phase 2: Replace Old Code
- [ ] 2.1 JSON reading code deleted
- [ ] 2.2 Database query code added

### Phase 3: Verification
- [ ] 3.1 Return dict structure unchanged
- [ ] 3.2 Full pipeline test passes
- [ ] 3.3 Journal recording verified

### Phase 4: Cleanup
- [ ] 4.1 Unused imports removed
- [ ] 4.2 Line 1578 addressed

---

## Rollback Procedure

If anything goes wrong:

```bash
cd C:/Users/santa/Desktop/TheAuditor
git checkout theauditor/pipelines.py
```

Time to rollback: ~10 seconds

---

## Post-Implementation

After all tasks complete:

1. Run `aud full --offline` one more time to confirm
2. Update success criteria in proposal.md (check all boxes)
3. Notify Architect implementation is complete
4. Archive change: `openspec archive refactor-pipeline-reporting --yes`
