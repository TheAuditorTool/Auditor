# TheAuditor MachineL (ML/Intelligence System)

## Overview

An intelligent **machine learning and impact analysis engine** that:
- Predicts code risk
- Identifies root causes
- Forecasts required edits
- Calculates blast radius of changes

Built on **sklearn's production-grade ML pipeline** with real codebase metrics.

---

## Three-Model Ensemble

| Model | Purpose | Algorithm |
|-------|---------|-----------|
| **Root Cause** | Identifies files likely causing failures | HistGradientBoostingClassifier |
| **Next Edit** | Forecasts files needing future editing | HistGradientBoostingClassifier |
| **Risk Regression** | Continuous risk score (0-1) | Ridge with L2 regularization |

### Pipeline Structure
```python
Pipeline([
    ("scaler", StandardScaler()),
    ("clf", HistGradientBoostingClassifier(
        learning_rate=0.1,
        max_iter=100,
        max_depth=5,
        class_weight="balanced",
    )),
])

# Probability calibration
calibrator = IsotonicRegression(out_of_bounds="clip")
```

---

## Feature Engineering (109 Dimensions)

### 16 Feature Tiers

| Tier | Features | Source |
|------|----------|--------|
| 1. File Metadata | bytes, loc | `files` table |
| 2. Language | is_js, is_py | Extension detection |
| 3. Graph Topology | in_degree, out_degree, has_routes | `refs` table |
| 4. Historical Journal | touches, failures, successes | `.pf/history/` |
| 5. Root Cause | rca_fails | FCE results |
| 6. AST Invariants | invariant_fails, passes | `ast_proofs.json` |
| 7. Git Churn | commits_90d, unique_authors | `git log` |
| 8. Semantic Imports | has_http, has_db, has_auth | Import classification |
| 9. AST Complexity | function_count, class_count | `symbols` table |
| 10. Security Patterns | jwt_usage, sql_query_count | Security tables |
| 11. Findings & CWE | critical/high/medium findings | `findings_consolidated` |
| 12. Type Coverage | type_annotation_count, any_type | Type tables |
| 13. Control Flow | cfg_blocks, cyclomatic_complexity | CFG tables |
| 14. Impact Radius | blast_radius, coupling_score | Impact analyzer |
| 15. AI Agent Behavior | blind_edit_count, hallucination_rate | Session logs |
| 16. Text Features | Hashed path components (50 dims) | FNV-1a hash |
```python
# Fowler-Noll-Vo hash for path components and RCA messages
for part in Path(path).parts:
    idx = fowler_noll_hash(part, dim=2000)
    features[idx] += 1.0
```

---

## Impact Analyzer

### Blast Radius Calculation
```python
def analyze_impact(db_path, target_file, target_line):
    # 1. Find symbol at target_line
    # 2. Find UPSTREAM (who calls this)
    # 3. Find DOWNSTREAM (what this calls)
    # 4. Expand to transitive dependencies (2 hops)
    # 5. Classify into production/tests/config/external
```

### Coupling Score
```python
def calculate_coupling_score(impact_data) -> int:
    base_score = (direct_upstream * 3) + (direct_downstream * 2)
    spread_multiplier = min(affected_files / 5, 3)
    return min(score, 100)  # 0-100 scale
```

**Interpretation:**
- 0-30: Low coupling - safe to refactor
- 30-70: Medium coupling - needs careful review
- 70-100: High coupling - requires design change

---

## Probability Calibration

Converts raw ML probabilities into reliable confidence scores:

```python
calibrator = IsotonicRegression(out_of_bounds="clip")
calibrator.fit(raw_probs, actual_labels)
calibrated_probs = calibrator.transform(raw_probs)
```

**Why**: Raw model saying "0.92" doesn't mean 92% actual frequency. Calibration ensures it does.

---

## CLI Commands

### `aud learn` - Training
```bash
aud learn --db-path .pf/repo_index.db \
          --enable-git \
          --session-dir ~/.claude/projects/
```

**Output:**
```json
{
  "n_samples": 2847,
  "n_features": 109,
  "root_cause_positive_ratio": 0.15,
  "cold_start": false
}
```

### `aud suggest` - Inference
```bash
aud suggest --workset .pf/workset.json --topk 10
```

**Output:**
```json
{
  "likely_root_causes": [
    {"path": "auth/jwt.py", "score": 0.87}
  ],
  "next_files_to_edit": [
    {"path": "middleware.py", "score": 0.92}
  ]
}
```

---

## Model Persistence

```python
model_data = {
    "root_cause_clf": root_cause_clf,
    "next_edit_clf": next_edit_clf,
    "risk_reg": risk_reg,
    "scaler": scaler,
    "root_cause_calibrator": calibrator,
}
joblib.dump(model_data, ".pf/ml/model.joblib")
```

---

## Cold Start Handling

When training on <500 samples:
- `class_weight="balanced"` over-weights rare class
- Human feedback (`feedback_path`) boosts sample weight 5x
- Large feature set (109 dims) helps interpolate

---

## Data Sources

| Source | Location | Extractor |
|--------|----------|-----------|
| File metadata | `repo_index.db` | Indexer |
| Security findings | `findings_consolidated` | Linters + rules |
| Git history | `.git/` | Git CLI |
| Session logs | `~/.claude/projects/` (default) | Session analyzer (`--session-dir` for custom) |
| Historical journal | `.pf/history/` | Pipeline logger |
