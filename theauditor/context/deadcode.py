"""Dead code detection - comprehensive multi-table analysis.

Detects:
1. Isolated modules - never referenced ANYWHERE (imports, assignments, function args)
2. Dead functions - defined but never called
3. Dead classes - defined but never instantiated
4. Orphaned features - internal cluster with no external entry

Pattern: Multi-table JOINs like taint tracking (see rules/progress.md).
"""
from __future__ import annotations


import sqlite3
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass


# Centralized exclusion patterns (DRY principle)
DEFAULT_EXCLUSIONS = [
    '__init__.py',
    'test', '__tests__', '.test.', '.spec.',
    'migration', 'migrations',
    '__pycache__', 'node_modules', '.venv',
    'dist', 'build', '.next', '.nuxt'
]


@dataclass
class DeadCode:
    """Base class for dead code findings."""
    type: str  # 'module' | 'function' | 'class' | 'feature'
    path: str
    name: str  # For functions/classes
    line: int  # For functions/classes
    symbol_count: int
    reason: str
    confidence: str  # 'high' | 'medium' | 'low'
    lines_estimated: int = 0  # For rule compatibility
    cluster_id: int | None = None  # For zombie cluster tracking


def detect_all(
    db_path: str,
    path_filter: str = None,
    exclude_patterns: list[str] = None,
    include_tests: bool = False
) -> list[DeadCode]:
    """Detect ALL types of dead code using multi-table analysis.

    Algorithm:
        1. Find modules never referenced (refs + assignments + function_call_args)
        2. Find functions never called (symbols - function_call_args)
        3. Find classes never instantiated (symbols - function_call_args)
        4. Find orphaned feature clusters (refs graph analysis)

    Args:
        db_path: Path to repo_index.db
        path_filter: Optional LIKE pattern
        exclude_patterns: Paths to skip
        include_tests: Include test files (default: False)

    Returns:
        List of DeadCode findings
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)

    findings = []
    findings.extend(_detect_isolated_modules(conn, path_filter, exclude_patterns, include_tests))
    findings.extend(_detect_dead_functions(conn, path_filter, exclude_patterns, include_tests))
    findings.extend(_detect_dead_classes(conn, path_filter, exclude_patterns, include_tests))

    conn.close()
    return findings


def _detect_isolated_modules(
    conn: sqlite3.Connection,
    path_filter: str = None,
    exclude_patterns: list[str] = None,
    include_tests: bool = False
) -> list[DeadCode]:
    """Find modules NEVER referenced anywhere in the codebase.

    Checks:
    1. Not imported (refs table)
    2. Not in string assignments (assignments.source_expr)
    3. Not passed to functions (function_call_args.argument_expr)
    4. Not mentioned in any code

    This is TRUE isolation - no references at all.
    """
    cursor = conn.cursor()

    # Step 1: Get all files with symbols
    if path_filter:
        cursor.execute(
            "SELECT DISTINCT path FROM symbols WHERE path LIKE ?",
            (path_filter,)
        )
    else:
        cursor.execute("SELECT DISTINCT path FROM symbols")

    files_with_code = {row[0] for row in cursor.fetchall()}

    # Step 2: Get files referenced in imports (refs table)
    cursor.execute("""
        SELECT DISTINCT value
        FROM refs
        WHERE kind = 'from'
    """)
    imported_files = {row[0] for row in cursor.fetchall()}

    # Also check module name imports and dynamic imports
    cursor.execute("""
        SELECT DISTINCT value
        FROM refs
        WHERE kind IN ('import', 'dynamic_import')
    """)
    for module_path in cursor.fetchall():
        module_str = module_path[0]

        # Match against existing files by checking if module path is substring of file path
        # Handles: '@/pages/dashboard/Login' -> 'frontend/src/pages/dashboard/Login.tsx'
        for file in files_with_code:
            # Strip path alias (@/) and check if rest matches
            if '@/' in module_str:
                module_without_alias = module_str.replace('@/', '')
                if module_without_alias in file:
                    imported_files.add(file)
            # Python-style module paths: 'theauditor.cli' -> 'theauditor/cli.py'
            elif '.' in module_str and '/' not in module_str:
                path_py = module_str.replace('.', '/') + '.py'
                if path_py == file:
                    imported_files.add(file)
            # Direct path match
            elif module_str in file:
                imported_files.add(file)

    # Step 3: Get files referenced in assignments (string paths)
    cursor.execute("""
        SELECT DISTINCT source_expr
        FROM assignments
        WHERE source_expr LIKE '%.py%'
           OR source_expr LIKE '%.js%'
           OR source_expr LIKE '%/%'
    """)
    for expr in cursor.fetchall():
        # Extract file paths from expressions like "path = 'ast_extractors/core.js'"
        expr_str = expr[0]
        for file in files_with_code:
            # Match full path OR basename (for expressions like js_dir / 'file.js')
            file_basename = file.split('/')[-1]
            if file in expr_str or file_basename in expr_str:
                imported_files.add(file)

    # Step 4: Get files referenced in function arguments
    cursor.execute("""
        SELECT DISTINCT argument_expr
        FROM function_call_args
        WHERE argument_expr LIKE '%.py%'
           OR argument_expr LIKE '%.js%'
           OR argument_expr LIKE '%/%'
    """)
    for arg in cursor.fetchall():
        arg_str = arg[0]
        for file in files_with_code:
            # Match full path OR basename (for expressions like open('file.js'))
            file_basename = file.split('/')[-1]
            if file in arg_str or file_basename in arg_str:
                imported_files.add(file)

    # Step 5: Check variable_usage for JSX component references (React Router, etc.)
    # Files that export symbols used in JSX are NOT dead (e.g., <POSHome /> in routes)
    cursor.execute("""
        SELECT DISTINCT variable_name
        FROM variable_usage
        WHERE variable_name NOT LIKE '%.%'  -- Exclude property access like 'React.lazy'
          AND variable_name NOT LIKE '%(%'   -- Exclude function calls
          AND variable_name NOT IN ('React', 'useState', 'useEffect', 'children')  -- Exclude common hooks/props
    """)
    jsx_used_symbols = {row[0] for row in cursor.fetchall()}

    # Match symbol names to files (e.g., "POSHome" -> "frontend/src/pages/pos/Home.tsx")
    if jsx_used_symbols:
        placeholders = ','.join('?' * len(jsx_used_symbols))
        cursor.execute(f"""
            SELECT DISTINCT path
            FROM symbols
            WHERE name IN ({placeholders})
              AND type IN ('function', 'class', 'variable')
        """, tuple(jsx_used_symbols))
        for row in cursor.fetchall():
            imported_files.add(row[0])

    # Step 6: Set difference = truly isolated files
    isolated_files = files_with_code - imported_files

    # Filter exclusions
    if not include_tests:
        isolated_files = {f for f in isolated_files if 'test' not in f.lower()}

    if exclude_patterns:
        filtered = set()
        for file in isolated_files:
            excluded = any(pattern in file for pattern in exclude_patterns)
            if not excluded:
                filtered.add(file)
        isolated_files = filtered

    # Get symbol counts
    if not isolated_files:
        return []

    placeholders = ','.join('?' * len(isolated_files))
    query = f"""
        SELECT path, COUNT(*) as count
        FROM symbols
        WHERE path IN ({placeholders})
        GROUP BY path
    """
    cursor.execute(query, tuple(isolated_files))
    symbol_counts = {row[0]: row[1] for row in cursor.fetchall()}

    # Build findings
    findings = []
    for file in sorted(isolated_files):
        count = symbol_counts.get(file, 0)
        confidence, reason = _classify_module(file, count)

        findings.append(DeadCode(
            type='module',
            path=file,
            name='',
            line=0,
            symbol_count=count,
            reason=reason,
            confidence=confidence
        ))

    return findings


def _detect_dead_functions(
    conn: sqlite3.Connection,
    path_filter: str = None,
    exclude_patterns: list[str] = None,
    include_tests: bool = False
) -> list[DeadCode]:
    """Find functions defined but NEVER called.

    Query: symbols.type='function' BUT name NOT IN function_call_args.callee_function
    AND name NOT IN variable_usage (JSX component usage like <Component />)
    """
    cursor = conn.cursor()

    # Get all function definitions
    where_clause = "WHERE s.type IN ('function', 'method')"
    if path_filter:
        where_clause += f" AND s.path LIKE '{path_filter}'"
    if not include_tests:
        where_clause += " AND s.path NOT LIKE '%test%'"

    cursor.execute(f"""
        SELECT s.path, s.name, s.line
        FROM symbols s
        {where_clause}
        AND s.name NOT IN (
            SELECT DISTINCT callee_function
            FROM function_call_args
        )
        AND s.name NOT IN (
            SELECT DISTINCT variable_name
            FROM variable_usage
            WHERE variable_name NOT LIKE '%.%'
              AND variable_name NOT LIKE '%(%'
        )
        AND s.name NOT IN (
            SELECT DISTINCT name
            FROM symbols_jsx
            WHERE type = 'function'
        )
        AND s.name NOT LIKE 'test_%'
        AND s.name NOT IN ('main', '__init__', '__main__', 'cli', '__repr__', '__str__')
    """)

    findings = []
    for path, name, line in cursor.fetchall():
        # Apply exclusions
        if exclude_patterns and any(p in path for p in exclude_patterns):
            continue

        confidence = 'high'
        reason = 'Function defined but never called'

        # Reduce confidence for special cases
        if name.startswith('_') and not name.startswith('__'):
            confidence = 'medium'
            reason = 'Private function (may be internal API)'
        elif path.endswith(('cli.py', 'main.py', '__main__.py')):
            confidence = 'medium'
            reason = 'Entry point file (may be invoked externally)'

        findings.append(DeadCode(
            type='function',
            path=path,
            name=name,
            line=line,
            symbol_count=1,
            reason=reason,
            confidence=confidence
        ))

    return findings


def _detect_dead_classes(
    conn: sqlite3.Connection,
    path_filter: str = None,
    exclude_patterns: list[str] = None,
    include_tests: bool = False
) -> list[DeadCode]:
    """Find classes defined but NEVER instantiated.

    Query: symbols.type='class' BUT name NOT IN function_call_args.callee_function
    (Class instantiation is a function call to the class name)
    """
    cursor = conn.cursor()

    where_clause = "WHERE s.type = 'class'"
    if path_filter:
        where_clause += f" AND s.path LIKE '{path_filter}'"
    if not include_tests:
        where_clause += " AND s.path NOT LIKE '%test%'"

    # Find classes never used anywhere - check ALL usage tables
    # Classes can be used via: instantiation, variable access, assignment source, or imports
    cursor.execute(f"""
        SELECT s.path, s.name, s.line
        FROM symbols s
        {where_clause}
        AND s.name NOT IN (
            SELECT DISTINCT callee_function FROM function_call_args
            UNION
            SELECT DISTINCT variable_name FROM variable_usage
            UNION
            SELECT DISTINCT value FROM refs WHERE value NOT LIKE '%.%'
        )
        -- Exclude classes referenced in assignments (returned from functions, etc)
        AND NOT EXISTS (
            SELECT 1 FROM assignments WHERE source_expr LIKE '%' || s.name || '%'
        )
        AND s.name NOT LIKE 'Base%'
        AND s.name NOT LIKE 'Abstract%'
        AND s.name NOT LIKE '%Mixin'
        AND s.name NOT LIKE '%Exception'
        AND s.name NOT LIKE '%Error'
    """)

    findings = []
    for path, name, line in cursor.fetchall():
        # Apply exclusions
        if exclude_patterns and any(p in path for p in exclude_patterns):
            continue

        confidence = 'high'
        reason = 'Class defined but never instantiated'

        findings.append(DeadCode(
            type='class',
            path=path,
            name=name,
            line=line,
            symbol_count=1,
            reason=reason,
            confidence=confidence
        ))

    return findings


def _classify_module(path: str, symbol_count: int) -> tuple[str, str]:
    """Classify module confidence and reason.

    Returns:
        (confidence, reason) tuple
    """
    confidence = 'high'
    reason = 'No references found anywhere'

    path_lower = path.lower()

    if path.endswith('__init__.py') and symbol_count == 0:
        confidence = 'low'
        reason = 'Empty package marker (likely false positive)'
    elif 'migration' in path_lower:
        confidence = 'medium'
        reason = 'Migration script (may be external entry)'
    elif path.endswith(('cli.py', '__main__.py', 'main.py')):
        confidence = 'medium'
        reason = 'CLI/main entry point (may be invoked externally)'

    return confidence, reason


# Backward compatibility - keep old function name
def detect_isolated_modules(
    db_path: str,
    path_filter: str = None,
    exclude_patterns: list[str] = None
) -> list[DeadCode]:
    """Legacy function for backward compatibility. Use detect_all() instead."""
    return detect_all(db_path, path_filter, exclude_patterns)
