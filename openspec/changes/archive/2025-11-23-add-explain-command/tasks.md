## 0. Verification (COMPLETED - DO NOT SKIP)

Verified against actual `.pf/repo_index.db` and `.pf/graphs.db` on 2025-11-23:

| Table | Exists | Row Count | Key Columns |
|-------|--------|-----------|-------------|
| `symbols` | YES | 58,018 | `path`, `name`, `type`, `line`, `end_line` |
| `symbols_jsx` | YES | - | Same as symbols |
| `function_call_args` | YES | 72,385 | `file`, `line`, `caller_function`, `callee_function`, `argument_expr` |
| `function_call_args_jsx` | YES | - | Same as function_call_args |
| `react_components` | YES | 224 | `file`, `name`, `type`, `start_line`, `end_line`, `has_jsx`, `props_type` |
| `react_hooks` | YES | 196 | `file`, `line`, `component_name`, `hook_name` (MIXED: hooks + method calls!) |
| `react_component_hooks` | YES | 142 | `component_file`, `component_name`, `hook_name` |
| `refs` | YES | 1,124 | `src`, `kind`, `value`, `line` (kind: import/require/dynamic_import) |
| `api_endpoints` | YES | - | `file`, `line`, `method`, `path`, `handler_function` |
| `edges` (graphs.db) | YES | 134,491 | `source`, `target`, `type`, `graph_type` (import/call/data_flow) |

**CRITICAL SCHEMA NOTES:**
- `symbols` uses `path` column for file path
- `function_call_args` uses `file` column for file path
- `refs` uses `src` column for file path
- `react_hooks.hook_name` contains BOTH React hooks (useState) AND method calls (userService.getUsers) - MUST FILTER
- Actual React hooks: useState, useEffect, useCallback, useMemo, useRef, useContext, useReducer, useLayoutEffect, useImperativeHandle, useDebugValue

---

## 1. Core Infrastructure

### 1.1 Create `theauditor/utils/code_snippets.py`

**File**: `theauditor/utils/code_snippets.py` (NEW)
**Lines**: ~150

**Imports:**
```python
from pathlib import Path
from collections import OrderedDict
from typing import Optional
```

**Class Structure:**
```python
class CodeSnippetManager:
    """Read source code lines with LRU caching and safety limits.

    Safety limits:
    - Max file size: 1MB (skip larger files)
    - Max cache size: 20 files
    - Max snippet lines: 15
    - Max line length: 120 chars (truncate with ...)
    """

    MAX_FILE_SIZE = 1_000_000  # 1MB
    MAX_CACHE_SIZE = 20
    MAX_SNIPPET_LINES = 15
    MAX_LINE_LENGTH = 120

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self._cache: OrderedDict[str, list[str]] = OrderedDict()

    def get_snippet(self, file_path: str, line: int, expand_block: bool = True) -> str:
        """Get code snippet for a line with optional block expansion.

        Args:
            file_path: Relative path from root_dir
            line: 1-indexed line number
            expand_block: If True, expand to include full block (max 15 lines)

        Returns:
            Formatted snippet with line numbers, or error message string
        """
        ...

    def _get_file_lines(self, file_path: str) -> list[str] | None:
        """Load file into cache, return lines or None on error."""
        ...

    def _expand_block(self, lines: list[str], start_idx: int) -> int:
        """Return end index for block expansion based on indentation."""
        ...

    def _format_snippet(self, lines: list[str], start_idx: int, end_idx: int) -> str:
        """Format lines with line numbers."""
        ...
```

**Method: `_get_file_lines` implementation:**
```python
def _get_file_lines(self, file_path: str) -> list[str] | None:
    # Check cache first
    if file_path in self._cache:
        self._cache.move_to_end(file_path)  # LRU touch
        return self._cache[file_path]

    # Build full path
    full_path = self.root_dir / file_path

    # Safety: check exists
    if not full_path.exists():
        return None  # Caller handles with "[File not found on disk]"

    # Safety: check size
    if full_path.stat().st_size > self.MAX_FILE_SIZE:
        return None  # Caller handles with "[File too large to preview]"

    # Read with encoding fallback
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return None  # Caller handles with "[Binary file - no preview]"

    # Add to cache, evict oldest if needed
    if len(self._cache) >= self.MAX_CACHE_SIZE:
        self._cache.popitem(last=False)  # Remove oldest
    self._cache[file_path] = lines

    return lines
```

**Method: `_expand_block` implementation:**
```python
def _expand_block(self, lines: list[str], start_idx: int) -> int:
    """Expand from start_idx to include indented block, max 15 lines."""
    if start_idx >= len(lines):
        return start_idx

    start_line = lines[start_idx]
    start_indent = len(start_line) - len(start_line.lstrip())

    end_idx = start_idx
    for i in range(start_idx + 1, min(start_idx + self.MAX_SNIPPET_LINES, len(lines))):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            end_idx = i
            continue

        curr_indent = len(line) - len(line.lstrip())

        # Stop if we're back to same or lower indent (unless closing brace)
        if curr_indent <= start_indent:
            if line.strip().startswith(('}', ']', ')')):
                return i  # Include closing brace
            return end_idx

        end_idx = i

    return end_idx
```

**Method: `get_snippet` implementation:**
```python
def get_snippet(self, file_path: str, line: int, expand_block: bool = True) -> str:
    lines = self._get_file_lines(file_path)

    if lines is None:
        # Determine error type
        full_path = self.root_dir / file_path
        if not full_path.exists():
            return "[File not found on disk]"
        if full_path.stat().st_size > self.MAX_FILE_SIZE:
            return "[File too large to preview]"
        return "[Binary file - no preview]"

    # Convert to 0-indexed
    start_idx = line - 1
    if start_idx < 0 or start_idx >= len(lines):
        return f"[Line {line} out of range]"

    # Determine end index
    if expand_block:
        end_idx = self._expand_block(lines, start_idx)
    else:
        end_idx = start_idx

    return self._format_snippet(lines, start_idx, end_idx)

def _format_snippet(self, lines: list[str], start_idx: int, end_idx: int) -> str:
    result = []
    for i in range(start_idx, end_idx + 1):
        line_num = i + 1  # 1-indexed
        line_content = lines[i].rstrip()

        # Truncate long lines
        if len(line_content) > self.MAX_LINE_LENGTH:
            line_content = line_content[:self.MAX_LINE_LENGTH - 3] + "..."

        result.append(f"{line_num:4d} | {line_content}")

    return "\n".join(result)
```

---

### 1.2 Create `theauditor/context/explain_formatter.py`

**File**: `theauditor/context/explain_formatter.py` (NEW)
**Lines**: ~250

**Imports:**
```python
from typing import Any
from theauditor.utils.code_snippets import CodeSnippetManager
```

**Class Structure:**
```python
class ExplainFormatter:
    """Format explain output for text and JSON modes.

    Output rules:
    - NO EMOJIS (Windows CP1252 compatibility)
    - Max 20 items per section (configurable)
    - Line truncation at 120 chars
    - Separator: 80x '='
    """

    SECTION_LIMIT = 20
    SEPARATOR = "=" * 80

    def __init__(self, snippet_manager: CodeSnippetManager, show_code: bool = True):
        self.snippet_manager = snippet_manager
        self.show_code = show_code

    def format_file_explain(self, data: dict) -> str:
        """Format file explain output."""
        ...

    def format_symbol_explain(self, data: dict) -> str:
        """Format symbol explain output."""
        ...

    def format_component_explain(self, data: dict) -> str:
        """Format React component explain output."""
        ...

    def _format_section(self, title: str, items: list, total: int, format_fn) -> str:
        """Format a section with limit and count."""
        ...
```

**Expected data structures (from CodeQueryEngine):**

```python
# File explain data
{
    "target": "path/to/file.ts",
    "target_type": "file",
    "symbols": [{"name": "foo", "type": "function", "line": 42, "end_line": 58, "signature": "..."}],
    "hooks": [{"hook_name": "useState", "line": 10}],
    "dependencies": [{"target": "react", "type": "import", "line": 1}],
    "dependents": [{"source": "app.ts", "type": "import", "line": 5}],
    "outgoing_calls": [{"callee_function": "bar", "line": 45, "arguments": "x, y"}],
    "incoming_calls": [{"caller_file": "app.ts", "caller_line": 20, "callee_function": "foo"}],
}

# Symbol explain data
{
    "target": "ClassName.methodName",
    "target_type": "symbol",
    "definition": {"file": "...", "line": 42, "type": "method", "signature": "..."},
    "callers": [{"file": "...", "line": 20, "caller_function": "..."}],
    "callees": [{"callee_function": "...", "line": 45}],
}
```

**Output format (text):**
```
================================================================================
EXPLAIN: path/to/file.ts
================================================================================

SYMBOLS DEFINED (5):
  1. foo (function) - line 42
        42 | function foo(x: string): number {
        43 |   return x.length;
        44 | }

  2. Bar (class) - line 60
        60 | class Bar {
        ...

REACT HOOKS (3):
  - useState (line 10)
  - useEffect (line 15)
  - useMemo (line 22)

DEPENDENCIES (12 imports):
  1. react (external)
  2. ./utils (internal) -> src/utils.ts

DEPENDENTS (3 files import this):
  1. src/app.ts:5
  2. src/index.ts:12
  (and 1 other)

OUTGOING CALLS (23):
  1. line 45: bar(x, y)
        45 | const result = bar(x, y);

INCOMING CALLS (2):
  1. src/app.ts:20 - main() calls foo
        20 | const val = foo("hello");

================================================================================
```

---

## 2. Query Engine Extensions

All changes in **File**: `theauditor/context/query.py`

### 2.1 Add `get_file_symbols()` method

**Location**: Add after `close()` method (line ~1488)

```python
def get_file_symbols(self, file_path: str, limit: int = 50) -> list[dict]:
    """Get all symbols defined in a file.

    Args:
        file_path: File path (partial match supported)
        limit: Max results

    Returns:
        List of {name, type, line, end_line, signature} dicts

    SQL (symbols table uses 'path' column):
        SELECT name, type, line, end_line, type_annotation
        FROM symbols
        WHERE path LIKE ?
        ORDER BY line
        LIMIT ?
    """
    cursor = self.repo_db.cursor()
    results = []

    for table in ['symbols', 'symbols_jsx']:
        try:
            cursor.execute(f"""
                SELECT name, type, line, end_line, type_annotation
                FROM {table}
                WHERE path LIKE ?
                ORDER BY line
                LIMIT ?
            """, (f"%{file_path}", limit))

            for row in cursor.fetchall():
                results.append({
                    'name': row['name'],
                    'type': row['type'],
                    'line': row['line'],
                    'end_line': row['end_line'] or row['line'],
                    'signature': row['type_annotation']
                })
        except sqlite3.OperationalError:
            continue

    return results[:limit]
```

### 2.2 Add `get_file_hooks()` method

**Location**: Add after `get_file_symbols()`

**CRITICAL**: Must filter for ACTUAL React hooks, not method calls!

```python
# Whitelist of actual React hooks (not method calls)
REACT_HOOK_NAMES = {
    'useState', 'useEffect', 'useCallback', 'useMemo', 'useRef',
    'useContext', 'useReducer', 'useLayoutEffect', 'useImperativeHandle',
    'useDebugValue', 'useTransition', 'useDeferredValue', 'useId',
    'useSyncExternalStore', 'useInsertionEffect',
    # Common custom hook patterns
    'useAuth', 'useForm', 'useQuery', 'useMutation', 'useSelector',
    'useDispatch', 'useNavigate', 'useParams', 'useLocation'
}

def get_file_hooks(self, file_path: str) -> list[dict]:
    """Get React hooks used in a file.

    IMPORTANT: Filters react_hooks table which contains BOTH hooks AND method calls.
    Only returns actual React hooks (useState, useEffect, etc.)

    Args:
        file_path: File path (partial match supported)

    Returns:
        List of {hook_name, line} dicts

    SQL (react_hooks table uses 'file' column):
        SELECT DISTINCT hook_name, line
        FROM react_hooks
        WHERE file LIKE ?
        ORDER BY line
    """
    cursor = self.repo_db.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT hook_name, line
            FROM react_hooks
            WHERE file LIKE ?
            ORDER BY line
        """, (f"%{file_path}",))

        results = []
        for row in cursor.fetchall():
            hook = row['hook_name']
            # Filter: only actual React hooks (starts with 'use' and in whitelist OR starts with 'use' + PascalCase)
            if hook in REACT_HOOK_NAMES or (hook.startswith('use') and len(hook) > 3 and hook[3].isupper()):
                results.append({
                    'hook_name': hook,
                    'line': row['line']
                })

        return results

    except sqlite3.OperationalError:
        return []
```

### 2.3 Add `get_file_imports()` method

**Location**: Add after `get_file_hooks()`

```python
def get_file_imports(self, file_path: str, limit: int = 50) -> list[dict]:
    """Get imports declared in a file.

    Uses refs table (NOT edges) for what THIS file imports.

    Args:
        file_path: File path (partial match)
        limit: Max results

    Returns:
        List of {module, kind, line} dicts

    SQL (refs table uses 'src' column):
        SELECT value, kind, line
        FROM refs
        WHERE src LIKE ?
        ORDER BY line
        LIMIT ?
    """
    cursor = self.repo_db.cursor()

    try:
        cursor.execute("""
            SELECT value, kind, line
            FROM refs
            WHERE src LIKE ?
            ORDER BY line
            LIMIT ?
        """, (f"%{file_path}", limit))

        return [
            {'module': row['value'], 'kind': row['kind'], 'line': row['line']}
            for row in cursor.fetchall()
        ]

    except sqlite3.OperationalError:
        return []
```

### 2.4 Add `get_file_importers()` method

**Location**: Add after `get_file_imports()`

```python
def get_file_importers(self, file_path: str, limit: int = 50) -> list[dict]:
    """Get files that import this file.

    Uses edges table in graphs.db with graph_type='import'.

    Args:
        file_path: File path (partial match)
        limit: Max results

    Returns:
        List of {source_file, type, line} dicts

    SQL (graphs.db edges table):
        SELECT source, type, line
        FROM edges
        WHERE target LIKE ? AND graph_type = 'import'
        ORDER BY source
        LIMIT ?
    """
    if not self.graph_db:
        return []

    cursor = self.graph_db.cursor()

    try:
        cursor.execute("""
            SELECT source, type, line
            FROM edges
            WHERE target LIKE ? AND graph_type = 'import'
            ORDER BY source
            LIMIT ?
        """, (f"%{file_path}%", limit))

        return [
            {'source_file': row['source'], 'type': row['type'], 'line': row['line'] or 0}
            for row in cursor.fetchall()
        ]

    except sqlite3.OperationalError:
        return []
```

### 2.5 Add `get_file_outgoing_calls()` method

**Location**: Add after `get_file_importers()`

```python
def get_file_outgoing_calls(self, file_path: str, limit: int = 50) -> list[dict]:
    """Get function calls made FROM this file.

    Args:
        file_path: File path (partial match)
        limit: Max results

    Returns:
        List of {callee_function, line, arguments, caller_function} dicts

    SQL (function_call_args uses 'file' column):
        SELECT callee_function, line, argument_expr, caller_function
        FROM function_call_args
        WHERE file LIKE ?
        ORDER BY line
        LIMIT ?
    """
    cursor = self.repo_db.cursor()
    results = []

    for table in ['function_call_args', 'function_call_args_jsx']:
        try:
            cursor.execute(f"""
                SELECT callee_function, line, argument_expr, caller_function
                FROM {table}
                WHERE file LIKE ?
                ORDER BY line
                LIMIT ?
            """, (f"%{file_path}", limit - len(results)))

            for row in cursor.fetchall():
                results.append({
                    'callee_function': row['callee_function'],
                    'line': row['line'],
                    'arguments': row['argument_expr'] or '',
                    'caller_function': row['caller_function']
                })
        except sqlite3.OperationalError:
            continue

    return results[:limit]
```

### 2.6 Add `get_file_incoming_calls()` method

**Location**: Add after `get_file_outgoing_calls()`

```python
def get_file_incoming_calls(self, file_path: str, limit: int = 50) -> list[dict]:
    """Get calls TO symbols defined in this file.

    Two-step query:
    1. Get symbol names from this file (symbols.path)
    2. Find calls to those symbols (function_call_args.callee_function)

    Args:
        file_path: File path (partial match)
        limit: Max results

    Returns:
        List of {caller_file, caller_line, caller_function, callee_function} dicts
    """
    cursor = self.repo_db.cursor()

    # Step 1: Get exported symbols from this file
    try:
        cursor.execute("""
            SELECT DISTINCT name FROM symbols
            WHERE path LIKE ? AND type IN ('function', 'class', 'method')
        """, (f"%{file_path}",))

        symbol_names = [row['name'] for row in cursor.fetchall()]

        if not symbol_names:
            return []

        # Step 2: Find calls to these symbols from OTHER files
        results = []
        for sym in symbol_names[:20]:  # Limit symbols to prevent huge queries
            for table in ['function_call_args', 'function_call_args_jsx']:
                try:
                    cursor.execute(f"""
                        SELECT file, line, caller_function, callee_function
                        FROM {table}
                        WHERE (callee_function = ? OR callee_function LIKE ?)
                          AND file NOT LIKE ?
                        ORDER BY file, line
                        LIMIT ?
                    """, (sym, f"%.{sym}", f"%{file_path}", limit - len(results)))

                    for row in cursor.fetchall():
                        results.append({
                            'caller_file': row['file'],
                            'caller_line': row['line'],
                            'caller_function': row['caller_function'],
                            'callee_function': row['callee_function']
                        })
                except sqlite3.OperationalError:
                    continue

            if len(results) >= limit:
                break

        return results[:limit]

    except sqlite3.OperationalError:
        return []
```

### 2.7 Add `get_file_context_bundle()` aggregation method

**Location**: Add after `get_file_incoming_calls()`

```python
def get_file_context_bundle(self, file_path: str, limit: int = 20) -> dict:
    """Aggregate all context for a file in one call.

    This is the main entry point for 'aud explain <file>'.

    Args:
        file_path: File path (partial match supported)
        limit: Max items per section

    Returns:
        Dict with all sections and metadata
    """
    return {
        'target': file_path,
        'target_type': 'file',
        'symbols': self.get_file_symbols(file_path, limit),
        'hooks': self.get_file_hooks(file_path),
        'imports': self.get_file_imports(file_path, limit),
        'importers': self.get_file_importers(file_path, limit),
        'outgoing_calls': self.get_file_outgoing_calls(file_path, limit),
        'incoming_calls': self.get_file_incoming_calls(file_path, limit),
    }
```

### 2.8 Add `get_symbol_context_bundle()` method

**Location**: Add after `get_file_context_bundle()`

```python
def get_symbol_context_bundle(self, symbol_name: str, limit: int = 20) -> dict:
    """Aggregate all context for a symbol in one call.

    This is the main entry point for 'aud explain <Symbol.method>'.

    Args:
        symbol_name: Symbol name (resolution applied)
        limit: Max items per section

    Returns:
        Dict with definition, callers, callees, or error dict
    """
    # Resolve symbol name
    resolved_names, error = self._resolve_symbol(symbol_name)
    if error:
        return {'error': error}

    # Get definition for first resolved name
    definitions = self.find_symbol(resolved_names[0])
    if isinstance(definitions, dict) and 'error' in definitions:
        return definitions

    definition = definitions[0] if definitions else None

    # Get callers and callees
    callers = self.get_callers(resolved_names[0], depth=1)
    if isinstance(callers, dict) and 'error' in callers:
        callers = []

    callees = self.get_callees(resolved_names[0])

    return {
        'target': symbol_name,
        'resolved_as': resolved_names,
        'target_type': 'symbol',
        'definition': {
            'file': definition.file if definition else None,
            'line': definition.line if definition else None,
            'end_line': definition.end_line if definition else None,
            'type': definition.type if definition else None,
            'signature': definition.signature if definition else None,
        } if definition else None,
        'callers': [
            {
                'file': c.caller_file,
                'line': c.caller_line,
                'caller_function': c.caller_function,
                'callee_function': c.callee_function,
            }
            for c in (callers[:limit] if isinstance(callers, list) else [])
        ],
        'callees': [
            {
                'file': c.caller_file,
                'line': c.caller_line,
                'callee_function': c.callee_function,
            }
            for c in (callees[:limit] if isinstance(callees, list) else [])
        ],
    }
```

---

## 3. CLI Command

### 3.1 Create `theauditor/commands/explain.py`

**File**: `theauditor/commands/explain.py` (NEW)
**Lines**: ~200

```python
"""Explain command - comprehensive context for files, symbols, and components.

Provides AI-optimized briefing packet for any code target in a single command.
Replaces the need to run 5-6 separate queries or read entire files.
"""

import json
import time
from pathlib import Path

import click

from theauditor.context.query import CodeQueryEngine
from theauditor.context.explain_formatter import ExplainFormatter
from theauditor.utils.code_snippets import CodeSnippetManager
from theauditor.utils.error_handler import handle_exceptions


# File extensions for auto-detection
FILE_EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx', '.py', '.rs', '.go', '.java'}


def detect_target_type(target: str, engine: CodeQueryEngine) -> str:
    """Detect whether target is a file, symbol, or component.

    Algorithm:
    1. If ends with known extension -> 'file'
    2. If contains '.' with uppercase start -> 'symbol' (Class.method)
    3. If PascalCase and in react_components -> 'component'
    4. Default -> 'symbol'
    """
    # Check file extension
    for ext in FILE_EXTENSIONS:
        if target.endswith(ext):
            return 'file'

    # Check for qualified symbol (Class.method)
    if '.' in target and target[0].isupper():
        return 'symbol'

    # Check for component (PascalCase in react_components)
    if target[0].isupper() and target[1:2].islower():
        component = engine.get_component_tree(target)
        if not isinstance(component, dict) or 'error' not in component:
            return 'component'

    return 'symbol'


@click.command()
@click.argument('target')
@click.option('--depth', default=1, type=int, help='Call graph depth (1-5, default=1)')
@click.option('--format', 'output_format', default='text',
              type=click.Choice(['text', 'json']),
              help='Output format: text (human), json (AI)')
@click.option('--section', default='all',
              type=click.Choice(['all', 'symbols', 'hooks', 'deps', 'callers', 'callees']),
              help='Show only specific section')
@click.option('--no-code', is_flag=True, help='Disable code snippets (faster)')
@click.option('--limit', default=20, type=int, help='Max items per section (default=20)')
@handle_exceptions
def explain(target, depth, output_format, section, no_code, limit):
    """Get comprehensive context about a file, symbol, or component.

    TARGET can be:

    \b
      - File path:     aud explain src/auth.ts
      - Symbol:        aud explain authenticateUser
      - Class.method:  aud explain UserController.create
      - Component:     aud explain Dashboard

    \b
    WHAT IT RETURNS:
      For files:     symbols, hooks, imports, importers, calls
      For symbols:   definition, callers, callees
      For components: info, hooks, children, props

    \b
    WHY USE THIS:
      - Single command replaces 5-6 queries
      - Includes code snippets by default
      - Saves 5,000-10,000 tokens per refactoring

    \b
    EXAMPLES:
      aud explain src/auth/service.ts
      aud explain validateInput --depth 3
      aud explain Dashboard --format json
      aud explain OrderController.create --no-code
    """
    start_time = time.perf_counter()

    root = Path.cwd()
    engine = CodeQueryEngine(root)
    snippet_manager = CodeSnippetManager(root)
    formatter = ExplainFormatter(snippet_manager, show_code=not no_code)

    try:
        # Auto-detect target type
        target_type = detect_target_type(target, engine)

        # Get context bundle based on type
        if target_type == 'file':
            data = engine.get_file_context_bundle(target, limit=limit)
            output = formatter.format_file_explain(data)
        elif target_type == 'symbol':
            data = engine.get_symbol_context_bundle(target, limit=limit)
            if 'error' in data:
                click.echo(f"Error: {data['error']}", err=True)
                return
            output = formatter.format_symbol_explain(data)
        else:  # component
            data = engine.get_component_tree(target)
            if isinstance(data, dict) and 'error' in data:
                click.echo(f"Error: {data['error']}", err=True)
                return
            data['target'] = target
            data['target_type'] = 'component'
            output = formatter.format_component_explain(data)

        # Add timing metadata
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        data['metadata'] = {'query_time_ms': round(elapsed_ms, 1)}

        # Output
        if output_format == 'json':
            click.echo(json.dumps(data, indent=2, default=str))
        else:
            click.echo(output)
            click.echo(f"\n(Query time: {elapsed_ms:.1f}ms)")

    finally:
        engine.close()
```

### 3.2 Register explain command in CLI

**File**: `theauditor/cli.py`
**Location**: Find import section (~line 20-40), add:

```python
from theauditor.commands import explain
```

**Location**: Find command registration section (~line 50-80), add:

```python
cli.add_command(explain.explain)
```

---

## 4. Query Command Enhancement

### 4.1 Add `--show-code` flag to query command

**File**: `theauditor/commands/query.py`

**Add import** (top of file):
```python
from theauditor.utils.code_snippets import CodeSnippetManager
```

**Add option** (after line ~45, with other options):
```python
@click.option("--show-code", is_flag=True, help="Include source code snippets for callers/callees")
```

**Modify function signature** (line ~48):
```python
def query(symbol, file, api, component, variable, pattern, category, search, list_mode,
          list_symbols, symbol_filter, path_filter,
          show_callers, show_callees, show_dependencies, show_dependents,
          show_tree, show_hooks, show_data_deps, show_flow, show_taint_flow,
          show_api_coverage, type_filter, include_tables,
          depth, output_format, save, show_code):  # Added show_code
```

**Add snippet manager initialization** (after engine initialization):
```python
if show_code:
    snippet_manager = CodeSnippetManager(Path.cwd())
else:
    snippet_manager = None
```

**Modify caller formatting** (in the show_callers output section):
```python
# Before (existing):
for i, caller in enumerate(callers, 1):
    click.echo(f"  {i}. {caller.caller_file}:{caller.caller_line}")
    click.echo(f"     {caller.caller_function} -> {caller.callee_function}")

# After (with show_code):
for i, caller in enumerate(callers, 1):
    click.echo(f"  {i}. {caller.caller_file}:{caller.caller_line}")
    click.echo(f"     {caller.caller_function} -> {caller.callee_function}")
    if show_code and snippet_manager:
        snippet = snippet_manager.get_snippet(caller.caller_file, caller.caller_line, expand_block=False)
        click.echo(f"     Code: {snippet.split('|', 1)[1].strip() if '|' in snippet else snippet}")
```

---

## 5. Agent Updates

### 5.1 Update planning agent

**File**: `agents/planning.md`
**Location**: Add as new first step in workflow

```markdown
**Step 0: Context Gathering**
Before planning any changes, gather comprehensive context:

1. Run `aud explain <target>` for each file/symbol being modified
   - For files: `aud explain src/auth/service.ts`
   - For symbols: `aud explain validateInput`
   - This provides symbols, hooks, dependencies, callers, callees in ONE command

2. Only read files directly if explain output is insufficient
   - Prefer: `aud explain file.ts` (structured, token-efficient)
   - Avoid: Reading entire files (burns context)
```

### 5.2 Update refactor agent

**File**: `agents/refactor.md`
**Location**: Add as new first step in workflow

```markdown
**Step 0: Understand Before Modifying**
Before editing any file:

1. Run `aud explain <file>` to understand:
   - What symbols are defined
   - What this file imports
   - Who imports this file (impact of changes)
   - What functions are called (dependencies)
   - Who calls functions here (clients to update)

2. Run `aud explain <Symbol.method>` for specific function changes:
   - See all callers before changing signature
   - See all callees before removing functionality

3. Only then proceed with modifications
```

---

## 6. Testing

### 6.1 Create `tests/test_code_snippets.py`

**File**: `tests/test_code_snippets.py` (NEW)

```python
"""Tests for CodeSnippetManager."""
import pytest
from pathlib import Path
from theauditor.utils.code_snippets import CodeSnippetManager


@pytest.fixture
def snippet_manager(tmp_path):
    """Create snippet manager with test files."""
    # Create test file
    test_file = tmp_path / "test.py"
    test_file.write_text("""def foo():
    x = 1
    if x > 0:
        return x
    return 0
""")
    return CodeSnippetManager(tmp_path)


def test_get_snippet_simple_line(snippet_manager, tmp_path):
    snippet = snippet_manager.get_snippet("test.py", 1, expand_block=False)
    assert "def foo():" in snippet
    assert "1 |" in snippet


def test_get_snippet_block_expansion(snippet_manager, tmp_path):
    snippet = snippet_manager.get_snippet("test.py", 3, expand_block=True)
    assert "if x > 0:" in snippet
    assert "return x" in snippet


def test_missing_file(snippet_manager):
    snippet = snippet_manager.get_snippet("nonexistent.py", 1)
    assert "[File not found" in snippet


def test_cache_reuse(snippet_manager, tmp_path):
    # Access same file twice
    snippet_manager.get_snippet("test.py", 1)
    snippet_manager.get_snippet("test.py", 2)
    # Should only have one entry in cache
    assert len(snippet_manager._cache) == 1
```

### 6.2 Create `tests/test_explain_command.py`

**File**: `tests/test_explain_command.py` (NEW)

```python
"""Integration tests for explain command."""
import pytest
from click.testing import CliRunner
from theauditor.commands.explain import explain, detect_target_type


def test_detect_target_type_file():
    # Mock engine not needed for file detection
    assert detect_target_type("src/auth.ts", None) == 'file'
    assert detect_target_type("app.py", None) == 'file'


def test_explain_command_help():
    runner = CliRunner()
    result = runner.invoke(explain, ['--help'])
    assert result.exit_code == 0
    assert 'comprehensive context' in result.output.lower()
```

---

## 7. Documentation

### 7.1 Update CLAUDE.md

**File**: `CLAUDE.md`
**Location**: Add to "Common CLI Commands" section

```markdown
# Code Context (AI-Optimized)
aud explain <target>           # Comprehensive context for file/symbol/component
aud explain file.ts            # Symbols, hooks, deps, callers, callees
aud explain Symbol.method      # Definition, callers, callees with code
aud explain --format json      # JSON output for AI consumption
aud query --symbol X --show-code  # Query with code snippets
```

---

## 8. Validation Checklist

- [ ] 8.1 `aud explain theauditor/cli.py` returns symbols, deps, callers (no errors)
- [ ] 8.2 `aud explain CodeQueryEngine.find_symbol` returns definition, callers, callees
- [ ] 8.3 `aud explain --format json theauditor/cli.py` returns valid JSON
- [ ] 8.4 Output contains NO emojis (grep for unicode > 127)
- [ ] 8.5 Response time <100ms for file with <50 symbols
- [ ] 8.6 `pytest tests/test_code_snippets.py tests/test_explain_command.py -v` passes
- [ ] 8.7 `aud query --symbol foo --show-callers --show-code` shows code snippets
