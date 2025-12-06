# Verification Report: Consolidate Findings Queries

**Verified**: 2025-11-28
**Verifier**: Opus (AI Lead Coder)
**Protocol**: teamsop.md Prime Directive

---

## Hypotheses & Verification

### Hypothesis 1: JSON files are read for final status aggregation
**Verification**: CONFIRMED

Evidence from `theauditor/pipelines.py:1594-1660`:
```python
taint_path = Path(root) / ".pf" / "raw" / "taint_analysis.json"
if taint_path.exists():
    try:
        with open(taint_path, encoding="utf-8") as f:
            taint_data = json.load(f)
            # ...
    except Exception as e:
        print(f"[WARNING] ...")  # ZERO FALLBACK VIOLATION
```

### Hypothesis 2: findings.json does not exist (wrong filename)
**Verification**: CONFIRMED

```bash
ls .pf/raw/findings.json  # File not found
ls .pf/raw/patterns.json  # EXISTS (307KB)
```

Code at line 1638 reads non-existent file:
```python
patterns_path = Path(root) / ".pf" / "raw" / "findings.json"  # WRONG!
```

### Hypothesis 3: findings_consolidated has data from security tools
**Verification**: CONFIRMED

```sql
SELECT tool, COUNT(*) FROM findings_consolidated GROUP BY tool;
-- patterns: 855
-- terraform: 7
-- (github-workflows: 0 - NOT YET INSERTED)
-- (vulnerabilities: 0 - NOT YET INSERTED)
```

### Hypothesis 4: GitHub workflow findings only go to JSON
**Verification**: CONFIRMED

`theauditor/commands/workflows.py:76`:
```python
@click.option("--output", default="./.pf/raw/github_workflows.json", help="Output JSON path")
```

No INSERT to findings_consolidated found in the file.

### Hypothesis 5: Vulnerability findings only go to JSON
**Verification**: CONFIRMED

`theauditor/vulnerability_scanner.py:630`:
```python
def save_findings_json(
    self, findings: list[dict[str, Any]], output_path: str = "./.pf/raw/vulnerabilities.json"
):
```

No INSERT to findings_consolidated found in the file.

### Hypothesis 6: Multiple consumers read JSON instead of DB
**Verification**: CONFIRMED

| File | Lines | JSON Read |
|------|-------|-----------|
| pipelines.py | 1594-1660 | taint_analysis.json, vulnerabilities.json, findings.json |
| commands/summary.py | 167-266 | lint.json, patterns.json, taint_analysis.json, terraform_findings.json |
| insights/ml/intelligence.py | 240-430 | taint_analysis.json, vulnerabilities.json, patterns.json, fce.json |
| commands/insights.py | 276, 333 | graph_analysis.json, taint_analysis.json |

---

## Discrepancies Found

### Discrepancy 1: findings.json vs patterns.json
- **Expected by code**: `.pf/raw/findings.json`
- **Actual file**: `.pf/raw/patterns.json`
- **Impact**: patterns findings never counted in final status

### Discrepancy 2: Empty vulnerabilities.json
- **Expected**: CVE data from dependency scan
- **Actual**: 442 bytes, nearly empty
- **Impact**: vulnerability findings never counted

### Discrepancy 3: Taint in separate table
- **Expected by proposal**: Taint in findings_consolidated
- **Actual**: Taint in `taint_flows` table with different schema
- **Resolution**: User handling separately - excluded from this change

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| DB query returns unexpected schema | LOW | HIGH | Verified schema has all needed columns |
| ML training breaks | MEDIUM | MEDIUM | Same data, different source - test first |
| workflow INSERT fails | LOW | MEDIUM | Use same pattern as existing tools |
| Breaking change to consumers | LOW | LOW | Return dict structure unchanged |

---

## Verification Status

- [x] JSON readers exist in claimed locations
- [x] findings.json does not exist (bug confirmed)
- [x] findings_consolidated has expected schema
- [x] GitHub workflows writes JSON only (no DB)
- [x] Vulnerability scanner writes JSON only (no DB)
- [x] Taint is in separate table (excluded from scope)

**Verification Phase**: COMPLETE
**Ready for Implementation**: YES
