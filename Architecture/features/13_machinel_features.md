# TheAuditor MachineL Features System

## Overview

TheAuditor's ML feature system extracts **109 dimensional features** from code repositories to power predictive models for:

1. **Root Cause Analysis** - Which files are likely causing failures
2. **Next Edit Prediction** - Which files need modification
3. **Risk Assessment** - Quantifying change risk (0-1)

---

## 16 Feature Tiers (109 Dimensions)

### Tier 1: File Metadata (4 features)
```
bytes_norm, loc_norm, is_js, is_py
```

### Tier 2: Graph Topology (4 features)
```
in_degree, out_degree, has_routes, has_sql
```

### Tier 3: Execution History (3 features)
```
touches, failures, successes
```
*Source: Historical journal.ndjson*

### Tier 4: Root Cause Analysis (1 feature)
```
rca_fails
```
*Source: Historical fce.json*

### Tier 5: AST Invariant Proofs (2 features)
```
ast_fails, ast_passes
```

### Tier 6: Git Churn (4 features)
```
git_commits_90d, git_unique_authors, git_days_since_modified, git_days_active_in_range
```

### Tier 7: Semantic Imports (4 features)
```
has_http_import, has_db_import, has_auth_import, has_test_import
```

### Tier 8: AST Complexity (5 features)
```
function_count, class_count, call_count, try_except_count, async_def_count
```

### Tier 9: Security Patterns (4 features)
```
jwt_usage_count, sql_query_count, has_hardcoded_secret, has_weak_crypto
```

### Tier 10: Vulnerability Flow (4 features)
```
critical_findings, high_findings, medium_findings, unique_cwe_count
```

### Tier 11: Type Coverage (5 features)
```
type_annotation_count, any_type_count, unknown_type_count, generic_type_count, type_coverage_ratio
```

### Tier 12: Control Flow Complexity (3 features)
```
cfg_block_count, cfg_edge_count, cyclomatic_complexity
```

### Tier 13: Impact & Coupling (8 features) - 2025 Feature Fusion
```
blast_radius, coupling_score, direct_upstream, direct_downstream,
transitive_impact, affected_files, is_api_endpoint, prod_dependency_count
```

### Tier 14: Agent Behavior (4 features)
```
agent_blind_edit_count, agent_duplicate_impl_rate, agent_missed_search_count, agent_read_efficiency
```

### Tier 15: Session Execution (4 features)
```
session_workflow_compliance, session_avg_risk_score, session_blind_edit_rate, session_user_engagement
```

### Tier 16: Text Features (50 features)
```
text_0 through text_49 (FNV-1a hashed path components)
```

---

## ML Models

### 1. Root Cause Classifier
- **Task**: Binary classification (is file root cause?)
- **Architecture**: StandardScaler + HistGradientBoostingClassifier
- **Calibration**: IsotonicRegression

### 2. Next Edit Predictor
- **Task**: Binary classification (will file be edited?)
- **Architecture**: Same pipeline

### 3. Risk Regression
- **Task**: Continuous scoring (0-1)
- **Architecture**: Ridge regression on scaled features

---

## Data Flow Architecture

```
Repository Code
    ↓
[Indexer Phase] → repo_index.db
    ↓
[Feature Extraction]
  - load_security_pattern_features()
  - load_vulnerability_flow_features()
  - load_impact_features()
  - ...
    ↓
[Session Logs] → Session Analysis
    ↓
[History Dir] → Historical Statistics
    ↓
[Git Repository] → Churn Analysis
    ↓
[Combined Feature Dict] (file_path → 109 features)
    ↓
[numpy Matrix] (N_files x 109)
    ↓
[ML Training] → model.joblib
```

---

## 2025 Feature Fusion: Impact Integration

### Batch Dependency Queries
```python
# Before: O(N*M) queries
for file in files:
    upstream = find_upstream(file)

# After: O(1) batch queries
upstream_results = find_upstream_batch(all_symbols)
```

### Coupling Score Formula
```
base_score = (direct_upstream × 3) + (direct_downstream × 2)
spread_multiplier = min(affected_files / 5, 3)
transitive_bonus = min(total_impact / 10, 20)
coupling_score = min(base_score × (1 + spread × 0.3) + bonus, 100)
```

---

## CLI Usage

### Training
```bash
aud learn --db-path .pf/repo_index.db --enable-git --session-dir ~/.claude/projects/
```

### Inference
```bash
aud suggest --workset .pf/workset.json --topk 10
```

### Output
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

## Feature Importance

The system saves top-20 features in `feature_importance.json`:
```json
{
  "root_cause": {
    "blast_radius": 0.234,
    "git_commits_90d": 0.156,
    "critical_findings": 0.128
  }
}
```

---

## Cold Start Handling

When <500 samples:
- Uses `class_weight="balanced"`
- Human feedback boosts sample weight 5x
- Large feature set (109 dims) helps interpolate
