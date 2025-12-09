# Verification Phase Report (TEAMSOP 1.3 Compliance)

## Hypotheses & Verification

### Hypothesis 1: `theauditor/core/` directory does NOT exist
**Verification**: CONFIRMED by `Glob` search returning "No files found" for `theauditor/core/**/*`
**Action**: Must create directory and `__init__.py`

### Hypothesis 2: BaseExtractor ends at line 77 with `cleanup()` method
**Verification**: CONFIRMED by reading `theauditor/indexer/extractors/__init__.py`
- Lines 13-77: BaseExtractor class
- Lines 72-76: `cleanup()` method is the last method
**Action**: Add metadata methods after line 77

### Hypothesis 3: ExtractorRegistry ends at line 136 with `supported_extensions()`
**Verification**: CONFIRMED by reading `theauditor/indexer/extractors/__init__.py`
- Lines 79-136: ExtractorRegistry class
- Lines 133-135: `supported_extensions()` is the last method
**Action**: Add query methods after line 136

### Hypothesis 4: Route table column names differ per language
**Verification**: CONFIRMED by reading `theauditor/boundaries/boundary_analyzer.py:229-323`

| Table | file | line | pattern | method |
|-------|------|------|---------|--------|
| `python_routes` | `file` | `line` | `pattern` | `method` |
| `js_routes` | `file` | `line` | `pattern` | `method` |
| `go_routes` | `file` | `line` | `path` (NOT pattern!) | `method` |
| `rust_attributes` | `file_path` (NOT file!) | `target_line` (NOT line!) | `args` (NOT pattern!) | `attribute_name` (NOT method!) |

**Action**: Created RouteTableInfo dataclass with column mapping

### Hypothesis 5: boundary_analyzer.py uses `_table_exists()` which violates ZERO FALLBACK
**Verification**: CONFIRMED by reading `theauditor/boundaries/boundary_analyzer.py:19-25`
```python
def _table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None
```
Used at lines 35, 69, 74, 93, 229, 248, 267, 286, 305 - each with `if _table_exists(cursor, "xxx"):` pattern.
**Action**: Delete `_table_exists()` in generic fallback section, preserve in framework-aware sections for now

### Hypothesis 6: boundary_analyzer.py has framework-aware Express analyzer
**Verification**: CONFIRMED by reading `theauditor/boundaries/boundary_analyzer.py:57-182`
```python
def _analyze_express_boundaries(cursor, framework_info: list[dict], max_entries: int) -> list[dict]:
    """Analyze boundaries for Express.js projects using middleware chains.

    Express middleware runs BEFORE the handler, so we check express_middleware_chains
    for validation middleware rather than doing call graph traversal.
    """
```
**Action**: PRESERVE this function, integrate with LanguageMetadataService via FrameworkRouteInfo

### Hypothesis 7: All 12 extractors exist in `theauditor/indexer/extractors/`
**Verification**: CONFIRMED by `Glob` search

**Main extractors (need metadata overrides):**
1. `python.py` - PythonExtractor
2. `javascript.py` - JavaScriptExtractor
3. `rust.py` - RustExtractor
4. `go.py` - GoExtractor
5. `bash.py` - BashExtractor

**Secondary extractors (use defaults):**
6. `terraform.py` - TerraformExtractor
7. `sql.py` - SQLExtractor
8. `graphql.py` - GraphQLExtractor
9. `prisma.py` - PrismaExtractor
10. `docker.py` - DockerExtractor
11. `github_actions.py` - GitHubWorkflowExtractor
12. `generic.py` - GenericExtractor

**Support files (not extractors):**
- `__init__.py` - Base classes
- `rust_resolver.py` - Rust module resolution
- `javascript_resolvers.py` - JS resolution mixin
- `manifest_extractor.py` - Manifest handling
- `manifest_parser.py` - Manifest parsing

### Hypothesis 8: explain.py FILE_EXTENSIONS is at lines 33-45
**Verification**: CONFIRMED by reading `theauditor/commands/explain.py:33-45`
```python
FILE_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".vue",
    ".rb",
    ".php",
}
```
**Action**: Replace with service call

### Hypothesis 9: deadcode_graph.py entry points are at lines 303-316
**Verification**: CONFIRMED by reading `theauditor/context/deadcode_graph.py:299-326`
```python
def _find_entry_points(self, graph: nx.DiGraph) -> set[str]:
    """Multi-strategy entry point detection."""
    entry_points = set()

    for node in graph.nodes():
        if any(
            pattern in node
            for pattern in [
                "cli.py",
                "__main__.py",
                "main.py",
                "index.ts",
                "index.js",
                "index.tsx",
                "App.tsx",
            ]
        ):
            entry_points.add(node)
```
**Action**: Replace with service call

### Hypothesis 10: orchestrator.py creates ExtractorRegistry at line 48
**Verification**: CONFIRMED by reading `theauditor/indexer/orchestrator.py:48`
```python
self.extractor_registry = ExtractorRegistry(root_path, self.ast_parser)
```
**Action**: Add `LanguageMetadataService.initialize(self.extractor_registry)` after line 48

### Hypothesis 11: blueprint.py naming conventions are at lines 385-455
**Verification**: CONFIRMED by reading `theauditor/commands/blueprint.py:382-455`
- `_get_naming_conventions()` function starts at line 382
- SQL query with hardcoded extensions runs from 385-455
**Action**: Document for future migration (not in scope for this proposal)

### Hypothesis 12: refactor.py migration globs are at lines 800-802
**Verification**: CONFIRMED by reading `theauditor/commands/refactor.py:799-802`
```python
migrations = sorted(
    glob.glob(str(migration_path / "*.js"))
    + glob.glob(str(migration_path / "*.ts"))
    + glob.glob(str(migration_path / "*.sql"))
)
```
**Action**: Document for future migration (not in scope for this proposal)

---

## Discrepancies Found

### Discrepancy 1: Original ticket assumed unified route query possible
**Initial Assumption**: Route tables have same column names
**Reality**: Column names differ per language (verified above)
**Resolution**: Added RouteTableInfo dataclass with column mapping

### Discrepancy 2: Original ticket only listed 5 extractors
**Initial Assumption**: Only Python, JavaScript, Rust, Go, Bash extractors
**Reality**: 12 extractors exist (5 main + 7 secondary)
**Resolution**: Updated spec to document all 12, secondary use defaults

### Discrepancy 3: Original ticket missed framework-aware boundary analysis
**Initial Assumption**: All route analysis uses simple table queries
**Reality**: Express framework has dedicated analyzer (`_analyze_express_boundaries`) that uses middleware chains
**Resolution**: Added FrameworkRouteInfo dataclass and `get_framework_routes()` method to handle framework overrides

### Discrepancy 4: Original ticket proposed replacing entire boundary_analyzer function
**Initial Assumption**: Simple replacement of analyze_input_validation_boundaries()
**Reality**: Function has 3-layer structure: framework detection → framework analyzers → generic fallback
**Resolution**: Only replace generic fallback section (lines 229-323), preserve framework-aware logic

---

## Verification Status

| Hypothesis | Status | Evidence |
|------------|--------|----------|
| 1. core/ doesn't exist | CONFIRMED | Glob returned no files |
| 2. BaseExtractor ends line 77 | CONFIRMED | Read __init__.py |
| 3. ExtractorRegistry ends line 136 | CONFIRMED | Read __init__.py |
| 4. Route columns differ | CONFIRMED | Read boundary_analyzer.py |
| 5. _table_exists violates ZERO FALLBACK | CONFIRMED | Read boundary_analyzer.py:19-25 |
| 6. Express has custom analyzer | CONFIRMED | Read boundary_analyzer.py:57-182 |
| 7. 12 extractors exist | CONFIRMED | Glob + Read |
| 8. FILE_EXTENSIONS at 33-45 | CONFIRMED | Read explain.py |
| 9. Entry points at 303-316 | CONFIRMED | Read deadcode_graph.py |
| 10. ExtractorRegistry at line 48 | CONFIRMED | Read orchestrator.py |
| 11. Naming conventions at 385-455 | CONFIRMED | Read blueprint.py |
| 12. Migration globs at 800-802 | CONFIRMED | Read refactor.py |

**All hypotheses verified. Ready for implementation.**
