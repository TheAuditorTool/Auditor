## Why

TheAuditor commands have **hardcoded language-specific data scattered across 10+ locations**. Adding a new language (e.g., Java, C#, Lua) requires modifying all of them manually - a maintenance nightmare that violates DRY.

### Current State: Hardcoded Data Inventory

| File | Lines | What's Hardcoded | Languages |
|------|-------|------------------|-----------|
| `theauditor/commands/explain.py` | 33-45 | `FILE_EXTENSIONS` set | 11 extensions |
| `theauditor/commands/blueprint.py` | 378-441 | Naming convention SQL CASE statements | py, js, jsx, ts, tsx, go, rs, sh, bash |
| `theauditor/commands/blueprint.py` | 449-473 | Language name dict keys | 6 languages |
| `theauditor/commands/blueprint.py` | 922-937 | Symbol types per language | go, rust, bash |
| `theauditor/commands/refactor.py` | 422-442 | Migration file globs | js, ts, sql only |
| `theauditor/context/deadcode_graph.py` | 287-298 | Entry point filenames | py, ts, js, tsx |
| `theauditor/context/deadcode_graph.py` | 350-355 | Go entry points | go |
| `theauditor/context/deadcode_graph.py` | 364-370 | Rust entry points | rs |
| `theauditor/context/deadcode_graph.py` | 372-374 | Bash entry points | sh, bash |
| `theauditor/context/deadcode_graph.py` | 316-327 | Python decorator patterns | py |
| `theauditor/boundaries/boundary_analyzer.py` | 35-52 | `python_routes` table query | py |
| `theauditor/boundaries/boundary_analyzer.py` | 55-72 | `js_routes` table query | js |
| `theauditor/boundaries/boundary_analyzer.py` | 95-112 | `go_routes` table query | go |
| `theauditor/boundaries/boundary_analyzer.py` | 115-130 | `rust_attributes` table query | rs |
| `theauditor/context/query.py` | 1403-1525 | Massive if-elif chain by extension | all |

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

### ZERO FALLBACK VIOLATION in Current Code

The current `boundary_analyzer.py` uses `_table_exists()` checks (lines 16-22, 35, 55, 95, 115) which **VIOLATES ZERO FALLBACK POLICY**. This proposal fixes that.

### Problem Example: Adding Lua Support

**Current process (10 file changes):**
1. Create `LuaExtractor` in `extractors/lua.py`
2. Create `lua_schema.py` with tables
3. Edit `explain.py` line 33: add `.lua` to FILE_EXTENSIONS
4. Edit `blueprint.py` lines 378-441: add 6 new SQL CASE statements
5. Edit `blueprint.py` lines 449-473: add "lua" key to conventions dict
6. Edit `deadcode_graph.py` lines 287-375: add Lua entry point patterns
7. Edit `boundary_analyzer.py`: add `lua_routes` query
8. Edit `query.py` lines 1403-1525: add Lua if-elif branch
9. Edit `fce/registry.py`: add Lua tables to CONTEXT_LANGUAGE
10. Pray you didn't miss anything

**Future process (1 file change):**
1. Create `LuaExtractor` in `extractors/lua.py` with metadata methods
2. Done. All commands discover the new language automatically.

## What Changes

### NEW Files
- `theauditor/core/__init__.py` - Core package init
- `theauditor/core/language_metadata.py` - RouteTableInfo, LanguageMetadata dataclasses + LanguageMetadataService singleton

### MODIFIED Files (Core Infrastructure)
- `theauditor/indexer/extractors/__init__.py` - Add 5 metadata methods to BaseExtractor, 5 query methods to ExtractorRegistry

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
- `theauditor/boundaries/boundary_analyzer.py` - Replace route table queries with RouteTableInfo + DELETE `_table_exists()`

### UNCHANGED Files (7 Secondary Extractors - use default metadata)
- `theauditor/indexer/extractors/terraform.py` - Uses default: `terraform`
- `theauditor/indexer/extractors/sql.py` - Uses default: `sql`
- `theauditor/indexer/extractors/graphql.py` - Uses default: `graphql`
- `theauditor/indexer/extractors/prisma.py` - Uses default: `prisma`
- `theauditor/indexer/extractors/docker.py` - Uses default: `docker`
- `theauditor/indexer/extractors/github_actions.py` - Uses default: `githubworkflow`
- `theauditor/indexer/extractors/generic.py` - Uses default: `generic`

### DELETED Code (~200 lines)
- `explain.py:33-45` - FILE_EXTENSIONS set (replaced by service)
- `boundary_analyzer.py:16-22` - `_table_exists()` function (ZERO FALLBACK violation)
- `boundary_analyzer.py:35-130` - Hardcoded route table queries (replaced by RouteTableInfo loop)
- `deadcode_graph.py:287-298` - Hardcoded entry point patterns (replaced by service)

## Impact

- **Affected specs**: NEW `language-metadata`
- **Breaking changes**: NONE - all new methods have defaults
- **ZERO FALLBACK fix**: Removes `_table_exists()` violation in boundary_analyzer.py
- **Risk level**: LOW - additive changes, gradual migration supported
- **Testing**: Run `aud full --offline` + all commands on polyglot test repo

## Success Criteria

1. `openspec validate add-language-metadata-service --strict` passes
2. All existing tests pass unchanged
3. Adding new language requires only 1 extractor file
4. Commands discover new language metadata automatically
5. NO `_table_exists()` checks remain in boundary_analyzer.py
6. NO try-except fallbacks in any migration code
