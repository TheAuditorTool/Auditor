# TheAuditor Rules Orchestrator

## Overview

A **unified, dynamically-discovered security rules system** with:
- **25 categories**
- **107 rule files**
- **113+ rule functions**

Uses an innovative orchestrator that dynamically discovers rules by scanning for `analyze` and `find_*` functions.

---

## Dynamic Rule Discovery

```python
def _discover_all_rules(self) -> dict[str, list[RuleInfo]]:
    for subdir in rules_dir.iterdir():
        for py_file in subdir.glob("*.py"):
            module = importlib.import_module(module_name)

            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("find_") or name == "analyze":
                    rule_info = self._analyze_rule(name, obj, ...)
```

**Discovery criteria:**
- Functions named `analyze` or `find_*`
- Defined in the module (not imported)
- Metadata captured from `METADATA` object

---

## All 25 Rule Categories

| Category | Files | Primary Focus |
|----------|-------|---------------|
| **dependency** | 10 | Package bloat, ghost deps, version lag |
| **github_actions** | 8 | Workflow risks, untrusted checkout |
| **security** | 8 | CORS, crypto, input validation, PII |
| **deployment** | 7 | AWS CDK, IAM wildcards, security groups |
| **graphql** | 7 | Query depth, N+1, overfetch, injection |
| **xss** | 7 | Template injection, unsafe escaping |
| **frameworks** | 6 | Express, FastAPI, Flask, Next.js, React |
| **rust** | 6 | Memory safety, unsafe blocks, panic |
| **vue** | 6 | Lifecycle hooks, state management |
| **python** | 5 | Deserialization, crypto, injection |
| **auth** | 4 | JWT, OAuth, password, session |
| **go** | 4 | Concurrency, crypto, error handling |
| **react** | 4 | Hooks, component lifecycle, state |
| **sql** | 4 | SQL injection, ORM raw queries |
| **bash** | 3 | Dangerous patterns, injection, quoting |
| **orm** | 3 | Sequelize, TypeORM vulnerabilities |
| + 9 more... | | |

---

## Rule Architecture

### RuleInfo Dataclass
```python
@dataclass
class RuleInfo:
    name: str                   # Function name
    module: str                 # Full module path
    function: Callable          # Actual function
    category: str               # Category folder

    requires_ast: bool          # Needs AST tree?
    requires_db: bool           # Needs database?
    requires_file: bool         # Needs file path?
    requires_content: bool      # Needs file content?

    rule_type: str              # standalone | discovery | taint-dependent
    execution_scope: str        # database | file
```

### Rule Types

1. **Standalone Rules** - No dependencies, execute independently
2. **Discovery Rules** - Populate taint registry with sources/sinks
3. **Taint-Dependent Rules** - Query taint analysis results

---

## Standardized Rule Context

```python
@dataclass
class StandardRuleContext:
    file_path: Path
    content: str
    language: str
    project_path: Path
    ast_wrapper: dict | None
    db_path: str | None
    taint_checker: Callable | None
```

### Standardized Finding
```python
@dataclass
class StandardFinding:
    rule_name: str              # Identifier (kebab-case)
    message: str                # Human-readable
    file_path: str
    line: int
    severity: Severity          # CRITICAL | HIGH | MEDIUM | LOW | INFO
    confidence: Confidence      # HIGH | MEDIUM | LOW
    cwe_id: str | None          # CWE-123 format
```

---

## Query System: The Q Class

Type-safe, composable database queries:

```python
from theauditor.rules.query import Q

rows = db.query(
    Q("function_call_args")
    .select("file", "line", "callee_function")
    .where("callee_function IN (?)", "eval", "exec")
    .where("file NOT LIKE ?", "%test%")
    .order_by("file, line")
)
```

**Benefits:**
- Column validation against schema at build time
- Foreign key auto-detection
- Parameterized queries (no SQL injection)

---

## Fidelity Verification

Rules return `RuleResult` with findings AND manifest:

```python
@dataclass
class RuleResult:
    findings: list[StandardFinding]
    manifest: dict  # {items_scanned, tables_queried, queries_executed}
```

**Purpose**: Catch "silent failures" where a rule scans nothing but reports no findings.

---

## Example Rule: CORS Analyzer

```python
def analyze(context: StandardRuleContext) -> RuleResult:
    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []
        findings.extend(_check_wildcard_with_credentials(db))
        findings.extend(_check_origin_reflection(db))
        findings.extend(_check_regex_vulnerabilities(db))
        # ... 15+ specialized checks
        return RuleResult(findings=findings, manifest=db.get_manifest())
```

---

## Rule Execution Pipeline

```python
# Phase 1: Discovery rules populate taint registry
registry = TaintRegistry()
orchestrator.run_discovery_rules(registry)

# Phase 2: Standalone rules (database scope)
all_findings.extend(orchestrator.run_standalone_rules())

# Phase 3: Taint analysis
taint_checker = orchestrator._create_taint_checker(context)

# Phase 4: Taint-dependent rules
all_findings.extend(orchestrator.run_taint_dependent_rules(taint_checker))
```
