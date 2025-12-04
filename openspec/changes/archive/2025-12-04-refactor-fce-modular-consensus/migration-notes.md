# FCE Migration Notes

This document describes changes for users migrating from the old FCE format to the new vector-based output.

## Summary of Changes

The FCE command has been completely rewritten to use **Vector-Based Signal Density** instead of the old tool-count approach.

### Philosophy Change

**Old (Removed):**
- Meta-findings with risk levels (CRITICAL, HIGH_RISK, etc.)
- Hardcoded thresholds (complexity <= 20, percentile_90)
- Prescriptive language ("This file needs attention")

**New (Current):**
- Vector-based signal density (4 independent vectors)
- ZERO hardcoded thresholds
- Pure fact-stacking without judgment
- Philosophy: "I am not the judge, I am the evidence locker"

## Output Format Changes

### Text Output

**Old format:**
```
=== FCE Analysis ===
CRITICAL: file.py (complexity: 45, coverage: 30%)
HIGH_RISK: utils.py (5 tools flagged)
```

**New format:**
```
FCE CONVERGENCE REPORT
Files with convergence: 605

Distribution:
  4/4 vectors:   0 files
  3/4 vectors:   3 files
  2/4 vectors:  41 files
  1/4 vectors: 561 files

[3/4] theauditor/cli.py [S-PT]
  - 15 facts from 3 vectors
```

### JSON Output

**Old format:** Tool-centric with risk labels
```json
{
  "meta_findings": [
    {"file": "x.py", "risk": "CRITICAL", "tools": 5}
  ]
}
```

**New format:** Vector-centric with pure facts
```json
{
  "convergence_points": [
    {
      "file_path": "x.py",
      "signal": {
        "density": 0.75,
        "vectors_present": ["static", "flow", "structural"]
      },
      "facts": [...]
    }
  ]
}
```

## Vector Mapping

The new FCE uses 4 independent analysis vectors:

| Vector | Code | Old Equivalent | Sources |
|--------|------|----------------|---------|
| STATIC | S | Linter findings | ruff, eslint, bandit |
| FLOW | F | Taint findings | taint_flows table |
| PROCESS | P | Churn data | churn-analysis |
| STRUCTURAL | T | Complexity data | cfg-analysis |

## API Changes

### Importing FCE

**Old:**
```python
# Not possible - monolithic script
from theauditor import fce  # Failed
```

**New:**
```python
from theauditor.fce import FCEQueryEngine, VectorSignal

engine = FCEQueryEngine(root)
signal = engine.get_vector_density("src/auth.py")
print(signal.density_label)  # "3/4 vectors"
```

### CLI Changes

| Old Flag | New Flag | Notes |
|----------|----------|-------|
| (none) | `--format [text\|json]` | Choose output format |
| (none) | `--min-vectors N` | Filter by vector count |
| (none) | `--detailed` | Show facts in text mode |
| (none) | `--write` | Save to .pf/raw/fce.json |

### Integration Flags

New `--fce` flag added to:
- `aud explain <target> --fce` - Show vector signal for file
- `aud blueprint --fce` - FCE drill-down in blueprint

## Removed Features

The following features from the old FCE have been intentionally removed:

1. **Risk categorization** - No more CRITICAL/HIGH_RISK/etc labels
2. **Threshold-based filtering** - No more "complexity > 20" style filters
3. **Tool subprocess execution** - FCE now reads from database only
4. **Prescriptive recommendations** - No "should be" language

## Database Requirements

FCE reads from `.pf/repo_index.db`. Ensure you run:

```bash
aud full  # Complete analysis pipeline
```

The old FCE ran tools on-demand. The new FCE reads pre-computed results from the database only.

## Performance

| Metric | Old | New |
|--------|-----|-----|
| 605 files | ~10s | 74ms |
| Database reads | 0 | All |
| Tool execution | Yes | No |

The new FCE is ~135x faster because it reads from the database instead of running tools.

## Breaking Changes Summary

1. JSON output structure completely changed
2. No more risk labels in output
3. API is now importable (was not before)
4. Requires `aud full` to populate database first
5. Text output format is different
6. `--format json` flag is new (was implicit)

## Questions?

See `aud fce --help` for complete documentation.
