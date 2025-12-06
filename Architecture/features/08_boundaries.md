# TheAuditor Boundaries Command

## Overview

The **BOUNDARIES** command analyzes security boundary enforcement by measuring the **distance** (in function calls) between where untrusted data enters the application and where security controls are enforced.

**Core Question**: "How far does untrusted data travel before hitting a security control?"

---

## Why It Matters

- **Multi-tenant SaaS compliance**: One missed tenant filter = data leak
- **Injection vulnerabilities**: Data validated too late reaches dangerous sinks
- **Authorization bypasses**: Protected operations without auth checks
- **Input validation gaps**: External data entering without validation

---

## Boundary Types

### 1. Input Validation (Fully Implemented)
Detects whether HTTP entry points validate external data before use.

**Entry Points**: HTTP routes (GET, POST, etc.) across frameworks
**Control Patterns**: `validate()`, `parse()`, `sanitize()`, `schema()`

### 2. Multi-Tenant Isolation (Planned)
Detects proper RLS (Row-Level Security) enforcement.

### 3. Authorization Checks (Planned)
Detects authentication/permission checks on protected operations.

### 4. Sanitization (Planned)
Detects sanitization before dangerous sinks.

---

## Quality Classification

| Quality | Condition | Risk |
|---------|-----------|------|
| **CLEAR** | Single control at distance 0 | Very Low |
| **ACCEPTABLE** | Single control at distance 1-2 | Low |
| **FUZZY** | Multiple controls OR distance 3+ | Medium-High |
| **MISSING** | No control found | Critical |

---

## Detection Algorithm

```
1. Find Entry Point (HTTP route handler)
2. Find Control Point (validation function)
3. Measure Distance (BFS through call graph)
4. Classify Quality (clear/acceptable/fuzzy/missing)
```

---

## Violation Types

| Type | Severity | Meaning |
|------|----------|---------|
| `NO_VALIDATION` | CRITICAL | No control in call chain |
| `VALIDATION_DISTANCE` | HIGH | Control at distance 3+ |
| `SCATTERED_VALIDATION` | MEDIUM | Multiple conflicting controls |

---

## CLI Usage

```bash
# Analyze all boundary types
aud boundaries

# Input validation only
aud boundaries --type input-validation

# JSON output
aud boundaries --format json

# Filter by severity
aud boundaries --severity critical

# Limit analysis scope
aud boundaries --max-entries 50
```

---

## Output Format

### Report (Human-Readable)
```
=== INPUT VALIDATION BOUNDARY ANALYSIS ===

Entry Points Analyzed: 47
  Clear Boundaries:      21 (45%)
  Acceptable Boundaries: 12 (26%)
  Fuzzy Boundaries:       8 (17%)
  Missing Boundaries:     6 (13%)

[CRITICAL] FINDINGS (6):
  1. POST /api/products
     File: src/routes/products.js:34
     Observation: No validation control detected
```

### JSON (Machine-Parseable)
```json
{
  "entry_point": "POST /api/users",
  "entry_file": "src/routes/users.js",
  "controls": [...],
  "quality": {
    "quality": "acceptable",
    "reason": "Single control at distance 2"
  },
  "violations": []
}
```

---

## How It Differs from Taint Analysis

| Aspect | BOUNDARIES | TAINT |
|--------|------------|-------|
| **Focus** | WHERE controls are placed | WHETHER data reaches sinks |
| **Question** | "How far from entry?" | "Can untrusted data reach sink?" |
| **Output** | Distance metrics + quality | Vulnerability paths |

### Together They Answer:
- BOUNDARIES: "Is there validation?" (control placement)
- TAINT: "Can data bypass it?" (actual flow)

---

## Security Value

| Boundary Quality | Risk | Recommendation |
|------------------|------|----------------|
| CLEAR (0) | Very Low | ✅ Maintain |
| ACCEPTABLE (1-2) | Low | ✅ Acceptable |
| FUZZY (3+) | Medium | ⚠️ Tighten |
| MISSING | Critical | 🔴 Immediate fix |
