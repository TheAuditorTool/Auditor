# TheAuditor Impact Analyzer

## Overview

The **Impact Analyzer** calculates the **blast radius** of code changes before they're made. It answers: "What breaks if I change this?"

---

## Why Impact Analysis Matters

- **Reduces Risk**: Understand scope before refactoring
- **Informs Planning**: Assess safety of changes
- **Prevents Regressions**: Identify dependent tests and code
- **Measures Coupling**: Identify tightly coupled code
- **Enables Safe Refactoring**: Decide when to extract interfaces first

---

## Blast Radius Calculation

### Step 1: Find Target Symbol
Query `symbols` table for function/class at target location.

### Step 2: Find Upstream Dependencies
Who calls this symbol? (via `function_call_args` table)

### Step 3: Find Downstream Dependencies
What does this symbol call?

### Step 4: Calculate Transitive Impact
Recursively apply Steps 2-3 up to `max_depth` (default: 2)
- Uses visited set to prevent cycles

### Step 5: Aggregate Impact
```python
{
    "direct_upstream": len(upstream),
    "direct_downstream": len(downstream),
    "total_impact": len(all_impacts),
    "affected_files": len(distinct_files)
}
```

---

## Coupling Score (0-100)

### Formula
```python
base_score = (direct_upstream × 3) + (direct_downstream × 2)
spread_multiplier = min(affected_files / 5, 3)
transitive_bonus = min(total_impact / 10, 20)
score = base_score × (1 + spread × 0.3) + bonus
return min(score, 100)
```

### Interpretation

| Score | Level | Action |
|-------|-------|--------|
| 0-29 | LOW | Safe to refactor directly |
| 30-69 | MEDIUM | Review callers, consider phased rollout |
| 70-100 | HIGH | Extract interface first |

---

## File Classification

Dependencies are bucketed by type:

| Category | Detection | Risk |
|----------|-----------|------|
| **Production** | Regular code files | High - coordinate |
| **Tests** | test/, spec/, __tests__ | Lower - will fail visibly |
| **Config** | .json, .yaml, config/ | Low - string-based |
| **External** | Unresolved symbols | Out of scope |

---

## CLI Usage

```bash
# By symbol name (recommended)
aud impact --symbol AuthManager

# By file + line
aud impact --file src/auth.py --line 42

# Planning context (agent-friendly)
aud impact --symbol validate --planning-context

# JSON output
aud impact --symbol validate --json

# Cross-stack tracing
aud impact --file src/api.js --line 50 --trace-to-backend
```

---

## Output Modes

### Default Report
```
============================================================
IMPACT ANALYSIS REPORT
============================================================

Target: validate (function) at src/auth.py:42

IMPACT SUMMARY:
  Direct Upstream: 8
  Direct Downstream: 3
  Total Impact: 14 symbols
  Affected Files: 7

RISK ASSESSMENT:
  Change Risk Level: MEDIUM
  Impact Breakdown: 6 production, 2 tests, 1 config
============================================================
```

### Planning Context
Includes:
- Coupling score with interpretation
- Dependencies by category
- Suggested phases for rollout
- Recommendations based on coupling

---

## Integration with ML

Impact features feed into ML models:

```python
"blast_radius"           # log1p(total_impact)
"coupling_score"         # min(total_impact / 50, 1.0)
"direct_upstream"        # Caller count
"direct_downstream"      # Callee count
"transitive_impact"      # Multi-hop dependencies
"prod_dependency_count"  # Production-only callers
```

### Training Impact
Files with high blast_radius + high churn = higher predicted risk.

---

## Use Cases

### 1. Pre-Refactor Assessment
```bash
aud impact --symbol UserService --planning-context
# If coupling > 70, extract interface first
```

### 2. API Change Planning
```bash
aud impact --file src/handlers/auth.py --line 50
# Shows all callers to coordinate with
```

### 3. Dead Code Confirmation
```bash
aud impact --symbol legacyFunction
# If upstream is empty, safe to remove
```

### 4. PR Review Risk Gate
```bash
aud impact --symbol $TARGET --json | jq '.impact_summary.total_impact > 20'
# Fail if high impact
```

---

## Standalone vs ML-Integrated

### Standalone Mode
```bash
aud impact --symbol validate --planning-context
```
Returns exact blast radius, coupling score, classification.

### ML-Integrated Mode
```bash
aud suggest  # Uses impact features in prediction
```
Returns predicted risky files based on learned patterns.
