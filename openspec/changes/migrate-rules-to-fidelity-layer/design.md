# Design: Migrate Rules to Fidelity Layer (Phase 2)

## Overview

This is a 10-terminal parallel migration with 2 waves. Each terminal gets explicit file assignments. No conflicts possible because files are strictly partitioned.

**Timeline:**
1. Foundation (1 terminal, blocking) - Verify Phase 1 complete
2. Wave 1 (10 terminals parallel) - 50 files
3. Wave 2 (10 terminals parallel) - 45 files

---

## Schema Reference (EMBEDDED - Do NOT Hunt)

### TABLES Dict

Location: `theauditor/indexer/schema.py:20-32`

```python
from theauditor.indexer.schema import TABLES

# TABLES is dict[str, TableSchema] composed from sub-modules:
TABLES: dict[str, TableSchema] = {
    **CORE_TABLES,           # symbols, refs, files, assignments, function_call_args
    **SECURITY_TABLES,       # sql_queries, taint_flows, vulnerabilities
    **FRAMEWORKS_TABLES,     # react_hooks, sequelize_models, express_routes
    **PYTHON_TABLES,         # python_orm_models, python_validators
    **NODE_TABLES,           # node_dependencies, package_configs
    **RUST_TABLES,           # rust_structs, rust_unsafe_blocks
    **GO_TABLES,             # go_structs, go_interfaces
    **BASH_TABLES,           # bash_commands, shell_scripts
    **INFRASTRUCTURE_TABLES, # docker_configs, k8s_resources
    **PLANNING_TABLES,       # plans, plan_tasks
    **GRAPHQL_TABLES,        # graphql_types, graphql_resolvers
}
```

**Key tables for rules:**
- `symbols` - functions, classes, variables (name, path, line, type)
- `function_call_args` - function calls (file, line, callee_function, argument_expr, argument_index, param_name)
- `assignments` - variable assignments (file, line, target_var, source_expr, in_function)
- `sql_queries` - detected SQL strings (file_path, line_number, query_text, has_interpolation, command)
- `import_styles` - import statements (file, line, package, import_style)
- `template_literals` - template strings (file, line, content)
- `react_components` - React components (file, name, start_line, end_line, has_jsx)

### TableSchema Structure

Location: `theauditor/indexer/schemas/utils.py:74-87`

```python
@dataclass
class TableSchema:
    """Represents a complete table schema."""
    name: str
    columns: list[Column]
    indexes: list[tuple[str, list[str]]] = field(default_factory=list)
    primary_key: list[str] | None = None
    unique_constraints: list[list[str]] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    def column_names(self) -> list[str]:
        """Get list of column names in definition order."""
        return [col.name for col in self.columns]
```

### ForeignKey Structure

Location: `theauditor/indexer/schemas/utils.py:36-71`

```python
@dataclass
class ForeignKey:
    """Foreign key relationship metadata for JOIN query generation."""
    local_columns: list[str]      # Columns in this table
    foreign_table: str            # Referenced table name
    foreign_columns: list[str]    # Columns in referenced table
```

**Usage for Q class FK auto-detection:**
```python
# Q looks up FK like this:
schema = TABLES["function_call_args"]
for fk in schema.foreign_keys:
    if fk.foreign_table == "symbols":
        # Found: can auto-generate JOIN condition
        # fk.local_columns = ["file", "callee_function"]
        # fk.foreign_columns = ["path", "name"]
```

---

## Q Class API Reference (EMBEDDED - Do NOT Hunt)

Location: `theauditor/rules/query.py` (created in Phase 1)

### Constructor
```python
Q(table: str)
```
- Validates table exists in TABLES
- Raises `ValueError` if unknown table

### Chainable Methods (all return `self`)

| Method | Description |
|--------|-------------|
| `.select(*columns)` | Columns to select. If empty, selects all. |
| `.where(condition, *params)` | WHERE clause. Multiple calls AND together. |
| `.join(table, on=None, join_type="INNER")` | JOIN clause (see below for `on` formats) |
| `.left_join(table, on=None)` | Shorthand for `join(..., join_type="LEFT")` |
| `.with_cte(name, subquery: Q)` | Add CTE. Multiple calls add multiple CTEs. |
| `.order_by(clause)` | ORDER BY clause (string) |
| `.limit(n)` | LIMIT clause (int) |
| `.group_by(*columns)` | GROUP BY columns |

### Join `on` Parameter Formats

1. **`on=None`** - Auto-detect from ForeignKey metadata
2. **`on=[("col1", "col2"), ...]`** - List of (base_col, join_col) pairs
3. **`on="raw sql"`** - Raw ON clause (escape hatch, no validation)

### Build Method
```python
.build() -> tuple[str, list]
```
- Validates all columns against TABLES
- Returns `(sql_string, params_list)`
- **PARAMETER ORDER**: CTE params FIRST, then main query params (in order of `.where()` calls)
- Raises `ValueError` on validation failure with full context

### Escape Hatch
```python
Q.raw(sql: str, params: list = None) -> tuple[str, list]
```
- Bypasses all validation
- Logs warning for audit trail
- Use only when Q cannot express the query

---

## CTE Parameter Ordering (CRITICAL)

When using CTEs, parameters are collected in this order:

```python
# CTE subquery with its own params
tainted = Q("assignments") \
    .select("file", "target_var") \
    .where("source_expr LIKE ?", "%request%")  # param1: "%request%"

# Main query with CTE
rows = db.query(
    Q("function_call_args")
    .with_cte("tainted_vars", tainted)
    .select("f.file", "f.line", "t.target_var")
    .join("tainted_vars", on=[("file", "file")])
    .where("f.callee_function LIKE ?", "%execute%")  # param2: "%execute%"
)

# PARAMETER ORDER: CTE params FIRST, then main params
# Final params list: ["%request%", "%execute%"]
#
# Generated SQL:
# WITH tainted_vars AS (
#     SELECT file, target_var FROM assignments WHERE source_expr LIKE ?
# )
# SELECT f.file, f.line, t.target_var
# FROM function_call_args f
# INNER JOIN tainted_vars t ON f.file = t.file
# WHERE f.callee_function LIKE ?
```

**Multiple CTEs:**
```python
cte1 = Q("table1").where("x = ?", "a")  # param1
cte2 = Q("table2").where("y = ?", "b")  # param2

Q("main")
    .with_cte("cte1", cte1)
    .with_cte("cte2", cte2)
    .where("z = ?", "c")  # param3
    .build()

# Final params: ["a", "b", "c"] - CTEs in order added, then main
```

---

## File Inventory (95 Rule Files)

All paths relative to `theauditor/rules/`:

```
01. auth/jwt_analyze.py
02. auth/oauth_analyze.py
03. auth/password_analyze.py
04. auth/session_analyze.py
05. bash/dangerous_patterns_analyze.py
06. bash/injection_analyze.py
07. bash/quoting_analyze.py
08. build/bundle_analyze.py
09. dependency/bundle_size.py
10. dependency/dependency_bloat.py
11. dependency/ghost_dependencies.py
12. dependency/peer_conflicts.py
13. dependency/suspicious_versions.py
14. dependency/typosquatting.py
15. dependency/unused_dependencies.py
16. dependency/update_lag.py
17. dependency/version_pinning.py
18. deployment/aws_cdk_encryption_analyze.py
19. deployment/aws_cdk_iam_wildcards_analyze.py
20. deployment/aws_cdk_s3_public_analyze.py
21. deployment/aws_cdk_sg_open_analyze.py
22. deployment/compose_analyze.py
23. deployment/docker_analyze.py
24. deployment/nginx_analyze.py
25. frameworks/express_analyze.py
26. frameworks/fastapi_analyze.py
27. frameworks/flask_analyze.py
28. frameworks/nextjs_analyze.py
29. frameworks/react_analyze.py
30. frameworks/vue_analyze.py
31. github_actions/artifact_poisoning.py
32. github_actions/excessive_permissions.py
33. github_actions/reusable_workflow_risks.py
34. github_actions/script_injection.py
35. github_actions/unpinned_actions.py
36. github_actions/untrusted_checkout.py
37. go/concurrency_analyze.py
38. go/crypto_analyze.py
39. go/error_handling_analyze.py
40. go/injection_analyze.py
41. graphql/injection.py
42. graphql/input_validation.py
43. graphql/mutation_auth.py
44. graphql/nplus1.py
45. graphql/overfetch.py
46. graphql/query_depth.py
47. graphql/sensitive_fields.py
48. logic/general_logic_analyze.py
49. node/async_concurrency_analyze.py
50. node/runtime_issue_analyze.py
51. orm/prisma_analyze.py
52. orm/sequelize_analyze.py
53. orm/typeorm_analyze.py
54. performance/perf_analyze.py
55. python/async_concurrency_analyze.py
56. python/python_crypto_analyze.py
57. python/python_deserialization_analyze.py
58. python/python_globals_analyze.py
59. python/python_injection_analyze.py
60. quality/deadcode_analyze.py
61. react/component_analyze.py
62. react/hooks_analyze.py
63. react/render_analyze.py
64. react/state_analyze.py
65. rust/ffi_boundary.py
66. rust/integer_safety.py
67. rust/memory_safety.py
68. rust/panic_paths.py
69. rust/unsafe_analysis.py
70. secrets/hardcoded_secret_analyze.py
71. security/api_auth_analyze.py
72. security/cors_analyze.py
73. security/crypto_analyze.py
74. security/input_validation_analyze.py
75. security/pii_analyze.py
76. security/rate_limit_analyze.py
77. security/sourcemap_analyze.py
78. security/websocket_analyze.py
79. sql/multi_tenant_analyze.py
80. sql/sql_injection_analyze.py
81. sql/sql_safety_analyze.py
82. terraform/terraform_analyze.py
83. typescript/type_safety_analyze.py
84. vue/component_analyze.py
85. vue/hooks_analyze.py
86. vue/lifecycle_analyze.py
87. vue/reactivity_analyze.py
88. vue/render_analyze.py
89. vue/state_analyze.py
90. xss/dom_xss_analyze.py
91. xss/express_xss_analyze.py
92. xss/react_xss_analyze.py
93. xss/template_xss_analyze.py
94. xss/vue_xss_analyze.py
95. xss/xss_analyze.py
```

---

## Terminal Assignments

### FOUNDATION (Must Complete Before Waves)

**Terminal 0: Infrastructure Build**

Files to create/modify:
- CREATE: `theauditor/rules/query.py` - Q class implementation
- CREATE: `theauditor/rules/fidelity.py` - RuleResult, RuleDB, RuleManifest, verify_fidelity
- MODIFY: `theauditor/rules/base.py` - Add RuleResult re-export
- MODIFY: `theauditor/rules/orchestrator.py` - Handle RuleResult, add fidelity verification
- MODIFY: `theauditor/rules/__init__.py` - Export new symbols

Validation:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.query import Q
from theauditor.rules.fidelity import RuleResult, RuleDB
print('Infrastructure imports OK')
"
```

---

### WAVE 1: Files 1-50 (5 files per terminal)

| Terminal | Files | Category Focus |
|----------|-------|----------------|
| T1 | 01-05 | auth/*, bash/dangerous |
| T2 | 06-10 | bash/*, build/*, dependency/bundle* |
| T3 | 11-15 | dependency/* (middle) |
| T4 | 16-20 | dependency/*, deployment/aws_cdk/* |
| T5 | 21-25 | deployment/*, frameworks/express |
| T6 | 26-30 | frameworks/* (all) |
| T7 | 31-35 | github_actions/* (first 5) |
| T8 | 36-40 | github_actions/untrusted, go/* |
| T9 | 41-45 | graphql/* (first 5) |
| T10 | 46-50 | graphql/*, logic/*, node/* |

---

### WAVE 2: Files 51-95 (4-5 files per terminal)

| Terminal | Files | Category Focus |
|----------|-------|----------------|
| T1 | 51-55 | orm/*, performance/*, python/async |
| T2 | 56-60 | python/*, quality/* |
| T3 | 61-65 | react/*, rust/ffi |
| T4 | 66-70 | rust/*, secrets/* |
| T5 | 71-75 | security/* (first 5) |
| T6 | 76-80 | security/*, sql/* (first 2) |
| T7 | 81-85 | sql/sql_safety, terraform/*, typescript/*, vue/* (first 2) |
| T8 | 86-90 | vue/* (remaining), xss/dom |
| T9 | 91-95 | xss/* (remaining) |
| T10 | -- | Integration validation, final cleanup, orchestrator test |

---

## Migration Pattern (MANDATORY FOR ALL TERMINALS)

### Step 1: Read File FULLY

Read the entire file. No skipping. Understand:
- What tables it queries
- What SQL patterns it uses
- What issues exist

### Step 2: Identify Issues

Look for these CLAUDE.md violations:

1. **ZERO FALLBACK violations** - Any `if not result: try_alternative()` pattern
2. **Raw SQL hardcoding** - `cursor.execute("SELECT ...")` without Q class
3. **Missing METADATA** - Rules should have `METADATA = RuleMetadata(...)`
4. **Emoji in strings** - Will crash on Windows CP1252
5. **Table existence checks** - `if 'table' in existing_tables`
6. **Try-except fallbacks** - `except: use_alternative()`

### Step 3: Convert to Q Class

**BEFORE:**
```python
cursor.execute("""
    SELECT file, line, callee_function
    FROM function_call_args
    WHERE callee_function LIKE '%execute%'
    ORDER BY file, line
""")
```

**AFTER:**
```python
from theauditor.rules.query import Q
from theauditor.rules.fidelity import RuleDB, RuleResult

def analyze(context: StandardRuleContext) -> RuleResult:
    with RuleDB(context.db_path, "rule_name") as db:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function")
            .where("callee_function LIKE ?", "%execute%")
            .order_by("file, line")
        )

        findings = []
        for file, line, func in rows:
            # ... process

        return RuleResult(findings=findings, manifest=db.get_manifest())
```

### Step 4: Handle Complex Cases

**For CTEs (like sql_injection_analyze.py:164-180):**
```python
# Build CTE subquery
tainted = Q("assignments") \
    .select("file", "target_var", "source_expr") \
    .where("source_expr LIKE ? OR source_expr LIKE ?", "%request.%", "%req.%")

# Main query with CTE
rows = db.query(
    Q("function_call_args")
    .with_cte("tainted_vars", tainted)
    .select("f.file", "f.line", "f.callee_function", "t.target_var")
    .join("tainted_vars", on=[("file", "file")])
    .where("f.callee_function LIKE ?", "%execute%")
)
```

**For truly complex SQL that Q can't express:**
```python
# Escape hatch - logs warning for audit
sql, params = Q.raw("""
    SELECT ... complex vendor-specific SQL ...
""", [param1, param2])
rows = db.execute(sql, params)
```

### Step 5: Validate

After modifying each file:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import theauditor.rules.{module_path}
print('Import OK: {module_path}')
"
```

---

## Common Issues to Fix

### Issue 1: Missing METADATA

```python
# ADD if missing:
METADATA = RuleMetadata(
    name="rule_name",
    category="category",
    target_extensions=[".py", ".js"],
    exclude_patterns=["test/", "node_modules/"],
    requires_jsx_pass=False,
    execution_scope="database",
)
```

### Issue 2: Bare List Return

```python
# BEFORE:
def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    findings = []
    # ...
    return findings

# AFTER:
def analyze(context: StandardRuleContext) -> RuleResult:
    with RuleDB(context.db_path, "rule_name") as db:
        findings = []
        # ...
        return RuleResult(findings=findings, manifest=db.get_manifest())
```

### Issue 3: Raw cursor.execute()

Replace ALL `cursor.execute()` calls with either:
- `db.query(Q(...))` for SELECT queries
- `db.execute(sql, params)` for edge cases (with Q.raw() for logging)

### Issue 4: Connection Management

```python
# BEFORE:
conn = sqlite3.connect(context.db_path)
cursor = conn.cursor()
try:
    # ...
finally:
    conn.close()

# AFTER:
with RuleDB(context.db_path, "rule_name") as db:
    # RuleDB handles connection lifecycle
```

---

## Validation Checklist (Per File)

Each terminal must verify for EACH file:

- [ ] File imports `from theauditor.rules.query import Q`
- [ ] File imports `from theauditor.rules.fidelity import RuleDB, RuleResult`
- [ ] Main function returns `RuleResult` (not bare list)
- [ ] All SQL uses Q class (or Q.raw() with justification)
- [ ] No raw `cursor.execute()` with hardcoded SQL
- [ ] No CLAUDE.md violations
- [ ] File passes import test
- [ ] METADATA present and complete

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Q class missing feature | Rules can't migrate | Q.raw() escape hatch |
| Parallel edit conflicts | Corrupted files | Strict file partitioning |
| Silent breakage | Rules don't run | Import validation per file |
| Performance regression | Slow scans | Benchmark before/after |

---

## Coordination

1. **Before Wave 1**: All terminals MUST wait for Foundation to complete
2. **Between Waves**: Quick sync to identify blockers
3. **After Wave 2**: Terminal 10 runs integration validation

---

## Files NOT to Modify

These are infrastructure, not rules:
- `base.py` (modified by Foundation only)
- `orchestrator.py` (modified by Foundation only)
- `__init__.py` files (only if needed for exports)
- `TEMPLATE_*.py` (templates, not active rules)
- `common/util.py` (utilities)
- `xss/constants.py` (constants)
- `dependency/config.py` (configuration)
