# Tasks: Migrate Rules to Fidelity Layer (Phase 2)

## CRITICAL READS BEFORE ANY WORK

Every terminal MUST read these files first:
1. `CLAUDE.md` - ALL sections, especially ZERO FALLBACK
2. `theauditor/rules/base.py` - Understand StandardFinding, StandardRuleContext, RuleMetadata
3. `theauditor/indexer/schema.py` - Understand TABLES dict
4. This file's "Common Patterns" section
5. `design.md` in this directory - Schema Reference and Q Class API are embedded there

---

## RuleMetadata Definition (EMBEDDED - Do NOT Hunt)

Location: `theauditor/rules/base.py:145-159`

```python
from theauditor.rules.base import RuleMetadata

@dataclass
class RuleMetadata:
    """Metadata describing rule requirements for smart orchestrator filtering."""

    name: str                                           # Unique rule identifier
    category: str                                       # Grouping category

    target_extensions: list[str] | None = None          # File extensions to analyze
    exclude_patterns: list[str] | None = None           # Patterns to skip
    target_file_patterns: list[str] | None = None       # Specific file patterns

    execution_scope: Literal["database", "file"] | None = None  # "database" or "file"

    requires_jsx_pass: bool = False                     # JSX extraction required?
    jsx_pass_mode: str = "preserved"                    # JSX mode
```

**Usage in rules:**
```python
METADATA = RuleMetadata(
    name="sql_injection",
    category="security",
    target_extensions=[".py", ".js", ".ts"],
    exclude_patterns=["test/", "node_modules/", "migration/"],
    requires_jsx_pass=False,
    execution_scope="database",
)
```

---

## PHASE 0: FOUNDATION (Blocking - VERIFY Phase 1 Complete)

**Assigned to: Terminal 0 (Orchestrator/Lead)**

**NOTE:** Phase 0 is VERIFICATION that Phase 1 (`add-rules-data-fidelity`) is complete.
If files don't exist, complete Phase 1 first. Do NOT start Wave 1 until Phase 0 passes.

### 0.1 Verify Query Builder Exists

Location: `theauditor/rules/query.py` (should exist from Phase 1)

- [ ] 0.1.1 VERIFY file exists: `ls theauditor/rules/query.py`
- [ ] 0.1.2 VERIFY Q class has `.select()` method
- [ ] 0.1.3 VERIFY Q class has `.where()` method
- [ ] 0.1.4 VERIFY Q class has `.join()` method with FK auto-detect
- [ ] 0.1.5 VERIFY Q class has `.with_cte()` method for CTE support
- [ ] 0.1.6 VERIFY Q class has `.order_by()` method
- [ ] 0.1.7 VERIFY Q class has `.limit()` method
- [ ] 0.1.8 VERIFY Q class has `.group_by()` method
- [ ] 0.1.9 VERIFY Q class has `.build()` method returning (sql, params)
- [ ] 0.1.10 VERIFY `Q.raw()` escape hatch exists

**If any VERIFY fails:** Complete Phase 1 tasks for that item first.

### 0.2 Verify Fidelity Infrastructure Exists

Location: `theauditor/rules/fidelity.py` (should exist from Phase 1)

- [ ] 0.2.1 VERIFY file exists: `ls theauditor/rules/fidelity.py`
- [ ] 0.2.2 VERIFY `RuleResult` dataclass exists (findings + manifest)
- [ ] 0.2.3 VERIFY `RuleManifest` class exists
- [ ] 0.2.4 VERIFY `RuleDB` class exists with `query()` and `execute()` methods
- [ ] 0.2.5 VERIFY `FidelityError` exception class exists
- [ ] 0.2.6 VERIFY `verify_fidelity()` function exists

**If any VERIFY fails:** Complete Phase 1 tasks for that item first.

### 0.3 Verify Base Module Updated

Location: `theauditor/rules/base.py:132` (RuleFunction type hint)

- [ ] 0.3.1 VERIFY `RuleResult` is imported from fidelity
- [ ] 0.3.2 VERIFY `RuleResult` in exports (if `__all__` exists)
- [ ] 0.3.3 VERIFY `RuleFunction` type hint allows `RuleResult` return

### 0.4 Verify Orchestrator Updated

Location: `theauditor/rules/orchestrator.py`

**Hook Points (VERIFIED 2024-12-04):**
- `RulesOrchestrator.__init__`: line 57
- `_execute_rule()` method: lines 483-499
- Rule function call: line 490 (`findings = rule.function(std_context)`)

- [ ] 0.4.1 VERIFY `RuleResult` import exists at top of file
- [ ] 0.4.2 VERIFY `_fidelity_failures` list in `__init__` (around line 68)
- [ ] 0.4.3 VERIFY `_execute_rule()` at line 483-499 handles `RuleResult` return type
- [ ] 0.4.4 VERIFY `_compute_expected()` method exists
- [ ] 0.4.5 VERIFY `get_aggregated_manifests()` method exists

**If any VERIFY fails:** Complete Phase 1 orchestrator integration first.

### 0.5 Validate Foundation (All Phase 1 Complete)

- [ ] 0.5.1 Run import validation:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.query import Q
from theauditor.rules.fidelity import RuleResult, RuleDB, RuleManifest
from theauditor.rules.base import RuleResult as BaseRuleResult
print('Foundation OK')
"
```
- [ ] 0.5.2 Test Q class against live database:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.query import Q
sql, params = Q('symbols').select('name', 'line').where('type = ?', 'function').limit(3).build()
print(f'SQL: {sql}')
print(f'Params: {params}')
"
```

---

## WAVE 1: Files 1-50

### Terminal 1: Files 01-05

**Files:**
```
theauditor/rules/auth/jwt_analyze.py
theauditor/rules/auth/oauth_analyze.py
theauditor/rules/auth/password_analyze.py
theauditor/rules/auth/session_analyze.py
theauditor/rules/bash/dangerous_patterns_analyze.py
```

Tasks per file:
- [ ] T1.01 jwt_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.02 oauth_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.03 password_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.04 session_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.05 dangerous_patterns_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.V1 Validate all 5 files import correctly

---

### Terminal 2: Files 06-10

**Files:**
```
theauditor/rules/bash/injection_analyze.py
theauditor/rules/bash/quoting_analyze.py
theauditor/rules/build/bundle_analyze.py
theauditor/rules/dependency/bundle_size.py
theauditor/rules/dependency/dependency_bloat.py
```

Tasks per file:
- [ ] T2.01 injection_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.02 quoting_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.03 bundle_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.04 bundle_size.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.05 dependency_bloat.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.V1 Validate all 5 files import correctly

---

### Terminal 3: Files 11-15

**Files:**
```
theauditor/rules/dependency/ghost_dependencies.py
theauditor/rules/dependency/peer_conflicts.py
theauditor/rules/dependency/suspicious_versions.py
theauditor/rules/dependency/typosquatting.py
theauditor/rules/dependency/unused_dependencies.py
```

Tasks per file:
- [ ] T3.01 ghost_dependencies.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.02 peer_conflicts.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.03 suspicious_versions.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.04 typosquatting.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.05 unused_dependencies.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.V1 Validate all 5 files import correctly

---

### Terminal 4: Files 16-20

**Files:**
```
theauditor/rules/dependency/update_lag.py
theauditor/rules/dependency/version_pinning.py
theauditor/rules/deployment/aws_cdk_encryption_analyze.py
theauditor/rules/deployment/aws_cdk_iam_wildcards_analyze.py
theauditor/rules/deployment/aws_cdk_s3_public_analyze.py
```

Tasks per file:
- [ ] T4.01 update_lag.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.02 version_pinning.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.03 aws_cdk_encryption_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.04 aws_cdk_iam_wildcards_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.05 aws_cdk_s3_public_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.V1 Validate all 5 files import correctly

---

### Terminal 5: Files 21-25

**Files:**
```
theauditor/rules/deployment/aws_cdk_sg_open_analyze.py
theauditor/rules/deployment/compose_analyze.py
theauditor/rules/deployment/docker_analyze.py
theauditor/rules/deployment/nginx_analyze.py
theauditor/rules/frameworks/express_analyze.py
```

Tasks per file:
- [ ] T5.01 aws_cdk_sg_open_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.02 compose_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.03 docker_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.04 nginx_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.05 express_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.V1 Validate all 5 files import correctly

---

### Terminal 6: Files 26-30

**Files:**
```
theauditor/rules/frameworks/fastapi_analyze.py
theauditor/rules/frameworks/flask_analyze.py
theauditor/rules/frameworks/nextjs_analyze.py
theauditor/rules/frameworks/react_analyze.py
theauditor/rules/frameworks/vue_analyze.py
```

Tasks per file:
- [ ] T6.01 fastapi_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.02 flask_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.03 nextjs_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.04 react_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.05 vue_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.V1 Validate all 5 files import correctly

---

### Terminal 7: Files 31-35

**Files:**
```
theauditor/rules/github_actions/artifact_poisoning.py
theauditor/rules/github_actions/excessive_permissions.py
theauditor/rules/github_actions/reusable_workflow_risks.py
theauditor/rules/github_actions/script_injection.py
theauditor/rules/github_actions/unpinned_actions.py
```

Tasks per file:
- [ ] T7.01 artifact_poisoning.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.02 excessive_permissions.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.03 reusable_workflow_risks.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.04 script_injection.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.05 unpinned_actions.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.V1 Validate all 5 files import correctly

---

### Terminal 8: Files 36-40

**Files:**
```
theauditor/rules/github_actions/untrusted_checkout.py
theauditor/rules/go/concurrency_analyze.py
theauditor/rules/go/crypto_analyze.py
theauditor/rules/go/error_handling_analyze.py
theauditor/rules/go/injection_analyze.py
```

Tasks per file:
- [ ] T8.01 untrusted_checkout.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.02 concurrency_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.03 crypto_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.04 error_handling_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.05 injection_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.V1 Validate all 5 files import correctly

---

### Terminal 9: Files 41-45

**Files:**
```
theauditor/rules/graphql/injection.py
theauditor/rules/graphql/input_validation.py
theauditor/rules/graphql/mutation_auth.py
theauditor/rules/graphql/nplus1.py
theauditor/rules/graphql/overfetch.py
```

Tasks per file:
- [ ] T9.01 injection.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.02 input_validation.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.03 mutation_auth.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.04 nplus1.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.05 overfetch.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.V1 Validate all 5 files import correctly

---

### Terminal 10: Files 46-50

**Files:**
```
theauditor/rules/graphql/query_depth.py
theauditor/rules/graphql/sensitive_fields.py
theauditor/rules/logic/general_logic_analyze.py
theauditor/rules/node/async_concurrency_analyze.py
theauditor/rules/node/runtime_issue_analyze.py
```

Tasks per file:
- [ ] T10.01 query_depth.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T10.02 sensitive_fields.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T10.03 general_logic_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T10.04 async_concurrency_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T10.05 runtime_issue_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T10.V1 Validate all 5 files import correctly

---

## WAVE 1 CHECKPOINT

Before proceeding to Wave 2:
- [ ] All 50 files pass import validation
- [ ] Run: `aud full --offline` on test repo - no crashes
- [ ] Quick sync meeting to identify any blockers

---

## WAVE 2: Files 51-95

### Terminal 1: Files 51-55

**Files:**
```
theauditor/rules/orm/prisma_analyze.py
theauditor/rules/orm/sequelize_analyze.py
theauditor/rules/orm/typeorm_analyze.py
theauditor/rules/performance/perf_analyze.py
theauditor/rules/python/async_concurrency_analyze.py
```

Tasks per file:
- [ ] T1.51 prisma_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.52 sequelize_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.53 typeorm_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.54 perf_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.55 async_concurrency_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T1.V2 Validate all 5 files import correctly

---

### Terminal 2: Files 56-60

**Files:**
```
theauditor/rules/python/python_crypto_analyze.py
theauditor/rules/python/python_deserialization_analyze.py
theauditor/rules/python/python_globals_analyze.py
theauditor/rules/python/python_injection_analyze.py
theauditor/rules/quality/deadcode_analyze.py
```

Tasks per file:
- [ ] T2.56 python_crypto_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.57 python_deserialization_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.58 python_globals_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.59 python_injection_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.60 deadcode_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T2.V2 Validate all 5 files import correctly

---

### Terminal 3: Files 61-65

**Files:**
```
theauditor/rules/react/component_analyze.py
theauditor/rules/react/hooks_analyze.py
theauditor/rules/react/render_analyze.py
theauditor/rules/react/state_analyze.py
theauditor/rules/rust/ffi_boundary.py
```

Tasks per file:
- [ ] T3.61 component_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.62 hooks_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.63 render_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.64 state_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.65 ffi_boundary.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T3.V2 Validate all 5 files import correctly

---

### Terminal 4: Files 66-70

**Files:**
```
theauditor/rules/rust/integer_safety.py
theauditor/rules/rust/memory_safety.py
theauditor/rules/rust/panic_paths.py
theauditor/rules/rust/unsafe_analysis.py
theauditor/rules/secrets/hardcoded_secret_analyze.py
```

Tasks per file:
- [ ] T4.66 integer_safety.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.67 memory_safety.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.68 panic_paths.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.69 unsafe_analysis.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.70 hardcoded_secret_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T4.V2 Validate all 5 files import correctly

---

### Terminal 5: Files 71-75

**Files:**
```
theauditor/rules/security/api_auth_analyze.py
theauditor/rules/security/cors_analyze.py
theauditor/rules/security/crypto_analyze.py
theauditor/rules/security/input_validation_analyze.py
theauditor/rules/security/pii_analyze.py
```

Tasks per file:
- [ ] T5.71 api_auth_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.72 cors_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.73 crypto_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.74 input_validation_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.75 pii_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T5.V2 Validate all 5 files import correctly

---

### Terminal 6: Files 76-80

**Files:**
```
theauditor/rules/security/rate_limit_analyze.py
theauditor/rules/security/sourcemap_analyze.py
theauditor/rules/security/websocket_analyze.py
theauditor/rules/sql/multi_tenant_analyze.py
theauditor/rules/sql/sql_injection_analyze.py
```

**SPECIAL NOTE:** `sql_injection_analyze.py` has CTEs - requires Q.with_cte() usage.

Tasks per file:
- [ ] T6.76 rate_limit_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.77 sourcemap_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.78 websocket_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.79 multi_tenant_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T6.80 sql_injection_analyze.py - Read, identify issues, convert CTEs to Q.with_cte(), return RuleResult
- [ ] T6.V2 Validate all 5 files import correctly

---

### Terminal 7: Files 81-85

**Files:**
```
theauditor/rules/sql/sql_safety_analyze.py
theauditor/rules/terraform/terraform_analyze.py
theauditor/rules/typescript/type_safety_analyze.py
theauditor/rules/vue/component_analyze.py
theauditor/rules/vue/hooks_analyze.py
```

Tasks per file:
- [ ] T7.81 sql_safety_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.82 terraform_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.83 type_safety_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.84 component_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.85 hooks_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T7.V2 Validate all 5 files import correctly

---

### Terminal 8: Files 86-90

**Files:**
```
theauditor/rules/vue/lifecycle_analyze.py
theauditor/rules/vue/reactivity_analyze.py
theauditor/rules/vue/render_analyze.py
theauditor/rules/vue/state_analyze.py
theauditor/rules/xss/dom_xss_analyze.py
```

Tasks per file:
- [ ] T8.86 lifecycle_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.87 reactivity_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.88 render_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.89 state_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.90 dom_xss_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T8.V2 Validate all 5 files import correctly

---

### Terminal 9: Files 91-95

**Files:**
```
theauditor/rules/xss/express_xss_analyze.py
theauditor/rules/xss/react_xss_analyze.py
theauditor/rules/xss/template_xss_analyze.py
theauditor/rules/xss/vue_xss_analyze.py
theauditor/rules/xss/xss_analyze.py
```

Tasks per file:
- [ ] T9.91 express_xss_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.92 react_xss_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.93 template_xss_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.94 vue_xss_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.95 xss_analyze.py - Read, identify issues, convert to Q/RuleDB, return RuleResult
- [ ] T9.V2 Validate all 5 files import correctly

---

### Terminal 10: Integration & Validation

No file assignments in Wave 2. Focus on:

- [ ] T10.INT1 Run full import validation for all 95 files
- [ ] T10.INT2 Run `aud full --offline` on TheAuditor itself
- [ ] T10.INT3 Run `aud full --offline` on test repository
- [ ] T10.INT4 Verify fidelity manifests are generated
- [ ] T10.INT5 Check for any remaining raw `cursor.execute()` calls
- [ ] T10.INT6 Generate migration completion report

---

## FINAL VALIDATION

After all waves complete:

```bash
# 1. Full import test
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import importlib
import os

rules_dir = 'theauditor/rules'
failed = []

for root, dirs, files in os.walk(rules_dir):
    dirs[:] = [d for d in dirs if not d.startswith('__')]
    for f in files:
        if f.endswith('.py') and not f.startswith('__') and not f.startswith('TEMPLATE'):
            module_path = os.path.join(root, f).replace('/', '.').replace('\\\\', '.')[:-3]
            try:
                importlib.import_module(module_path)
            except Exception as e:
                failed.append((module_path, str(e)))

if failed:
    print(f'FAILED: {len(failed)} modules')
    for m, e in failed:
        print(f'  {m}: {e}')
else:
    print('ALL IMPORTS OK')
"

# 2. Run full pipeline
aud full --offline

# 3. Check for remaining raw SQL
grep -r "cursor.execute" theauditor/rules --include="*.py" | grep -v "Q.raw" | grep -v "__pycache__"
```

---

## COMMON PATTERNS (REFERENCE)

### Pattern A: Simple Single Table Query

```python
# BEFORE
query = build_query("symbols", ["name", "path", "line"], where="type = 'function'")
cursor.execute(query)
rows = cursor.fetchall()

# AFTER
rows = db.query(
    Q("symbols")
    .select("name", "path", "line")
    .where("type = ?", "function")
)
```

### Pattern B: Two-Table JOIN

```python
# BEFORE
cursor.execute("""
    SELECT a.file, a.line, b.name
    FROM function_call_args a
    JOIN symbols b ON a.callee_function = b.name
    WHERE a.file LIKE '%test%'
""")

# AFTER
rows = db.query(
    Q("function_call_args")
    .select("a.file", "a.line", "b.name")
    .join("symbols", on=[("callee_function", "name")])
    .where("a.file LIKE ?", "%test%")
)
```

### Pattern C: CTE Query

```python
# BEFORE
cursor.execute("""
    WITH tainted_vars AS (
        SELECT file, target_var FROM assignments
        WHERE source_expr LIKE '%request%'
    )
    SELECT f.file, f.line, t.target_var
    FROM function_call_args f
    JOIN tainted_vars t ON f.file = t.file
""")

# AFTER
tainted = Q("assignments") \
    .select("file", "target_var") \
    .where("source_expr LIKE ?", "%request%")

rows = db.query(
    Q("function_call_args")
    .with_cte("tainted_vars", tainted)
    .select("f.file", "f.line", "t.target_var")
    .join("tainted_vars", on=[("file", "file")])
)
```

### Pattern D: Escape Hatch (Complex SQL)

```python
# For truly complex SQL that Q cannot express
sql, params = Q.raw("""
    SELECT ... complex vendor-specific SQL with window functions ...
""", [param1, param2])
rows = db.execute(sql, params)
```

### Pattern E: Full Rule Migration Template

```python
"""Rule description."""

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext
from theauditor.rules.query import Q
from theauditor.rules.fidelity import RuleDB, RuleResult

METADATA = RuleMetadata(
    name="rule_name",
    category="category",
    target_extensions=[".py", ".js"],
    exclude_patterns=["test/", "node_modules/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Main analysis function."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        # Query using Q class
        rows = db.query(
            Q("table_name")
            .select("col1", "col2")
            .where("condition = ?", "value")
        )

        for col1, col2 in rows:
            # Process and create findings
            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message="Description",
                    file_path=col1,
                    line=col2,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    snippet="relevant code",
                    cwe_id="CWE-XXX",
                )
            )

        return RuleResult(findings=findings, manifest=db.get_manifest())
```
