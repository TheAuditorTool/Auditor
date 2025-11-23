## Context

AI assistants waste context tokens reading entire files when they only need relationship data. TheAuditor indexes 250+ tables of code facts but lacks a command that bundles them into a "briefing packet." The explain command bridges query results (data) with source code (context).

**Constraints:**
- Database schema is frozen (use existing tables)
- No new dependencies (Python stdlib only)
- Windows CP1252 encoding (no emojis in output)
- ZERO FALLBACK policy (crash on missing tables, not silent degradation)

## Goals / Non-Goals

**Goals:**
- Single command for comprehensive code context
- Code snippets included by default (not optional)
- <100ms response time for typical files
- Works with files, symbols, and React components
- JSON output for AI consumption

**Non-Goals:**
- Git blame integration (future enhancement)
- Interactive drill-down mode (out of scope)
- Cross-project search (single project only)
- Semantic/embedding search (exact matches only)

## Decisions

### Decision 1: Separate command vs extending query

**Choice**: NEW `aud explain` command, not extending `aud query`

**Reasoning**:
- `query` is a microscope (specific, single-table queries)
- `explain` is a dossier (holistic, multi-table aggregation)
- Different mental models, different use cases
- Keeps query focused and fast

**Alternatives Rejected:**
- `aud query --explain` flag: Overloads query semantics, confusing UX
- `aud context explain`: Already have context subcommand, adds nesting

### Decision 2: Code snippet retrieval

**Choice**: Read from disk on-demand with LRU file cache (20 files max)

**Reasoning**:
- File contents are NOT in database (by design)
- Reading 1-3 lines per symbol is cheap (<1ms)
- Cache prevents re-reading same file for multiple symbols
- 20-file cache sufficient for typical explain output

**Implementation Details:**
- `CodeSnippetManager` class in `theauditor/utils/code_snippets.py`
- LRU cache using `collections.OrderedDict`
- Safety: file size limit (1MB), binary detection, encoding fallback
- Line expansion: indentation-based block detection (max 15 lines)

### Decision 3: Target auto-detection

**Choice**: Detect target type by extension and naming convention

**Algorithm:**
```python
def detect_target_type(target: str) -> str:
    # File path detection (has known extension)
    if any(target.endswith(ext) for ext in ['.ts', '.tsx', '.js', '.jsx', '.py', '.rs']):
        return 'file'
    # Qualified symbol (Class.method)
    if '.' in target and target[0].isupper():
        return 'symbol'
    # Component candidate (PascalCase)
    if target[0].isupper():
        # Check react_components table first
        return 'component' if found_in_react_components else 'symbol'
    # Default to symbol search
    return 'symbol'
```

**Rejected Alternatives:**
- `--type file|symbol|component` flag: Extra friction for common case
- Always search all types: Slower, ambiguous results

### Decision 4: Output limiting for super-nodes

**Choice**: Limit each section to 20 items, show count and hint for more

**Reasoning**:
- Files like `utils/logger.ts` may have 5000+ dependents
- Dumping all destroys context window
- 20 items gives representative sample

**Format:**
```
DEPENDENTS (5,023 files import this):
  1. src/app.ts
  2. src/server.ts
  ...
  20. src/utils/crypto.ts
  (and 5,003 others - run 'aud query --dependents' to list all)
```

### Decision 5: Database queries

**Choice**: Reuse `CodeQueryEngine` from `theauditor/context/query.py`

**Reasoning**:
- Already has all the query methods needed
- Handles symbol resolution, fuzzy suggestions
- Connection management and error handling done

**New method to add:**
```python
def get_file_context_bundle(self, file_path: str) -> dict:
    """Aggregate all context for a file in one call."""
    return {
        'symbols': self.find_symbol_in_file(file_path),
        'hooks': self._get_react_hooks(file_path),
        'dependencies': self.get_file_dependencies(file_path, 'outgoing'),
        'dependents': self.get_file_dependencies(file_path, 'incoming'),
        'outgoing_calls': self._get_outgoing_calls(file_path),
        'incoming_calls': self._get_incoming_calls(file_path),
    }
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| File not on disk (deleted/moved) | Show indexed data with "[file not found]" for snippets |
| Binary file | Detect via encoding error, skip snippets |
| Very long lines (>200 chars) | Truncate with "..." |
| Multi-line expressions | Show line + 2 context lines, max 15 total |
| Stale index | Warn if file mtime > index time |

## Migration Plan

N/A - New command, no existing behavior to migrate.

## Open Questions

NONE - All decisions made. Ready for implementation.
