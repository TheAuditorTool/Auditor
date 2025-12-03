# Design: FCE Vector-Based Consensus Engine

## Requirements

- **Python**: >= 3.10 (for `X | None` union syntax)
- **Pydantic**: >= 2.0 (for `model_dump_json()` method)

## Context

The FCE is TheAuditor's correlation engine - it identifies WHERE multiple independent analysis vectors converge to highlight areas that deserve attention. Current implementation is a 1500-line monolith that:

1. Loads ALL findings into memory (RAM hog)
2. Uses hardcoded magic numbers (`if complexity <= 20:`)
3. Mixes data collection with risk judgment
4. Doesn't follow existing patterns (`CodeQueryEngine`)

The rewrite transforms it from a "Risk Calculator" to a "Consensus Aggregator" that follows the proven `aud explain` architecture pattern.

## Goals / Non-Goals

**Goals:**
- Follow `CodeQueryEngine` pattern from `aud explain`
- Vector-based Signal Density (Static, Flow, Process, Structural)
- Semantic Table Registry for 226 tables
- Service API for `--fce` flags on other commands
- Zero hardcoded thresholds
- Pure fact reporting

**Non-Goals:**
- Adding new analysis tools
- Changing database schemas
- Async/parallel execution (keep it simple)
- Collector abstraction layers (over-engineering)
- Building a frontend/UI

## Architecture Decisions

### Decision 1: Follow CodeQueryEngine Pattern

**Reference Implementation**: `theauditor/context/query.py:73-95`

```python
# From theauditor/context/query.py:73-95
class CodeQueryEngine:
    """Query engine for code navigation."""

    def __init__(self, root: Path):
        """Initialize with project root."""
        self.root = root
        pf_dir = root / ".pf"

        repo_db_path = pf_dir / "repo_index.db"
        if not repo_db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {repo_db_path}\nRun 'aud full' first to build the database."
            )

        self.repo_db = sqlite3.connect(str(repo_db_path))
        self.repo_db.row_factory = sqlite3.Row

        graph_db_path = pf_dir / "graphs.db"
        if graph_db_path.exists():
            self.graph_db = sqlite3.connect(str(graph_db_path))
            self.graph_db.row_factory = sqlite3.Row
        else:
            self.graph_db = None
```

**FCEQueryEngine follows same pattern:**

```python
from theauditor.utils.helpers import normalize_path_for_db  # See query.py:97-99

class FCEQueryEngine:
    """Query engine for vector-based convergence analysis."""

    def __init__(self, root: Path):
        self.root = root
        pf_dir = root / ".pf"

        repo_db_path = pf_dir / "repo_index.db"
        if not repo_db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {repo_db_path}\nRun 'aud full' first."
            )

        self.repo_db = sqlite3.connect(str(repo_db_path))
        self.repo_db.row_factory = sqlite3.Row

        graph_db_path = pf_dir / "graphs.db"
        if graph_db_path.exists():
            self.graph_db = sqlite3.connect(str(graph_db_path))
            self.graph_db.row_factory = sqlite3.Row
        else:
            self.graph_db = None

        self.registry = SemanticTableRegistry()

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path for database queries."""
        return normalize_path_for_db(file_path, self.root)

    def get_vector_density(self, file_path: str) -> VectorSignal:
        """Calculate which analysis vectors have data for this file."""
        pass

    def get_convergence_points(self, min_vectors: int = 2) -> list[ConvergencePoint]:
        """Find all locations where multiple vectors converge."""
        pass

    def get_context_bundle(self, file_path: str, line: int) -> AIContextBundle:
        """Package convergence + context for AI consumption."""
        pass

    def close(self) -> None:
        """Close database connections."""
        self.repo_db.close()
        if self.graph_db:
            self.graph_db.close()
```

**Rationale:**
- Proven pattern already working in `aud explain`
- Same databases (repo_index.db, graphs.db)
- Consistent with codebase conventions
- Easy to integrate with other commands
- Path normalization required (see `theauditor/utils/helpers.py`)

### Decision 2: Package Structure

```
theauditor/fce/
    __init__.py       # Public API exports
    schema.py         # Pydantic models
    query.py          # FCEQueryEngine (main logic)
    formatter.py      # Text/JSON output formatting
    registry.py       # Semantic Table Registry
```

**NOT this (over-engineered):**
```
theauditor/fce/
    collectors/       # NO - abstraction for abstraction's sake
    analyzers/        # NO - same problem
    resolver.py       # NO - merged into query.py
```

**Rationale:**
- 5 files vs 15+ files
- No unnecessary abstraction layers
- Matches `theauditor/context/` structure
- ZERO FALLBACK compliant (no collector failure fallback needed)

### Decision 3: Pydantic Models

```python
from pydantic import BaseModel
from enum import Enum

class Vector(str, Enum):
    """The four independent analysis dimensions."""
    STATIC = "static"      # Linters (ruff, eslint, patterns)
    FLOW = "flow"          # Taint analysis (taint_flows)
    PROCESS = "process"    # Git churn (code_diffs, churn-analysis)
    STRUCTURAL = "struct"  # Complexity (cfg-analysis)

class Fact(BaseModel):
    """A single undeniable observation from one source."""
    vector: Vector
    source: str           # e.g., "ruff", "taint_flows", "cfg-analysis"
    file_path: str
    line: int | None
    observation: str      # Human-readable description
    raw_data: dict        # The proof

class VectorSignal(BaseModel):
    """Which vectors have data for a location."""
    file_path: str
    vectors_present: set[Vector]

    @property
    def density(self) -> float:
        """0.0 to 1.0 based on vectors present."""
        return len(self.vectors_present) / 4

    @property
    def density_label(self) -> str:
        """Human-readable: '3/4 vectors'"""
        return f"{len(self.vectors_present)}/4 vectors"

class ConvergencePoint(BaseModel):
    """A location where multiple vectors converge."""
    file_path: str
    line_start: int
    line_end: int
    signal: VectorSignal
    facts: list[Fact]

class AIContextBundle(BaseModel):
    """Package for AI/LLM consumption."""
    convergence: ConvergencePoint
    context_layers: dict[str, list[dict]]  # framework, security, language context

    def to_prompt_context(self) -> str:
        return self.model_dump_json(indent=2)
```

**Rationale:**
- Strict typing catches bugs
- `Vector` enum makes density calculation impossible to mess up
- `density` is pure math - can't be wrong
- `context_layers` is generic - works for any table category

### Decision 4: Vector-Based Signal Density

**OLD (Tool Count - Wrong):**
```python
# 5 linters screaming = high density (FALSE - it's one syntax error)
signal_density = len(unique_tools) / 9  # 5/9 = 0.55
```

**NEW (Vector Count - Correct):**
```python
def _has_static_findings(self, file_path: str) -> bool:
    """Check if file has any linter findings (STATIC vector)."""
    normalized = self._normalize_path(file_path)
    cursor = self.repo_db.cursor()
    cursor.execute("""
        SELECT 1 FROM findings_consolidated
        WHERE file = ?
          AND tool NOT IN ('cfg-analysis', 'churn-analysis', 'graph-analysis')
        LIMIT 1
    """, (normalized,))
    return cursor.fetchone() is not None

def _has_flow_findings(self, file_path: str) -> bool:
    """Check if file has taint flows (FLOW vector)."""
    normalized = self._normalize_path(file_path)
    cursor = self.repo_db.cursor()
    cursor.execute("""
        SELECT 1 FROM taint_flows
        WHERE source_file = ? OR sink_file = ?
        LIMIT 1
    """, (normalized, normalized))
    return cursor.fetchone() is not None

def _has_process_data(self, file_path: str) -> bool:
    """Check if file has churn data (PROCESS vector)."""
    normalized = self._normalize_path(file_path)
    cursor = self.repo_db.cursor()
    cursor.execute("""
        SELECT 1 FROM findings_consolidated
        WHERE file = ? AND tool = 'churn-analysis'
        LIMIT 1
    """, (normalized,))
    return cursor.fetchone() is not None

def _has_structural_data(self, file_path: str) -> bool:
    """Check if file has CFG/complexity data (STRUCTURAL vector)."""
    normalized = self._normalize_path(file_path)
    cursor = self.repo_db.cursor()
    cursor.execute("""
        SELECT 1 FROM findings_consolidated
        WHERE file = ? AND tool = 'cfg-analysis'
        LIMIT 1
    """, (normalized,))
    return cursor.fetchone() is not None

def get_vector_density(self, file_path: str) -> VectorSignal:
    """Calculate which analysis vectors have data for this file."""
    vectors = set()

    if self._has_static_findings(file_path):
        vectors.add(Vector.STATIC)
    if self._has_flow_findings(file_path):
        vectors.add(Vector.FLOW)
    if self._has_process_data(file_path):
        vectors.add(Vector.PROCESS)
    if self._has_structural_data(file_path):
        vectors.add(Vector.STRUCTURAL)

    return VectorSignal(file_path=file_path, vectors_present=vectors)
```

**Vector Definitions:**

| Vector | SQL Query | What It Means |
|--------|-----------|---------------|
| STATIC | `WHERE tool NOT IN ('cfg-analysis', 'churn-analysis', 'graph-analysis')` | Code quality issues (bugs, style) |
| FLOW | `FROM taint_flows WHERE source_file = ? OR sink_file = ?` | Data flow vulnerabilities |
| PROCESS | `WHERE tool = 'churn-analysis'` | Change volatility |
| STRUCTURAL | `WHERE tool = 'cfg-analysis'` | Complexity issues |

**Rationale:**
- Independent signals that don't duplicate
- 4/4 = "everything is screaming at this location"
- 1/4 = "one dimension noticed something"
- Pure math, no opinion

### Decision 5: Semantic Table Registry

**The Problem:** 226 tables, can't write custom queries for each.

**The Solution:** Categorize ALL tables by role (complete lists):

```python
class SemanticTableRegistry:
    """Categorizes tables for intelligent querying."""

    # Tables that flag PROBLEMS (used for vector detection)
    RISK_SOURCES = {
        "cdk_findings",
        "findings_consolidated",
        "framework_taint_patterns",
        "graphql_findings_cache",
        "python_security_findings",
        "taint_flows",
        "terraform_findings",
    }

    # Change history / volatility
    CONTEXT_PROCESS = {
        "code_diffs",
        "code_snapshots",
        "refactor_candidates",
        "refactor_history",
    }

    # CFG / complexity data
    CONTEXT_STRUCTURAL = {
        "cfg_block_statements",
        "cfg_block_statements_jsx",
        "cfg_blocks",
        "cfg_blocks_jsx",
        "cfg_edges",
        "cfg_edges_jsx",
    }

    # Framework-specific tables (36 tables)
    CONTEXT_FRAMEWORK = {
        "angular_component_styles",
        "angular_components",
        "angular_guards",
        "angular_module_declarations",
        "angular_module_exports",
        "angular_module_imports",
        "angular_module_providers",
        "angular_modules",
        "angular_services",
        "bullmq_queues",
        "bullmq_workers",
        "express_middleware_chains",
        "graphql_arg_directives",
        "graphql_execution_edges",
        "graphql_field_args",
        "graphql_field_directives",
        "graphql_fields",
        "graphql_resolver_mappings",
        "graphql_resolver_params",
        "graphql_schemas",
        "graphql_types",
        "prisma_models",
        "react_component_hooks",
        "react_components",
        "react_hook_dependencies",
        "react_hooks",
        "sequelize_associations",
        "sequelize_model_fields",
        "sequelize_models",
        "vue_component_emits",
        "vue_component_props",
        "vue_component_setup_returns",
        "vue_components",
        "vue_directives",
        "vue_hooks",
        "vue_provide_inject",
    }

    # Security patterns
    CONTEXT_SECURITY = {
        "api_endpoint_controls",
        "api_endpoints",
        "jwt_patterns",
        "sql_objects",
        "sql_queries",
        "sql_query_tables",
    }

    # Language-specific tables (87 tables)
    CONTEXT_LANGUAGE = {
        # Bash (10 tables)
        "bash_command_args",
        "bash_commands",
        "bash_control_flows",
        "bash_functions",
        "bash_pipes",
        "bash_redirections",
        "bash_set_options",
        "bash_sources",
        "bash_subshells",
        "bash_variables",
        # Go (22 tables)
        "go_captured_vars",
        "go_channel_ops",
        "go_channels",
        "go_constants",
        "go_defer_statements",
        "go_error_returns",
        "go_func_params",
        "go_func_returns",
        "go_functions",
        "go_goroutines",
        "go_imports",
        "go_interface_methods",
        "go_interfaces",
        "go_methods",
        "go_middleware",
        "go_packages",
        "go_routes",
        "go_struct_fields",
        "go_structs",
        "go_type_assertions",
        "go_type_params",
        "go_variables",
        # Python (37 tables)
        "python_branches",
        "python_build_requires",
        "python_class_features",
        "python_collections",
        "python_comprehensions",
        "python_control_statements",
        "python_decorators",
        "python_descriptors",
        "python_django_middleware",
        "python_django_views",
        "python_expressions",
        "python_fixture_params",
        "python_framework_config",
        "python_framework_methods",
        "python_functions_advanced",
        "python_imports_advanced",
        "python_io_operations",
        "python_literals",
        "python_loops",
        "python_operators",
        "python_orm_fields",
        "python_orm_models",
        "python_package_configs",
        "python_package_dependencies",
        "python_protocol_methods",
        "python_protocols",
        "python_routes",
        "python_schema_validators",
        "python_state_mutations",
        "python_stdlib_usage",
        "python_test_cases",
        "python_test_fixtures",
        "python_type_definitions",
        "python_typeddict_fields",
        "python_validation_schemas",
        "python_validators",
        # Rust (20 tables)
        "rust_async_functions",
        "rust_await_points",
        "rust_enum_variants",
        "rust_enums",
        "rust_extern_blocks",
        "rust_extern_functions",
        "rust_functions",
        "rust_generics",
        "rust_impl_blocks",
        "rust_lifetimes",
        "rust_macro_invocations",
        "rust_macros",
        "rust_modules",
        "rust_struct_fields",
        "rust_structs",
        "rust_trait_methods",
        "rust_traits",
        "rust_unsafe_blocks",
        "rust_unsafe_traits",
        "rust_use_statements",
    }

    # Extension to language prefix mapping
    EXTENSION_TO_PREFIX = {
        ".py": "python_",
        ".go": "go_",
        ".rs": "rust_",
        ".sh": "bash_",
        ".bash": "bash_",
    }

    # Extension to framework tables mapping
    EXTENSION_TO_FRAMEWORKS = {
        ".ts": {"react_", "angular_", "vue_", "graphql_", "sequelize_", "prisma_"},
        ".tsx": {"react_", "angular_", "vue_", "graphql_", "sequelize_", "prisma_"},
        ".js": {"react_", "angular_", "vue_", "graphql_", "sequelize_", "prisma_", "express_"},
        ".jsx": {"react_", "graphql_"},
        ".vue": {"vue_"},
    }

    def get_context_tables_for_file(self, file_path: str) -> list[str]:
        """Return relevant context tables based on file extension."""
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        tables = []

        # Add language-specific tables
        prefix = self.EXTENSION_TO_PREFIX.get(ext)
        if prefix:
            tables.extend(t for t in self.CONTEXT_LANGUAGE if t.startswith(prefix))

        # Add framework tables for JS/TS
        fw_prefixes = self.EXTENSION_TO_FRAMEWORKS.get(ext, set())
        for fw_prefix in fw_prefixes:
            tables.extend(t for t in self.CONTEXT_FRAMEWORK if t.startswith(fw_prefix))

        return sorted(set(tables))
```

**Query Strategy:**
1. **Risk Query (Always):** Query RISK_SOURCES for the file
2. **Vector Check (Always):** Determine which vectors have data
3. **Context Expansion (Lazy):** Only load context tables when:
   - User requests `--deep` or `--context`
   - Building AIContextBundle

**Rationale:**
- Avoids 226 queries per file
- Smart about which context is relevant
- Lazy loading prevents memory explosion
- NO fallback if a table is missing - just skip it

### Decision 6: Service API for --fce Flags

**Public API in `theauditor/fce/__init__.py`:**

```python
from theauditor.fce.query import FCEQueryEngine
from theauditor.fce.schema import (
    Vector,
    Fact,
    VectorSignal,
    ConvergencePoint,
    AIContextBundle,
)

__all__ = [
    "FCEQueryEngine",
    "Vector",
    "Fact",
    "VectorSignal",
    "ConvergencePoint",
    "AIContextBundle",
]
```

**Integration in other commands:**

```python
# In theauditor/commands/explain.py
@click.option("--fce", is_flag=True, help="Add FCE convergence data")
def explain(target: str, fce: bool, ...):
    engine = CodeQueryEngine(root)
    data = engine.get_file_context_bundle(target)

    if fce:
        from theauditor.fce import FCEQueryEngine
        fce_engine = FCEQueryEngine(root)
        data["fce_signal"] = fce_engine.get_vector_density(target).model_dump()

    # ... rest of command
```

**Rationale:**
- FCE as a library, not just a command
- Other commands opt-in via flag
- Clean separation of concerns
- No coupling to specific output format

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Breaking output format | Document migration, version the schema |
| Missing vector data | Report 0/4 honestly, don't fabricate |
| Context expansion slow | Lazy load, cache per session |
| Table registry stale | Registry is code, update as schema evolves |

## What Gets Deleted

From current `theauditor/fce.py` (1512 lines):

| Lines | Code | Why Delete |
|-------|------|------------|
| 1003-1024 | `ARCHITECTURAL_RISK_ESCALATION` meta-finding | Opinion, not fact |
| 1043-1062 | `SYSTEMIC_DEBT_CLUSTER` meta-finding | Opinion, not fact |
| 1087-1135 | `COMPLEXITY_RISK_CORRELATION` with `complexity <= 20` | Hardcoded threshold |
| 1145-1163 | `HIGH_CHURN_RISK_CORRELATION` with `percentile_90` | Hardcoded threshold |
| 389-465 | `run_tool()` subprocess execution | Separate concern |
| 468-611 | Test output parsers (pytest, jest, tsc) | Separate concern |
| 951-978 | `register_meta()` function | Supports deleted features |

**Kept (refactored):**
- Database loading functions -> become FCEQueryEngine methods
- `scan_all_findings()` -> `_load_risk_sources()`
- `load_taint_data_from_db()` -> `_has_flow_findings()` check
- Output JSON writer -> FCEFormatter

## Migration Plan

1. Create `theauditor/fce/` package
2. Implement schema.py (Pydantic models)
3. Implement registry.py (table categories)
4. Implement query.py (FCEQueryEngine)
5. Implement formatter.py (text/json output)
6. Update commands/fce.py to use new package
7. Test: `aud fce` produces vector-based output
8. Delete old `theauditor/fce.py`
9. Add `--fce` flag to `aud explain` (Phase 2)
10. Add `--fce` flag to `aud blueprint` (Phase 2)

## Open Questions (Resolved)

1. **Should signal_density weight vectors?**
   - Answer: NO. 4 vectors, equal weight, pure math.

2. **Should we add async for parallel queries?**
   - Answer: NO. Keep sync, match CodeQueryEngine. Don't over-engineer.

3. **What if a vector has no data?**
   - Answer: Report honestly. 0/4 vectors is valid data.

4. **Should FCE run subprocess tests?**
   - Answer: NO. Move to separate command. FCE = correlation only.

5. **What about coverage data?**
   - Answer: NO coverage table exists in the database. The old FCE referenced coverage but it was never populated. Remove coverage references from spec.
