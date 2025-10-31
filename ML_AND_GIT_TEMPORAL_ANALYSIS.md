# TheAuditor ML and Git Temporal Analysis Layer

**Status**: Production-Ready  
**Module Location**: `theauditor/insights/ml/`  
**Key Feature**: 4-tier intelligent system with git temporal analysis

---

## Executive Summary

TheAuditor's ML layer learns patterns from execution history to predict risk and root causes:

- **Tier 1**: Pipeline log parsing (phase timing)
- **Tier 2**: Enhanced journal parsing (26+ event types)
- **Tier 3**: Raw artifact mining (taint, security, CFG data)
- **Tier 4**: Git temporal analysis (commits, authors, recency)

Produces 50+ features and trains 3 complementary models:
1. **Root Cause Classifier** - Which file caused failure?
2. **Next Edit Predictor** - Which file needs editing?
3. **Risk Scorer** - What's the risk score?

---

## Architecture Overview

### Directory Structure

```
theauditor/insights/ml/
├── __init__.py          # API exports
├── cli.py               # CLI orchestrator
├── loaders.py           # Historical data loading
├── features.py          # Feature extraction (50+ dims)
├── intelligence.py      # Smart parsing
└── models.py            # Model training, persistence
```

Legacy:
- `theauditor/ml.py` - Compatibility shim
- `theauditor/commands/ml.py` - Click CLI

### Integration Points

1. **Historical Data**: `.pf/history/full/*/`
2. **Features**: `.pf/repo_index.db` + `.pf/raw/*.json`
3. **Git Analysis**: `.git/` directory
4. **Models**: `.pf/ml/model.joblib` + metadata

---

## 4-Tier ML Intelligence System

### Tier 1: Pipeline Log Parsing

Source: `.pf/history/full/YYYYMMDD-HHMMSS/pipeline.log`

Extracts:
- Phase name and sequence
- Execution time
- Status (success/failure)
- Finding severity
- Exit code

### Tier 2: Enhanced Journal Parsing

Source: `.pf/history/full/YYYYMMDD-HHMMSS/journal.ndjson`

Captures:
- `phase_start` / `phase_end`
- `file_touch` (analysis operations)
- `finding` (security findings)
- `apply_patch` (patch outcomes)
- `pipeline_summary` (run statistics)

### Tier 3: Raw Artifact Parsers

Source: `.pf/raw/` directory

Artifacts:
- **taint_analysis.json** - Vulnerability paths, CWEs
- **security_patterns.json** - Secrets, weak crypto
- **fce.json** - Failure correlations, hotspots
- **cfg_analysis.json** - Complexity metrics
- **frameworks.json** - Framework detection

### Tier 4: Git Temporal Analysis

Source: `.git/` directory

Metrics (90-day window):
- `commits_90d` - Commit frequency
- `unique_authors` - Developer diversity
- `days_since_modified` - Recency (0=today)
- `days_active_in_range` - Active span

Key insight: High churn + many authors = instability

---

## Feature Engineering (50+ Dimensions)

### Sources

**File Metadata**:
- Bytes, LOC, extension type

**Graph Topology**:
- In/out degree, has routes, has SQL, centrality

**Execution History**:
- Journal touches, failures, RCA hits, AST checks

**Security Patterns**:
- JWT usage, SQL queries, hardcoded secrets, weak crypto

**Vulnerability Flows**:
- Critical/High/Medium findings, unique CWEs

**Type Coverage (TS)**:
- Annotation counts, coverage ratio

**CFG Complexity**:
- Block/edge counts, cyclomatic complexity

**Semantic Imports**:
- HTTP, DB, auth, test libraries

**AST Complexity**:
- Function/class/call counts, try/except, async

**Git Temporal**:
- Commit frequency, author diversity, recency, span

**Historical Findings**:
- Total/critical/high counts, recurring CWEs

**Text Features**:
- Path hashing, RCA tokenization

**Total**: 50+ dimensions

---

## Model Training

### Three Models

**Root Cause Classifier**:
- GradientBoostingClassifier (50 trees)
- Binary classification
- Label: RCA/FCE failures

**Next Edit Predictor**:
- GradientBoostingClassifier (50 trees)
- Binary classification
- Label: Journal touches

**Risk Scorer**:
- Ridge Regression
- Continuous output [0, 1]
- Label: Failure ratio

### Training Usage

```python
from theauditor.insights.ml import learn

result = learn(
    enable_git=True,
    print_stats=True,
    train_on="full"  # "full", "diff", "all"
)
```

### Human Feedback

```json
{
    "auth.py": {
        "is_risky": true,
        "is_root_cause": false,
        "will_need_edit": true
    }
}
```

Weighted 5x higher in training.

---

## Prediction

### Generate Suggestions

```python
from theauditor.insights.ml import suggest

result = suggest(topk=10, print_plan=True)
```

### Output Format

```json
{
    "generated_at": "2025-01-01T12:00:00+00:00",
    "workset_size": 45,
    "likely_root_causes": [
        {
            "path": "auth.py",
            "score": 0.92,
            "confidence_std": 0.04
        }
    ],
    "next_files_to_edit": [
        {
            "path": "service.py",
            "score": 0.78,
            "confidence_std": 0.08
        }
    ],
    "risk": [
        {
            "path": "api.py",
            "score": 0.65
        }
    ]
}
```

---

## CLI Commands

### Training

```bash
aud learn
aud learn --enable-git
aud learn --print-stats
aud learn --feedback /path/to/feedback.json
aud learn --train-on diff
```

### Feedback Retraining

```bash
aud learn-feedback --feedback-file /path/to/feedback.json
```

### Suggestions

```bash
aud suggest
aud suggest --topk 20 --print-plan
```

---

## Use Cases

### Root Cause Analysis
Rank likely culprits after failure:
```bash
aud suggest --topk 5 --print-plan
```

### Code Review Planning
Identify risky files before development:
```bash
aud learn --enable-git
aud suggest --topk 20 --print-plan
```

### Testing Prioritization
- High risk + low type coverage
- High complexity + few tests

### Developer Onboarding
- Volatile files (high churn) = complex learning
- Stable files (low churn) = safe changes

### Dependency Analysis
Architectural hubs:
- High out-degree = many imports
- High in-degree = widely used
- Changes risky

---

## Performance

### Training Time
- 1-2 seconds for 1000+ files
- Git: +5-10 seconds
- Database: +2-3 seconds

### Model Size
- Model: 2-5MB (joblib)
- Metadata: 20KB
- Total: 2-6MB

### Prediction
- 100ms for 100 files
- Linear scaling

---

## Key Design Decisions

### Why 4 Tiers?
1. Redundancy - Multiple sources validate
2. Flexibility - Degrade gracefully
3. Intelligence - High + low level
4. Temporal - Development patterns

### Why GradientBoosting?
- Non-linear relationships
- Feature interactions
- Importance extraction
- Calibration support

### Why Multiple Models?
- Root Cause - "who broke it?"
- Next Edit - "what needs fixing?"
- Risk - "how bad is it?"

### Why No Fallbacks?
- Missing data = broken pipeline
- Don't hide bugs
- Database fresh each run

---

## Troubleshooting

### No models found
Train them:
```bash
aud learn --print-stats
```

### No execution history
Run audit:
```bash
aud full
aud learn --print-stats
```

### ML deps missing
```bash
pip install -e .
```

### Cold-start warning
Normal with <500 files. Improves with more runs and feedback.

---

## References

- **Commit**: 4f2e4ae - feat(ml): Add git temporal analysis
- **Module**: `theauditor/insights/ml/`
- **Commands**: `theauditor/commands/ml.py`
- **Config**: `theauditor/config_runtime.py`

---

## Summary

TheAuditor's ML system provides:

1. **Root cause identification** - Which file broke it?
2. **Edit prediction** - Which file needs changes?
3. **Risk scoring** - Which files problematic?
4. **Git analysis** - How stable? Who owns?

Production-ready, schema-validated, seamlessly integrated.
