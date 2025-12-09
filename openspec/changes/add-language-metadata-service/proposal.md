## Why

TheAuditor commands have **hardcoded language-specific data scattered across 10+ locations**. Adding a new language (e.g., Java, C#, Lua) requires modifying all of them manually - a maintenance nightmare that violates DRY.

### Current State: Hardcoded Data Inventory

| File | Lines | What's Hardcoded | Languages |
|------|-------|------------------|-----------|
| `theauditor/commands/explain.py` | 33-45 | `FILE_EXTENSIONS` set | 11 extensions |
| `theauditor/commands/blueprint.py` | 385-455 | Naming convention SQL CASE statements | py, js, jsx, ts, tsx, go, rs, sh, bash |
| `theauditor/commands/blueprint.py` | 459-483 | Language name dict keys | 6 languages |
| `theauditor/context/deadcode_graph.py` | 303-316 | Entry point patterns in `_find_entry_points()` | py, ts, js, tsx |
| `theauditor/context/deadcode_graph.py` | 346-386 | Framework entry points in `_find_framework_entry_points()` | all |
| `theauditor/commands/refactor.py` | 800-802 | Migration file globs | js, ts, sql only |
| `theauditor/boundaries/boundary_analyzer.py` | 19-25 | `_table_exists()` function | N/A |
| `theauditor/boundaries/boundary_analyzer.py` | 229-323 | Route table queries with `_table_exists` checks | py, js, go, rs |

### CRITICAL: Route Table Column Differences (Discovered During Investigation)

Route tables have **DIFFERENT column names** per language:

| Table | file column | line column | pattern column | method column |
|-------|-------------|-------------|----------------|---------------|
| `python_routes` | `file` | `line` | `pattern` | `method` |
| `js_routes` | `file` | `line` | `pattern` | `method` |
| `go_routes` | `file` | `line` | `path` | `method` |
| `rust_attributes` | `file_path` | `target_line` | `args` | `attribute_name` |

A unified "SELECT file, line, pattern, method FROM {table}" query **DOES NOT WORK**.
This proposal includes `RouteTableInfo` dataclass with column mapping.

### CRITICAL: Framework-Specific Route Sources

**This was missed in initial proposal.** Frameworks override default language route sources:

| Framework | Language | Route Source | Notes |
|-----------|----------|--------------|-------|
| Express | JavaScript | `express_middleware_chains` | NOT `js_routes` - uses middleware chain analysis |
| FastAPI | Python | `python_routes` + `python_decorators` | Default + decorator enrichment |
| Django | Python | `python_routes` | Default |
| Actix/Rocket | Rust | `rust_attributes` | Default with filter |

The current `boundary_analyzer.py` already implements framework-aware routing (lines 57-182 for Express).
This proposal extends LanguageMetadataService to be **framework-aware**.

### ZERO FALLBACK VIOLATION in Current Code

The current `boundary_analyzer.py` uses `_table_exists()` checks (lines 19-25, used at 35, 69, 74, 93, 229, 248, 267, 286, 305) which **VIOLATES ZERO FALLBACK POLICY**. This proposal fixes that.

### Problem Example: Adding Lua Support

**Current process (10 file changes):**
1. Create `LuaExtractor` in `extractors/lua.py`
2. Create `lua_schema.py` with tables
3. Edit `explain.py` line 33: add `.lua` to FILE_EXTENSIONS
4. Edit `blueprint.py` lines 385-455: add new SQL CASE statements
5. Edit `blueprint.py` lines 459-483: add "lua" key to conventions dict
6. Edit `deadcode_graph.py` lines 303-386: add Lua entry point patterns
7. Edit `boundary_analyzer.py`: add `lua_routes` query
8. Edit `refactor.py` lines 800-802: add `.lua` to migration globs (if applicable)
9. Edit `fce/registry.py`: add Lua tables to CONTEXT_LANGUAGE
10. Pray you didn't miss anything

**Future process (1 file change):**
1. Create `LuaExtractor` in `extractors/lua.py` with metadata methods
2. Done. All commands discover the new language automatically.

## What Changes

### NEW Files
- `theauditor/core/__init__.py` - Core package init
- `theauditor/core/language_metadata.py` - RouteTableInfo, FrameworkRouteInfo, LanguageMetadata dataclasses + LanguageMetadataService singleton

### MODIFIED Files (Core Infrastructure)
- `theauditor/indexer/extractors/__init__.py` - Add 6 metadata methods to BaseExtractor (including framework-aware), 5 query methods to ExtractorRegistry

### MODIFIED Files (5 Main Extractors - add metadata overrides)
- `theauditor/indexer/extractors/python.py`
- `theauditor/indexer/extractors/javascript.py`
- `theauditor/indexer/extractors/rust.py`
- `theauditor/indexer/extractors/go.py`
- `theauditor/indexer/extractors/bash.py`

### MODIFIED Files (Service Initialization)
- `theauditor/indexer/orchestrator.py` - Initialize LanguageMetadataService after ExtractorRegistry

### MODIFIED Files (Command Migration)
- `theauditor/commands/explain.py` - Replace FILE_EXTENSIONS with service call
- `theauditor/context/deadcode_graph.py` - Replace entry point patterns with service call
- `theauditor/boundaries/boundary_analyzer.py` - Replace `_table_exists` checks in GENERIC fallback only (preserve Express analyzer)

### UNCHANGED Files (7 Secondary Extractors - use default metadata)
- `theauditor/indexer/extractors/terraform.py` - Uses default: `terraform`
- `theauditor/indexer/extractors/sql.py` - Uses default: `sql`
- `theauditor/indexer/extractors/graphql.py` - Uses default: `graphql`
- `theauditor/indexer/extractors/prisma.py` - Uses default: `prisma`
- `theauditor/indexer/extractors/docker.py` - Uses default: `docker`
- `theauditor/indexer/extractors/github_actions.py` - Uses default: `githubworkflow`
- `theauditor/indexer/extractors/generic.py` - Uses default: `generic`

### DELETED Code (~150 lines from generic fallback only)
- `explain.py:33-45` - FILE_EXTENSIONS set (replaced by service)
- `boundary_analyzer.py:19-25` - `_table_exists()` function (ZERO FALLBACK violation)
- `boundary_analyzer.py:229-323` - Hardcoded route table queries in generic fallback (replaced by RouteTableInfo loop)

### PRESERVED Code (Express framework analyzer)
- `boundary_analyzer.py:28-54` - `_detect_frameworks()` function (KEEP - uses LanguageMetadataService internally)
- `boundary_analyzer.py:57-182` - `_analyze_express_boundaries()` function (KEEP - framework-specific logic)

## Impact

- **Affected specs**: NEW `language-metadata`
- **Breaking changes**: NONE - all new methods have defaults
- **ZERO FALLBACK fix**: Removes `_table_exists()` violation in boundary_analyzer.py generic fallback
- **Framework preservation**: Express analyzer remains intact, gets metadata from service
- **Risk level**: LOW - additive changes, gradual migration supported
- **Testing**: Run `aud full --offline` + all commands on polyglot test repo

## Success Criteria

1. `openspec validate add-language-metadata-service --strict` passes
2. All existing tests pass unchanged
3. Adding new language requires only 1 extractor file
4. Commands discover new language metadata automatically
5. NO `_table_exists()` checks remain in boundary_analyzer.py generic fallback
6. Express framework analyzer continues to work (uses middleware chains)
7. NO try-except fallbacks in any migration code
