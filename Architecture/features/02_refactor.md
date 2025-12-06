# TheAuditor Refactor System (YAML Rules)

## Overview

The REFACTOR system is a **database-first, YAML-driven framework** for detecting incomplete refactorings and code-schema mismatches. Unlike migration scripts that describe *what changed* in the database, refactor profiles describe *how your application should behave* after those changes.

**Core Philosophy**: Encode product-specific semantics in YAML without modifying the engine itself.

---

## What Problem Does It Solve?

**The Problem**: When you drop a table or rename a column, your migration files tell you *what changed*. But they don't tell you if the codebase actually stopped using the old schema. Code might still reference `orders.product_id` after you've dropped that column—and won't fail until runtime.

**The Solution**: YAML profiles define *what the refactored code should look like*. They separate legacy identifiers (must disappear) from new ones (must appear). The engine queries `.pf/repo_index.db` to find every violation.

---

## Architecture

```
aud refactor --file profile.yaml
         │                           │                       │
         ▼                           ▼                       ▼
  Migration Parser          YAML Profile Loader      RefactorEngine
  (Scan DROP/ALTER)         (Compile rules)          (Query database)
         │                           │                       │
         └───────────────────────────┴───────────────────────┘
                                     │
                                     ▼
                        ProfileEvaluation Output:
                        - Schema mismatches
                        - Refactor debt
                        - File priority queue
```

---

## YAML Rule Schema

```yaml
refactor_name: "plantflow_frontend_variants"
description: "Ensure every frontend surface references product_variant_id"
version: "2025-10-26"

metadata:
  owner: "Frontend Team"
  jira_epic: "PF-276"

rules:
  - id: "order-pos-cart"
    description: "Cart flows must use variant IDs"
    severity: "critical"
    category: "pos-flow"
    match:
      identifiers:
        - "product.unit_price"
        - "/.*\\.product\\.id/"      # Regex pattern
    expect:
      identifiers:
        - "product_variant.retail_price"
    scope:
      include: ["frontend/src/pages/pos/**"]
      exclude: ["tests/"]
    guidance: "Update CartItem to use variant pricing"
```

### Pattern Modes

| Mode | Syntax | Example |
|------|--------|---------|
| Literal | Plain string | `"product_id"` (word boundary match) |
| Regex | `/pattern/` | `"/.*\\.product\\.id/"` (full regex) |

---

## Rule Execution: Five-Stage Pipeline

1. **Profile Loading**: Parse YAML → RefactorProfile object
2. **Database Connection**: Open `.pf/repo_index.db`
3. **Rule Evaluation**: For each rule, compile patterns and query database
4. **Pattern Matching**: Hybrid SQL LIKE + Python regex for precision
5. **Output Generation**: ProfileEvaluation with violations and progress

### Query Sources

When you list identifiers, the engine searches:
- `symbols` table (variable definitions)
- `variable_usage` table (variable references)
- `assignments` table (targets and RHS)
- `function_call_args` table (function arguments)
- `sql_queries` table (SQL strings)
- `api_endpoints` table (HTTP paths)

---

## CLI Usage

```bash
# Analyze all migrations + find code violations
aud refactor --migration-limit 0

# Use custom refactor profile
aud refactor --file profile.yaml

# Export detailed JSON report
aud refactor --output breaking_changes.json

# Filter to specific files
aud refactor --file profile.yaml --in-file "OrderDetails"
```

---

## Output Sections

1. **Profile Summary**: Rules count, old references found
2. **Migration Analysis**: Removed tables, columns, renamed items
3. **Rule Breakdown**: Per-rule violations with file:line locations
4. **File Priority Queue**: Files sorted by violation count
5. **Schema Mismatch Summary**: Code touching dropped schema

---

## Integration with Planning

```bash
# Add task with refactor spec
aud planning add-task 1 --title "Migrate orders" --spec orders_spec.yaml

# Verify task using refactor profile
aud full --index && aud planning verify-task 1 1 --verbose
```

---

## Best Practices

1. **Be specific in regex**: `"product.unit_price"` not `"product"`
2. **Use scope to reduce noise**: `include: ["frontend/src/"]`
3. **Use `expect` to confirm coverage**: Verify new patterns exist
4. **Track version & metadata**: Date, owner, JIRA ticket
5. **One YAML per initiative**: Separate concerns for clarity
