# Implementation Tasks: Consolidate Findings Queries

**VERIFIED**: 2025-11-28 against live database and codebase
**Verifier**: Opus (AI Lead Coder)
**Protocol**: teamsop.md Prime Directive

---

## Prerequisites (MANDATORY - READ BEFORE ANY CODE)

1. [ ] Read `proposal.md` - Understand why, what, and impact
2. [ ] Read `design.md` - Understand technical decisions
3. [ ] Read `CLAUDE.md:189-244` - Understand ZERO FALLBACK policy
4. [ ] Read `teamsop.md` - Understand Prime Directive
5. [ ] Verify line numbers still match (code may have changed)

---

## 0. Verification Phase (Prime Directive)

### 0.1 Verify Database State
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

print('=== Current tools in findings_consolidated ===')
c.execute('SELECT tool, COUNT(*) FROM findings_consolidated GROUP BY tool ORDER BY COUNT(*) DESC')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

print('\n=== Check for github-workflows (should NOT exist yet) ===')
c.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE tool = 'github-workflows'\")
print(f'  github-workflows: {c.fetchone()[0]}')

print('\n=== Check for vulnerabilities (should NOT exist yet) ===')
c.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE tool = 'vulnerabilities'\")
print(f'  vulnerabilities: {c.fetchone()[0]}')

conn.close()
"
```

**Expected**: github-workflows and vulnerabilities should be 0

- [ ] Database verified, github-workflows = 0
- [ ] Database verified, vulnerabilities = 0

### 0.2 Verify JSON Readers Exist
```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -n "json.load\|load_json" theauditor/pipelines.py theauditor/commands/summary.py theauditor/insights/ml/intelligence.py
```

**Expected**: Multiple JSON load calls in these files

- [ ] JSON readers confirmed in pipelines.py
- [ ] JSON readers confirmed in summary.py
- [ ] JSON readers confirmed in intelligence.py

### 0.3 Verify Line Numbers Match

```bash
# Check pipelines.py aggregation code location
grep -n "critical_findings = 0" theauditor/pipelines.py
# Expected: Line ~1588

# Check workflows.py output path
grep -n "github_workflows.json" theauditor/commands/workflows.py
# Expected: Line ~76

# Check vulnerability_scanner.py output
grep -n "vulnerabilities.json" theauditor/vulnerability_scanner.py
# Expected: Lines ~630, ~709
```

- [ ] pipelines.py:1588 confirmed
- [ ] workflows.py:76 confirmed
- [ ] vulnerability_scanner.py:630 confirmed

---

## Phase 1: Add Missing Tool Inserts

### Task 1.1: Add GitHub Workflows → findings_consolidated

**File**: `theauditor/commands/workflows.py`
**Location**: After findings are generated, before JSON write

**Step 1**: Add import at top of file
```python
from datetime import datetime
```

**Step 2**: Add insert function (after imports, before commands)

**VERIFIED workflow finding keys (from workflows.py:394-403)**:
- `file`, `line`, `rule`, `tool`, `message`, `severity`, `category`, `confidence`, `code_snippet`

```python
def _insert_workflow_findings(findings: list[dict], db_path: Path) -> int:
    """Insert workflow findings into findings_consolidated.

    ZERO FALLBACK: No try/except. Crashes if DB issue (correct behavior).

    Workflow finding keys (VERIFIED):
        file, line, rule, tool, message, severity, category, confidence, code_snippet

    Args:
        findings: List of workflow finding dicts
        db_path: Path to repo_index.db

    Returns:
        Number of findings inserted
    """
    import sqlite3

    if not findings:
        return 0

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    for f in findings:
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

    conn.commit()
    inserted = len(findings)
    conn.close()
    return inserted
```

**Step 3**: Call insert function after findings generation
Find where findings are collected and JSON is written. Add:
```python
# After JSON write, insert into DB
db_path = Path(root) / ".pf" / "repo_index.db"
if db_path.exists():
    inserted = _insert_workflow_findings(all_findings, db_path)
    click.echo(f"[INFO] Inserted {inserted} workflow findings into database")
```

**Verification**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && aud workflows analyze
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE tool = 'github-workflows'\")
print(f'github-workflows findings: {c.fetchone()[0]}')
conn.close()
"
```

- [ ] Import added
- [ ] Insert function added
- [ ] Insert call added after JSON write
- [ ] Verified: github-workflows findings appear in DB

### Task 1.2: Add Vulnerabilities → findings_consolidated

**File**: `theauditor/vulnerability_scanner.py`
**Location**: In `save_findings_json` method and/or `scan_vulnerabilities` function

**Step 1**: Add CVSS mapping function
```python
def _cvss_to_severity(cvss_score: float) -> str:
    """Map CVSS score to standard severity level.

    Based on CVSS v3.0 qualitative severity rating scale:
    - Critical: 9.0 - 10.0
    - High: 7.0 - 8.9
    - Medium: 4.0 - 6.9
    - Low: 0.1 - 3.9
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

**Step 2**: Add insert function

**VERIFIED vulnerability dict keys (from vulnerability_scanner.py:530-540)**:
- `package`, `version`, `manager`, `file`, `vulnerability_id`, `severity`, `title`, `summary`, `details`, `confidence`, `cwe`

```python
def _insert_vulnerability_findings(vulnerabilities: list[dict], db_path: Path) -> int:
    """Insert CVE findings into findings_consolidated.

    ZERO FALLBACK: No try/except. Crashes if DB issue (correct behavior).

    Vulnerability dict keys (VERIFIED):
        package, version, manager, file, vulnerability_id, severity, title, summary, confidence, cwe

    Args:
        vulnerabilities: List of validated vulnerability dicts
        db_path: Path to repo_index.db

    Returns:
        Number of findings inserted
    """
    import sqlite3
    from datetime import datetime

    if not vulnerabilities:
        return 0

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    for v in vulnerabilities:
        # CWE may be list or string
        cwe_str = ','.join(v.get('cwe', [])) if isinstance(v.get('cwe'), list) else v.get('cwe', '')

        cursor.execute("""
            INSERT INTO findings_consolidated
            (file, line, column, rule, tool, message, severity, category, confidence, cwe, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            v.get('file', 'package.json'),  # File is in the dict
            0,  # CVEs don't have line numbers
            0,
            v['vulnerability_id'],  # e.g., 'CVE-2023-12345' or 'GHSA-xxxx'
            'vulnerabilities',
            f"{v['package']}@{v['version']}: {v.get('summary', v.get('title', ''))}",
            v['severity'],  # Already in dict (validated by scanner)
            'security',
            v.get('confidence', 0.7),
            cwe_str,
            datetime.now().isoformat(),
        ))

    conn.commit()
    inserted = len(vulnerabilities)
    conn.close()
    return inserted
```

**Step 3**: Call insert in `save_findings_json` method (line ~630)
```python
# After writing JSON, insert into DB
db_path = Path(output_path).parent.parent / "repo_index.db"
if db_path.exists():
    inserted = _insert_vulnerability_findings(findings, db_path)
    print(f"[INFO] Inserted {inserted} vulnerability findings into database")
```

**Verification**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && aud deps --audit
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE tool = 'vulnerabilities'\")
print(f'vulnerability findings: {c.fetchone()[0]}')
conn.close()
"
```

- [ ] CVSS mapping function added
- [ ] Insert function added
- [ ] Insert call added after JSON write
- [ ] Verified: vulnerabilities findings appear in DB

---

## Phase 2: Replace JSON Readers with DB Queries

### Task 2.1: Fix pipelines.py Final Status (CRITICAL)

**File**: `theauditor/pipelines.py`
**Location**: Lines 1588-1660 (approximately)

**Step 1**: Add helper function before `run_full_pipeline()`
```python
# Tool categories for final status
SECURITY_TOOLS = ('patterns', 'terraform', 'github-workflows', 'vulnerabilities')

def _get_security_findings_from_db(db_path: Path) -> dict[str, int]:
    """Query findings_consolidated for security tool severity counts.

    ZERO FALLBACK: No try/except. If DB query fails, pipeline crashes.
    This exposes bugs instead of hiding them with false '[CLEAN]' status.

    Args:
        db_path: Path to repo_index.db

    Returns:
        Dict with critical, high, medium, low counts from security tools only.
    """
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(SECURITY_TOOLS))
    cursor.execute(f"""
        SELECT severity, COUNT(*)
        FROM findings_consolidated
        WHERE tool IN ({placeholders})
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
```

**Step 2**: DELETE lines 1588-1660 (the JSON reading code)

**Current code to DELETE**:
```python
    critical_findings = 0
    high_findings = 0
    medium_findings = 0
    low_findings = 0
    total_vulnerabilities = 0

    taint_path = Path(root) / ".pf" / "raw" / "taint_analysis.json"
    if taint_path.exists():
        try:
            # ... all this JSON reading code
        except Exception as e:
            print(f"[WARNING] ...")

    vuln_path = Path(root) / ".pf" / "raw" / "vulnerabilities.json"
    # ... same pattern

    patterns_path = Path(root) / ".pf" / "raw" / "findings.json"  # WRONG!
    # ... same pattern
```

**Step 3**: REPLACE with DB query
```python
    # Query findings from database (source of truth)
    # ZERO FALLBACK: No try/except - crash if DB missing
    db_path = Path(root) / ".pf" / "repo_index.db"
    findings_counts = _get_security_findings_from_db(db_path)

    critical_findings = findings_counts['critical']
    high_findings = findings_counts['high']
    medium_findings = findings_counts['medium']
    low_findings = findings_counts['low']
    total_vulnerabilities = sum(findings_counts.values())
```

**Verification**:
```bash
# Should NOT show [CLEAN] when DB has findings
cd C:/Users/santa/Desktop/TheAuditor && aud full --offline
# Expected: STATUS: [CRITICAL] or [HIGH] with actual counts
```

- [ ] Helper function added
- [ ] Old JSON reading code deleted (lines 1588-1660)
- [ ] New DB query code added
- [ ] Verified: Final status shows actual counts

### Task 2.2: Fix commands/summary.py

**File**: `theauditor/commands/summary.py`
**Location**: Lines 116-266

**VERIFIED load_json calls (from summary.py)**:
| Line | File Loaded | What it returns | Replacement |
|------|-------------|-----------------|-------------|
| 127 | manifest.json | list of files | KEEP (not findings) |
| 141 | deps.json | dependency data | KEEP (not findings) |
| 142 | deps_latest.json | version data | KEEP (not findings) |
| 167 | lint.json | `{"findings": [...]}` | QUERY DB |
| 183 | patterns.json | `{"findings": [...]}` | QUERY DB |
| 185 | findings.json | fallback for patterns | DELETE (wrong filename) |
| 202 | graph_analysis.json | `{"summary": {...}}` | KEEP (metrics, not findings) |
| 221 | taint_analysis.json | `{"taint_paths": [...]}` | KEEP (taint separate) |
| 240 | terraform_findings.json | list of findings | QUERY DB |
| 266 | fce.json | correlation data | KEEP (not findings) |

**Step 1**: Add DB query function at top of file (after imports)
```python
def _get_findings_from_db(db_path: Path, tools: tuple[str, ...]) -> dict[str, int]:
    """Query findings_consolidated for severity counts by tools.

    ZERO FALLBACK: No try/except.

    Args:
        db_path: Path to repo_index.db
        tools: Tuple of tool names to query

    Returns:
        Dict of {severity: count}
    """
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(tools))
    cursor.execute(f"""
        SELECT severity, COUNT(*)
        FROM findings_consolidated
        WHERE tool IN ({placeholders})
        GROUP BY severity
    """, tools)

    counts = dict(cursor.fetchall())
    conn.close()
    return counts
```

**Step 2**: Replace lint.json load (line 167)

**Current** (line 167-181):
```python
    lint_data = load_json(raw_path / "lint.json")
    if lint_data and "findings" in lint_data:
        lint_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in lint_data["findings"]:
            severity = finding.get("severity", "info").lower()
            if severity in lint_by_severity:
                lint_by_severity[severity] += 1
        # ... uses lint_by_severity
```

**Replace with**:
```python
    # Query lint findings from database (source of truth)
    db_path = raw_path.parent / "repo_index.db"
    lint_by_severity = _get_findings_from_db(db_path, ('ruff', 'mypy', 'eslint'))
    # Ensure all keys exist
    for sev in ('critical', 'high', 'medium', 'low', 'info', 'warning', 'error'):
        lint_by_severity.setdefault(sev, 0)
    if sum(lint_by_severity.values()) > 0:
        # ... rest of existing code using lint_by_severity
```

**Step 3**: Replace patterns.json load (line 183-185)

**Current**:
```python
    patterns = load_json(raw_path / "patterns.json")
    if not patterns:
        patterns = load_json(raw_path / "findings.json")  # WRONG FILENAME
```

**Replace with**:
```python
    # Query pattern findings from database
    pattern_by_severity = _get_findings_from_db(db_path, ('patterns',))
    for sev in ('critical', 'high', 'medium', 'low', 'info'):
        pattern_by_severity.setdefault(sev, 0)
```

**Step 4**: Replace terraform_findings.json load (line 240)

**Current**:
```python
    terraform_findings = load_json(raw_path / "terraform_findings.json")
    if terraform_findings:
        # ... iterates through list
```

**Replace with**:
```python
    # Query terraform findings from database
    terraform_by_severity = _get_findings_from_db(db_path, ('terraform',))
    for sev in ('critical', 'high', 'medium', 'low', 'info'):
        terraform_by_severity.setdefault(sev, 0)
```

**Verification**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && aud summary
# Should show finding counts matching database
```

- [ ] DB query function added
- [ ] lint.json load replaced (line 167)
- [ ] patterns.json load replaced (line 183)
- [ ] findings.json fallback DELETED (line 185)
- [ ] terraform_findings.json load replaced (line 240)
- [ ] Verified: summary command works

### Task 2.3: Fix insights/ml/intelligence.py

**File**: `theauditor/insights/ml/intelligence.py`
**Location**: Lines 240-430 (parse_* functions)

**Functions to update**:
- `parse_taint_analysis()` - Line 240 - SKIP (taint separate)
- `parse_vulnerabilities()` - Line 303 - Replace with DB query
- `parse_patterns()` - Line 360 - Replace with DB query
- `parse_fce()` - Line 417 - SKIP (FCE is not findings)

**Step 1**: Update `parse_vulnerabilities()` to query DB
```python
def parse_vulnerabilities(raw_path: Path) -> list[dict]:
    """Get vulnerability data from findings_consolidated.

    Returns list of vulnerability findings for ML training.
    """
    import sqlite3

    db_path = raw_path.parent / "repo_index.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, rule, message, severity, cwe
        FROM findings_consolidated
        WHERE tool = 'vulnerabilities'
    """)

    findings = []
    for row in cursor.fetchall():
        findings.append({
            'file': row[0],
            'cve_id': row[1],
            'description': row[2],
            'severity': row[3],
            'cwe': row[4],
        })

    conn.close()
    return findings
```

**Step 2**: Update `parse_patterns()` to query DB
```python
def parse_patterns(raw_path: Path) -> list[dict]:
    """Get pattern findings from findings_consolidated.

    Returns list of pattern findings for ML training.
    """
    import sqlite3

    db_path = raw_path.parent / "repo_index.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, line, rule, message, severity, category, cwe
        FROM findings_consolidated
        WHERE tool = 'patterns'
    """)

    findings = []
    for row in cursor.fetchall():
        findings.append({
            'file': row[0],
            'line': row[1],
            'rule': row[2],
            'message': row[3],
            'severity': row[4],
            'category': row[5],
            'cwe': row[6],
        })

    conn.close()
    return findings
```

- [ ] parse_vulnerabilities() updated
- [ ] parse_patterns() updated
- [ ] Verified: ML functions return data from DB

### Task 2.4: Fix commands/insights.py

**File**: `theauditor/commands/insights.py`
**Location**: Lines 276, 333

**Step 1**: Line 276 - graph_analysis.json
Replace JSON load with DB query for graph-analysis tool.

**Step 2**: Line 333 - taint_analysis.json
SKIP - taint handled separately by user.

- [ ] graph_analysis.json load replaced
- [ ] taint_analysis.json SKIPPED (user handling)

### Task 2.5: Fix commands/report.py

**File**: `theauditor/commands/report.py`
**Location**: Lines 61-65 (docstring)

**Step 1**: Update docstring to reflect DB queries
```python
"""
Generates comprehensive audit report.

Data sources:
  - Lint results (findings_consolidated WHERE tool IN ('ruff', 'mypy', 'eslint'))
  - Pattern findings (findings_consolidated WHERE tool = 'patterns')
  - FCE correlations (.pf/raw/fce.json - correlation data, not findings)
  - Terraform findings (findings_consolidated WHERE tool = 'terraform')
"""
```

**Step 2**: Update any JSON loads in the command body

- [ ] Docstring updated
- [ ] JSON loads replaced (if any)

---

## Phase 3: Verification

### Task 3.1: Run Full Pipeline Test

```bash
cd C:/Users/santa/Desktop/TheAuditor && aud full --offline
```

**Expected**:
- Status shows [CRITICAL] or [HIGH] (not [CLEAN])
- Finding counts match database

- [ ] Pipeline completes without errors
- [ ] Status is NOT [CLEAN]
- [ ] Counts match database

### Task 3.2: Verify New Tools in Database

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT tool, COUNT(*) FROM findings_consolidated GROUP BY tool ORDER BY COUNT(*) DESC')
print('Tools in findings_consolidated:')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')
conn.close()
"
```

**Expected**: github-workflows and vulnerabilities appear in list

- [ ] github-workflows has findings
- [ ] vulnerabilities has findings (if any CVEs exist)

### Task 3.3: Verify No JSON Reads for Findings

```bash
# Should find NO json.load calls for findings files in modified code
grep -n "json.load" theauditor/pipelines.py | grep -v "^#"
# Expected: No matches in lines 1588-1660

grep -n "load_json.*patterns\|load_json.*lint\|load_json.*terraform" theauditor/commands/summary.py
# Expected: No matches
```

- [ ] No JSON reads in pipelines.py aggregation
- [ ] No JSON reads in summary.py for findings

### Task 3.4: Verify ZERO FALLBACK Compliance

```bash
# Should find NO try/except around findings queries
grep -A5 "findings_consolidated" theauditor/pipelines.py | grep -c "try:\|except"
# Expected: 0
```

- [ ] No try/except around DB queries

---

## Checklist Summary

### Phase 0: Verification
- [ ] 0.1 Database state verified
- [ ] 0.2 JSON readers exist confirmed
- [ ] 0.3 Line numbers match

### Phase 1: Add Missing Tool Inserts
- [ ] 1.1 GitHub Workflows → findings_consolidated
- [ ] 1.2 Vulnerabilities → findings_consolidated

### Phase 2: Replace JSON Readers
- [ ] 2.1 pipelines.py final status (CRITICAL)
- [ ] 2.2 commands/summary.py
- [ ] 2.3 insights/ml/intelligence.py
- [ ] 2.4 commands/insights.py
- [ ] 2.5 commands/report.py

### Phase 3: Verification
- [ ] 3.1 Full pipeline test
- [ ] 3.2 New tools in database
- [ ] 3.3 No JSON reads for findings
- [ ] 3.4 ZERO FALLBACK compliance

---

## Rollback Procedure

If anything goes wrong:

```bash
cd C:/Users/santa/Desktop/TheAuditor
git checkout theauditor/pipelines.py
git checkout theauditor/commands/summary.py
git checkout theauditor/commands/workflows.py
git checkout theauditor/commands/insights.py
git checkout theauditor/commands/report.py
git checkout theauditor/vulnerability_scanner.py
git checkout theauditor/insights/ml/intelligence.py
```

Time to rollback: ~30 seconds

---

## Post-Implementation

After all tasks complete:

1. Run `aud full --offline` one more time to confirm
2. Update success criteria in proposal.md (check all boxes)
3. Notify Architect implementation is complete
4. Archive change: `openspec archive consolidate-findings-queries --yes`
