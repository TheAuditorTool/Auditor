"""Database operations for taint analysis.

This module contains all database query functions used by the taint analyzer.

Schema Contract:
    All queries use build_query() for schema compliance.
    Table existence is guaranteed by schema contract - no checks needed.
"""

import sys
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from theauditor.indexer.schema import build_query
from .sources import TAINT_SOURCES, SECURITY_SINKS


def find_taint_sources(cursor: sqlite3.Cursor, sources_dict: Optional[Dict[str, List[str]]] = None,
                      cache: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Find all occurrences of taint sources in the codebase.

    CRITICAL: This function REQUIRES symbols table to have call/property types.
    Query: SELECT * FROM symbols WHERE type IN ('call', 'property')

    If this returns empty:
      1. Verify indexer extracted call/property symbols
      2. Run: aud index
      3. Check symbols table: SELECT COUNT(*) FROM symbols WHERE type='property'
      4. DO NOT add fallback logic - fix the indexer

    With cache: O(1) lookups, no queries
    Without cache: Falls back to disk-based queries

    Args:
        cursor: Database cursor
        sources_dict: Optional dictionary of sources to use instead of global TAINT_SOURCES
        cache: Optional MemoryCache for optimized lookups

    Returns:
        List of source occurrences found in the codebase
    """
    # Check if cache is available and use it for O(1) lookups
    if cache and hasattr(cache, 'find_taint_sources_cached'):
        return cache.find_taint_sources_cached(sources_dict)

    # FALLBACK: Disk-based implementation
    sources = []

    # Use provided sources or default to global
    sources_to_use = sources_dict if sources_dict is not None else TAINT_SOURCES

    # Combine all source patterns
    all_sources = []
    for source_list in sources_to_use.values():
        all_sources.extend(source_list)

    # Query for each source pattern
    for source_pattern in all_sources:
        # Handle dot notation (e.g., req.body)
        if "." in source_pattern:
            base, attr = source_pattern.rsplit(".", 1)
            # Look for attribute access patterns - property accesses AND calls
            query = build_query('symbols', ['path', 'name', 'line', 'col'],
                where="(type = 'call' OR type = 'property' OR type = 'symbol') AND name LIKE ?",
                order_by="path, line"
            )
            cursor.execute(query, (f"%{source_pattern}%",))
        else:
            # Look for simple function calls and symbols
            query = build_query('symbols', ['path', 'name', 'line', 'col'],
                where="(type = 'call' OR type = 'symbol') AND name = ?",
                order_by="path, line"
            )
            cursor.execute(query, (source_pattern,))

        for row in cursor.fetchall():
            sources.append({
                "file": row[0].replace("\\", "/"),  # Normalize path separators
                "name": row[1],
                "line": row[2],
                "column": row[3],
                "pattern": source_pattern,
                "type": "source"
            })

    # HARD FAILURE CHECK: If symbols query returned nothing, verify database state
    if not sources:
        import sys
        print(f"[TAINT] WARNING: Found 0 taint sources", file=sys.stderr)
        print(f"[TAINT] Checked {len(all_sources)} patterns", file=sys.stderr)

        # Verify symbols table has call/property types
        prop_query = build_query('symbols', ['name'],
            where="type='property'"
        )
        cursor.execute(prop_query)
        prop_count = len(cursor.fetchall())

        call_query = build_query('symbols', ['name'],
            where="type='call'"
        )
        cursor.execute(call_query)
        call_count = len(cursor.fetchall())

        print(f"[TAINT] Symbols table: {call_count} calls, {prop_count} properties", file=sys.stderr)

        if call_count == 0 and prop_count == 0:
            print(f"[TAINT] ERROR: Indexer did not extract call/property symbols", file=sys.stderr)
            print(f"[TAINT] Run: aud index", file=sys.stderr)
            print(f"[TAINT] This is a CRITICAL failure - taint analysis impossible", file=sys.stderr)
            raise RuntimeError("Taint analysis impossible: No call/property symbols in database. Run 'aud index' first.")

    # P2 Enhancement: Add API endpoint context for prioritization
    sources = enhance_sources_with_api_context(cursor, sources)

    return sources


def enhance_sources_with_api_context(
    cursor: sqlite3.Cursor,
    sources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Enhance taint sources with API endpoint context for prioritization.

    Maps taint sources (req.body, req.query) to their API endpoint definitions
    to provide attack surface context (public vs authenticated endpoints).

    This allows prioritization of taint analysis on public API endpoints which
    represent higher risk as they are accessible without authentication.

    Args:
        cursor: Database cursor
        sources: List of taint sources from find_taint_sources()

    Returns:
        Enhanced sources with API endpoint metadata

    Schema Contract:
        Queries api_endpoints table (guaranteed to exist)
    """
    # Build endpoint lookup map indexed by file
    query = build_query('api_endpoints',
        ['file', 'line', 'method', 'path', 'has_auth', 'handler_function']
    )
    cursor.execute(query)

    endpoints_by_file = defaultdict(list)
    for file, line, method, path, has_auth, handler in cursor.fetchall():
        endpoints_by_file[file].append({
            'line': line,
            'method': method,
            'path': path,
            'has_auth': has_auth,
            'handler': handler
        })

    # Enhance sources with endpoint context
    for source in sources:
        file = source['file']
        line = source['line']

        if file in endpoints_by_file:
            # Find closest endpoint (within 50 lines)
            closest_endpoint = None
            min_distance = float('inf')

            for endpoint in endpoints_by_file[file]:
                distance = abs(endpoint['line'] - line)
                if distance < min_distance and distance < 50:
                    min_distance = distance
                    closest_endpoint = endpoint

            if closest_endpoint:
                source['api_context'] = {
                    'method': closest_endpoint['method'],
                    'path': closest_endpoint['path'],
                    'has_auth': closest_endpoint['has_auth'],
                    'handler': closest_endpoint['handler'],
                    'attack_surface': 'public' if not closest_endpoint['has_auth'] else 'authenticated'
                }

    return sources


def find_security_sinks(cursor: sqlite3.Cursor, sinks_dict: Optional[Dict[str, List[str]]] = None,
                       cache: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Find all occurrences of security sinks in the codebase.

    MULTI-TABLE STRATEGY (Phase 3.2 Rewrite):
    - SQL sinks: Query sql_queries + orm_queries tables (has query_text metadata)
    - Command sinks: Query function_call_args (has argument data)
    - XSS sinks: Query react_hooks + function_call_args (has dependencies + arguments)
    - Path sinks: Query function_call_args (has path arguments)
    - Fallback: Query symbols table for call types

    With cache: O(1) lookups, no queries
    Without cache: Multi-table database queries

    Args:
        cursor: Database cursor
        sinks_dict: Optional dictionary of sinks to use instead of global SECURITY_SINKS
        cache: Optional MemoryCache for optimized lookups

    Returns:
        List of sink occurrences with rich metadata (query_text, arguments, dependencies)
    """
    # Check if cache is available and use it for O(1) lookups
    if cache and hasattr(cache, 'find_security_sinks_cached'):
        return cache.find_security_sinks_cached(sinks_dict)

    # MULTI-TABLE QUERY IMPLEMENTATION
    sinks = []

    # Use provided sinks or default to global
    sinks_to_use = sinks_dict if sinks_dict is not None else SECURITY_SINKS

    # Build category-specific sink sets for O(1) lookups
    sql_sinks = frozenset(sinks_to_use.get('sql', []))
    command_sinks = frozenset(sinks_to_use.get('command', []))
    xss_sinks = frozenset(sinks_to_use.get('xss', []))
    path_sinks = frozenset(sinks_to_use.get('path', []))
    ldap_sinks = frozenset(sinks_to_use.get('ldap', []))
    nosql_sinks = frozenset(sinks_to_use.get('nosql', []))

    # STRATEGY 1: Query sql_queries table for SQL sinks (P2 ENHANCED)
    # Schema: file_path, line_number, query_text, command, tables, extraction_source
    # Analyzes query structure to detect SQL injection risk factors
    # Schema Contract: sql_queries table guaranteed to exist
    if sql_sinks:
        query = build_query('sql_queries',
            ['file_path', 'line_number', 'query_text', 'command', 'tables', 'extraction_source'],
            where="query_text IS NOT NULL AND query_text != '' AND command != 'UNKNOWN'",
            order_by="file_path, line_number"
        )
        cursor.execute(query)

        for file_path, line_number, query_text, command, tables, extraction_source in cursor.fetchall():
            # Analyze query for SQL injection risk factors
            risk_factors = []
            risk_level = "low"

            # Check for string concatenation (high risk)
            if any(indicator in query_text for indicator in ['+', '${', '`${', 'f"', "f'"]):
                risk_factors.append("string_concatenation")
                risk_level = "high"

            # Check for parameterized queries (low risk)
            elif any(indicator in query_text for indicator in ['?', '$1', ':param', '@param']):
                risk_factors.append("parameterized")
                risk_level = "low"
            else:
                # Uncertain - treat as medium risk
                risk_level = "medium"

            # Extract function/method name from query context
            func_query = build_query('symbols', ['name'],
                where="path = ? AND line = ? AND type = 'call'",
                order_by="col DESC",
                limit=1
            )
            cursor.execute(func_query, (file_path, line_number))

            func_result = cursor.fetchone()
            func_name = func_result[0] if func_result else 'execute'

            # Match against SQL sink patterns
            matched_pattern = None
            for pattern in sql_sinks:
                if pattern in func_name or func_name in pattern:
                    matched_pattern = pattern
                    break

            if matched_pattern:
                sinks.append({
                    "file": file_path.replace("\\", "/"),
                    "name": func_name,
                    "line": line_number,
                    "column": 0,
                    "pattern": matched_pattern,
                    "category": "sql",
                    "type": "sink",
                    "metadata": {
                        "query_text": query_text[:200],  # Truncate for readability
                        "command": command,
                        "tables": tables,
                        "risk_level": risk_level,
                        "risk_factors": risk_factors,
                        "extraction_source": extraction_source,
                        "table": "sql_queries"
                    }
                })

    # STRATEGY 2: Query orm_queries table for ORM sinks (P2 ENHANCED)
    # Schema: file, line, query_type, includes, has_limit, has_transaction
    # Classifies ORM operations by risk level based on operation type and safeguards
    # Schema Contract: orm_queries table guaranteed to exist
    if sql_sinks:
        query = build_query('orm_queries',
            ['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'],
            where="query_type IS NOT NULL",
            order_by="file, line"
        )
        cursor.execute(query)

        for file, line, query_type, includes, has_limit, has_transaction in cursor.fetchall():
            # Classify risk level based on ORM operation type
            risk_level = "medium"

            # High-risk operations (write operations without transactions)
            if query_type in ['create', 'update', 'delete', 'destroy'] and not has_transaction:
                risk_level = "high"

            # Medium-risk operations (read operations without limits)
            elif query_type in ['findOne', 'findAll', 'find'] and not has_limit:
                risk_level = "medium"

            # Low-risk operations (reads with limits, transactional writes)
            else:
                risk_level = "low"

            # ORM operations are implicit SQL sinks
            sinks.append({
                "file": file.replace("\\", "/"),
                "name": query_type,
                "line": line,
                "column": 0,
                "pattern": query_type,
                "category": "sql",
                "type": "sink",
                "metadata": {
                    "query_type": query_type,
                    "includes": includes,
                    "risk_level": risk_level,
                    "has_limit": has_limit,
                    "has_transaction": has_transaction,
                    "table": "orm_queries"
                }
            })

    # STRATEGY 3: Query function_call_args for command execution sinks
    # Schema Contract: function_call_args table guaranteed to exist
    if command_sinks:
        for pattern in command_sinks:
            query = build_query('function_call_args',
                ['file', 'line', 'callee_function', 'argument_expr'],
                where="callee_function LIKE ? OR callee_function = ?",
                order_by="file, line"
            )
            cursor.execute(query, (f"%{pattern}%", pattern))

            for file, line, callee_func, arg_expr in cursor.fetchall():
                sinks.append({
                    "file": file.replace("\\", "/"),
                    "name": callee_func,
                    "line": line,
                    "column": 0,
                    "pattern": pattern,
                    "category": "command",
                    "type": "sink",
                    "metadata": {
                        "arguments": arg_expr[:200] if arg_expr else "",
                        "table": "function_call_args"
                    }
                })

    # STRATEGY 4: Query react_hooks for XSS vulnerabilities (P2 ENHANCED)
    # Schema: file, line, component_name, hook_name, dependency_array, dependency_vars, callback_body
    # Detects DOM manipulation in hooks with external dependencies
    # Schema Contract: react_hooks table guaranteed to exist
    if xss_sinks:
        # Query hooks that depend on external data (potential XSS vectors)
        query = build_query('react_hooks',
            ['file', 'line', 'component_name', 'hook_name', 'dependency_vars', 'callback_body'],
            where="""hook_name IN ('useEffect', 'useLayoutEffect', 'useMemo', 'useCallback')
            AND (
                dependency_vars LIKE '%props%' OR
                dependency_vars LIKE '%state%' OR
                dependency_vars LIKE '%data%' OR
                dependency_vars LIKE '%response%' OR
                callback_body LIKE '%innerHTML%' OR
                callback_body LIKE '%dangerouslySetInnerHTML%' OR
                callback_body LIKE '%document.write%'
            )""",
            order_by="file, line"
        )
        cursor.execute(query)

        for file, line, component, hook, deps, body in cursor.fetchall():
            # Detect DOM manipulation in hook callbacks
            xss_risk = False
            risk_reason = []

            if body and 'innerHTML' in body:
                xss_risk = True
                risk_reason.append('innerHTML usage')

            if body and 'dangerouslySetInnerHTML' in body:
                xss_risk = True
                risk_reason.append('dangerouslySetInnerHTML')

            if body and 'document.write' in body:
                xss_risk = True
                risk_reason.append('document.write')

            if xss_risk:
                sinks.append({
                    "file": file.replace("\\", "/"),
                    "name": f"{hook} in {component}",
                    "line": line,
                    "column": 0,
                    "pattern": hook,
                    "category": "xss",
                    "type": "sink",
                    "metadata": {
                        "hook": hook,
                        "component": component,
                        "dependencies": deps,
                        "risk_factors": risk_reason,
                        "table": "react_hooks"
                    }
                })

    # STRATEGY 5: Query function_call_args for XSS sinks (res.send, res.render, etc.)
    # Schema Contract: function_call_args table guaranteed to exist
    if xss_sinks:
        for pattern in xss_sinks:
            if pattern == 'dangerouslySetInnerHTML':
                continue  # Already handled in react_hooks

            query = build_query('function_call_args',
                ['file', 'line', 'callee_function', 'argument_expr'],
                where="callee_function LIKE ? OR callee_function = ?",
                order_by="file, line"
            )
            cursor.execute(query, (f"%{pattern}%", pattern))

            for file, line, callee_func, arg_expr in cursor.fetchall():
                sinks.append({
                    "file": file.replace("\\", "/"),
                    "name": callee_func,
                    "line": line,
                    "column": 0,
                    "pattern": pattern,
                    "category": "xss",
                    "type": "sink",
                    "metadata": {
                        "arguments": arg_expr[:200] if arg_expr else "",
                        "table": "function_call_args"
                    }
                })

    # STRATEGY 6: Query function_call_args for path traversal sinks
    # Schema Contract: function_call_args table guaranteed to exist
    if path_sinks:
        for pattern in path_sinks:
            query = build_query('function_call_args',
                ['file', 'line', 'callee_function', 'argument_expr'],
                where="callee_function LIKE ? OR callee_function = ?",
                order_by="file, line"
            )
            cursor.execute(query, (f"%{pattern}%", pattern))

            for file, line, callee_func, arg_expr in cursor.fetchall():
                sinks.append({
                    "file": file.replace("\\", "/"),
                    "name": callee_func,
                    "line": line,
                    "column": 0,
                    "pattern": pattern,
                    "category": "path",
                    "type": "sink",
                    "metadata": {
                        "path_argument": arg_expr[:200] if arg_expr else "",
                        "table": "function_call_args"
                    }
                })

    # STRATEGY 7: Fallback to symbols table for any remaining sinks
    # This catches sinks not found in specialized tables
    all_sinks = []
    sink_categories = {}
    for category, sink_list in sinks_to_use.items():
        for sink in sink_list:
            all_sinks.append(sink)
            sink_categories[sink] = category

    # Get already found sink locations to avoid duplicates
    found_locations = {(s['file'], s['line'], s['pattern']) for s in sinks}

    for sink_pattern in all_sinks:
        # CRITICAL FIX: Handle chained method patterns like "res.status().json"
        if '().' in sink_pattern:
            # Decompose pattern: "res.status().json" → "res.status" + "json"
            parts = sink_pattern.replace('().', '.').split('.')
            base_method = '.'.join(parts[:-1])
            final_method = parts[-1]

            # NOTE: This query uses EXISTS subquery which build_query() doesn't support yet
            # Using raw SQL with proper column selection from schema
            query = """
                SELECT DISTINCT a.path, a.line, a.col
                FROM symbols a
                WHERE a.type = 'call'
                AND (a.name = ? OR a.name LIKE ?)
                AND EXISTS (
                    SELECT 1 FROM symbols b
                    WHERE b.path = a.path
                    AND b.line = a.line
                    AND b.type = 'call'
                    AND (b.name LIKE ? OR b.name = ?)
                )
                ORDER BY a.path, a.line
            """
            cursor.execute(query, (final_method, f"%.{final_method}", f"%{base_method}%", base_method))

            for row in cursor.fetchall():
                file = row[0].replace("\\", "/")
                line = row[1]

                # Skip if already found in specialized tables
                if (file, line, sink_pattern) in found_locations:
                    continue

                sinks.append({
                    "file": file,
                    "name": sink_pattern,
                    "line": line,
                    "column": row[2],
                    "pattern": sink_pattern,
                    "category": sink_categories.get(sink_pattern, ""),
                    "type": "sink",
                    "metadata": {
                        "table": "symbols"
                    }
                })
        else:
            query = build_query('symbols', ['path', 'name', 'line', 'col'],
                where="type = 'call' AND (name = ? OR name LIKE ?)",
                order_by="path, line"
            )
            cursor.execute(query, (sink_pattern, f"%.{sink_pattern}"))

            for row in cursor.fetchall():
                file = row[0].replace("\\", "/")
                line = row[2]

                # Skip if already found in specialized tables
                if (file, line, sink_pattern) in found_locations:
                    continue

                sinks.append({
                    "file": file,
                    "name": row[1],
                    "line": line,
                    "column": row[3],
                    "pattern": sink_pattern,
                    "category": sink_categories.get(sink_pattern, ""),
                    "type": "sink",
                    "metadata": {
                        "table": "symbols"
                    }
                })

    # HARD FAILURE CHECK: If no sinks found, verify database state
    if not sinks:
        import sys
        print(f"[TAINT] WARNING: Found 0 security sinks", file=sys.stderr)
        print(f"[TAINT] Checked {len(all_sinks)} patterns across {len(sinks_to_use)} categories", file=sys.stderr)

        # Verify symbols table has call types
        call_query = build_query('symbols', ['name'],
            where="type='call'"
        )
        cursor.execute(call_query)
        call_count = len(cursor.fetchall())

        print(f"[TAINT] Symbols table: {call_count} calls", file=sys.stderr)

        # Check specialized tables (guaranteed to exist by schema contract)
        sql_query = build_query('sql_queries', ['file'])
        cursor.execute(sql_query)
        sql_count = len(cursor.fetchall())
        print(f"[TAINT] sql_queries table: {sql_count} rows", file=sys.stderr)

        args_query = build_query('function_call_args', ['callee_function'])
        cursor.execute(args_query)
        args_count = len(cursor.fetchall())
        print(f"[TAINT] function_call_args table: {args_count} rows", file=sys.stderr)

        if call_count == 0:
            print(f"[TAINT] ERROR: Indexer did not extract call symbols", file=sys.stderr)
            print(f"[TAINT] Run: aud index", file=sys.stderr)
            print(f"[TAINT] This is a CRITICAL failure - taint analysis impossible", file=sys.stderr)
            raise RuntimeError("Taint analysis impossible: No call symbols in database. Run 'aud index' first.")

    return sinks


def filter_framework_safe_sinks(
    cursor: sqlite3.Cursor,
    sinks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Filter out framework-safe sinks from taint analysis.

    Queries framework_safe_sinks table to remove sinks that are
    automatically sanitized by the framework (e.g., res.json in Express).

    This eliminates false positives by recognizing when frameworks provide
    automatic encoding/sanitization (JSON.stringify, template engines, etc.).

    Args:
        cursor: Database cursor
        sinks: List of detected sinks from find_security_sinks()

    Returns:
        Filtered list of sinks with framework-safe patterns removed

    Schema Contract:
        Queries framework_safe_sinks table (guaranteed to exist)
    """
    # Query all safe sink patterns
    query = build_query('framework_safe_sinks', ['sink_pattern', 'reason'],
        where="is_safe = 1"
    )
    cursor.execute(query)

    safe_patterns = {row[0]: row[1] for row in cursor.fetchall()}

    if not safe_patterns:
        # No safe sinks configured, return all sinks
        return sinks

    # Filter sinks
    filtered = []
    removed_count = 0

    for sink in sinks:
        sink_name = sink.get('name', '')
        sink_pattern = sink.get('pattern', '')

        # Check if this sink matches any safe pattern
        is_safe = False
        reason = None

        for safe_pattern, safe_reason in safe_patterns.items():
            # Match pattern in sink name or vice versa
            if (safe_pattern in sink_name or
                safe_pattern in sink_pattern or
                sink_name in safe_pattern or
                sink_pattern in safe_pattern):
                is_safe = True
                reason = safe_reason
                break

        if is_safe:
            removed_count += 1
            # Optional: Log removed sinks for debugging
            import os
            if os.environ.get("THEAUDITOR_DEBUG") or os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                print(f"[TAINT] Filtered safe sink: {sink_name} at {sink.get('file', 'unknown')}:{sink.get('line', 0)} ({reason})", file=sys.stderr)
        else:
            filtered.append(sink)

    if removed_count > 0:
        print(f"[TAINT] Filtered {removed_count} framework-safe sinks", file=sys.stderr)

    return filtered


def build_call_graph(cursor: sqlite3.Cursor) -> Dict[str, List[str]]:
    """Build a call graph mapping functions to their callees.

    Schema Contract:
        Queries symbols table (guaranteed to exist)
    """
    import os
    call_graph = defaultdict(list)

    # Get all function definitions
    query = build_query('symbols', ['path', 'name', 'line'],
        where="type = 'function'",
        order_by="path, line"
    )
    cursor.execute(query)
    
    functions = cursor.fetchall()
    
    for func_path, func_name, func_line in functions:
        # Normalize the path for consistency
        func_path = func_path.replace("\\", "/")
        # Use unified boundary detection
        func_start, func_end = get_function_boundaries(cursor, func_path, func_line)
        end_line = func_end
        
        # Find any nested functions within this function's range to exclude them
        query = build_query('symbols', ['line', 'name'],
            where="path = ? AND type = 'function' AND line > ? AND line < ?",
            order_by="line"
        )
        cursor.execute(query, (func_path, func_line, end_line))
        
        nested_functions = cursor.fetchall()
        
        # Build SQL to exclude nested function ranges
        if nested_functions:
            # Create ranges to exclude
            exclude_conditions = []
            for i, (nested_line, nested_name) in enumerate(nested_functions):
                # Find end of nested function
                if i + 1 < len(nested_functions):
                    next_nested_end = nested_functions[i + 1][0]
                else:
                    next_nested_end = end_line
                # Create condition to exclude this nested function's range
                exclude_conditions.append(f"NOT (line >= {nested_line} AND line < {next_nested_end})")
            
            exclude_clause = " AND " + " AND ".join(exclude_conditions)
        else:
            exclude_clause = ""
        
        # Find all calls within this function, excluding nested functions
        # Fixed: Use >= instead of > to include calls on the function definition line
        # NOTE: Uses dynamic WHERE clause (exclude_conditions) which build_query() doesn't support
        # Column names match schema: path, name, type, line
        query = f"""
            SELECT name
            FROM symbols
            WHERE path = ?
            AND type = 'call'
            AND line >= ?
            AND line < ?
            {exclude_clause}
        """

        cursor.execute(query, (func_path, func_line, end_line))
        
        calls = [row[0] for row in cursor.fetchall()]
        func_key = f"{func_path}:{func_name}"
        call_graph[func_key] = calls
        
        # Diagnostic logging
        if os.environ.get("THEAUDITOR_DEBUG"):
            if calls:
                print(f"[CALL GRAPH DEBUG] {func_key} calls: {calls[:5]}{'...' if len(calls) > 5 else ''}", file=sys.stderr)
            elif func_name not in ['__init__', '__del__', '__str__', '__repr__']:  # Skip common empty methods
                print(f"[CALL GRAPH DEBUG] WARNING: {func_key} has no calls", file=sys.stderr)
    
    return dict(call_graph)


def get_containing_function(cursor: sqlite3.Cursor, location: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the function containing a given code location.

    Schema Contract:
        Queries symbols table (guaranteed to exist)
    """
    # CRITICAL FIX: Normalize path BEFORE querying database
    # Database stores forward slashes, but location["file"] may have backslashes on Windows
    normalized_file = location["file"].replace("\\", "/")

    query = build_query('symbols', ['name', 'line'],
        where="path = ? AND type = 'function' AND line <= ?",
        order_by="line DESC",
        limit=1
    )
    cursor.execute(query, (normalized_file, location["line"]))

    result = cursor.fetchone()
    if result:
        return {
            "file": normalized_file,  # Already normalized
            "name": result[0],
            "line": result[1]
        }
    return None


def get_function_boundaries(cursor: sqlite3.Cursor, file_path: str,
                          function_line: int) -> Tuple[int, int]:
    """Get function boundaries from pre-extracted end_line column.

    The indexer extracts function end lines during parsing (for both Python
    and TypeScript/JavaScript via their respective extractors) and stores them
    in symbols.end_line. This function queries that pre-computed data.

    Args:
        cursor: Database cursor
        file_path: Path to source file (relative to project root)
        function_line: Start line of function

    Returns:
        Tuple of (start_line, end_line)

    Schema Contract:
        Queries symbols table with columns ['line', 'end_line']
        Both columns guaranteed to exist per schema.py:217-235
    """
    # CRITICAL FIX: Normalize path BEFORE querying database
    file_path = file_path.replace("\\", "/")

    # Query the end_line column that was extracted by the indexer
    query = build_query('symbols', ['line', 'end_line'],
        where="path = ? AND type = 'function' AND line = ?",
        limit=1
    )
    cursor.execute(query, (file_path, function_line))

    result = cursor.fetchone()

    if result and result[1]:
        # end_line was populated by indexer - use it
        return result[0], result[1]

    # Fallback for missing end_line (shouldn't happen after extraction fix)
    # This handles edge cases like:
    # - Old databases that haven't been re-indexed
    # - Functions from unsupported/fallback parsers
    # Use heuristic: assume function is ~200 lines max
    return function_line, function_line + 200


def get_code_snippet(file_path: str, line_num: int) -> str:
    """
    Get actual code line from file for enhanced path details.

    Args:
        file_path: Path to the source file (database format with forward slashes)
        line_num: Line number to extract (1-indexed)

    Returns:
        Stripped code line or empty string if unavailable
    """
    import os
    try:
        # CRITICAL FIX: Convert database path (forward slashes) to OS-specific path
        # Database stores "backend/src/file.js" but Windows open() needs "backend\src\file.js"
        os_path = file_path.replace("/", os.sep)
        with open(os_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if 0 <= line_num - 1 < len(lines):
                return lines[line_num - 1].strip()[:100]  # Limit to 100 chars for readability
    except (FileNotFoundError, IOError, OSError):
        pass
    return ""


# ============================================================================
# CFG Integration Functions - For Flow-Sensitive Taint Analysis
# ============================================================================

def get_block_for_line(cursor: sqlite3.Cursor, file_path: str, line: int,
                       function_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Find the CFG block containing a specific line.

    Args:
        cursor: Database cursor
        file_path: Path to the source file
        line: Line number to find
        function_name: Optional function name to narrow search

    Returns:
        Block dictionary or None if not found

    Schema Contract:
        Queries cfg_blocks table (guaranteed to exist)
    """
    # Normalize path
    file_path = file_path.replace("\\", "/")

    # Query for block containing the line
    if function_name:
        query = build_query('cfg_blocks',
            ['id', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'],
            where="file = ? AND function_name = ? AND start_line <= ? AND end_line >= ?",
            order_by="start_line DESC",
            limit=1
        )
        cursor.execute(query, (file_path, function_name, line, line))
    else:
        query = build_query('cfg_blocks',
            ['id', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'],
            where="file = ? AND start_line <= ? AND end_line >= ?",
            order_by="start_line DESC",
            limit=1
        )
        cursor.execute(query, (file_path, line, line))
    
    result = cursor.fetchone()
    if result:
        return {
            "id": result[0],
            "function_name": result[1],
            "type": result[2],
            "start_line": result[3],
            "end_line": result[4],
            "condition": result[5]
        }
    return None


def get_paths_between_blocks(cursor: sqlite3.Cursor, file_path: str,
                            source_block_id: int, sink_block_id: int,
                            max_paths: int = 100) -> List[List[int]]:
    """
    Find all execution paths between two CFG blocks.

    Uses BFS to enumerate paths from source block to sink block,
    avoiding cycles and limiting to max_paths.

    Args:
        cursor: Database cursor
        file_path: Path to the source file
        source_block_id: Starting block ID
        sink_block_id: Target block ID
        max_paths: Maximum number of paths to return

    Returns:
        List of paths, each path is a list of block IDs

    Schema Contract:
        Queries cfg_edges table (guaranteed to exist)
    """
    from collections import deque

    # Normalize path
    file_path = file_path.replace("\\", "/")

    # Build adjacency list from edges
    query = build_query('cfg_edges',
        ['source_block_id', 'target_block_id', 'edge_type'],
        where="file = ?"
    )
    cursor.execute(query, (file_path,))
    
    adjacency = defaultdict(list)
    for source, target, edge_type in cursor.fetchall():
        # Skip back edges to avoid infinite loops
        if edge_type != 'back_edge':
            adjacency[source].append(target)
    
    # BFS to find all paths
    paths = []
    queue = deque([(source_block_id, [source_block_id])])
    
    while queue and len(paths) < max_paths:
        current_block, current_path = queue.popleft()
        
        if current_block == sink_block_id:
            paths.append(current_path)
            continue
        
        # Add neighbors to queue
        for neighbor in adjacency[current_block]:
            # Avoid cycles within path
            if neighbor not in current_path:
                queue.append((neighbor, current_path + [neighbor]))
    
    return paths


def get_block_statements(cursor: sqlite3.Cursor, block_id: int) -> List[Dict[str, Any]]:
    """
    Get all statements within a CFG block.

    Args:
        cursor: Database cursor
        block_id: CFG block ID

    Returns:
        List of statement dictionaries

    Schema Contract:
        Queries cfg_block_statements table (guaranteed to exist)
    """
    query = build_query('cfg_block_statements',
        ['statement_type', 'line', 'statement_text'],
        where="block_id = ?",
        order_by="line"
    )
    cursor.execute(query, (block_id,))
    
    statements = []
    for stmt_type, line, text in cursor.fetchall():
        statements.append({
            "type": stmt_type,
            "line": line,
            "text": text
        })
    
    return statements


def get_cfg_for_function(cursor: sqlite3.Cursor, file_path: str,
                        function_name: str) -> Dict[str, Any]:
    """
    Get complete CFG for a function.

    Args:
        cursor: Database cursor
        file_path: Path to the source file
        function_name: Name of the function

    Returns:
        Dictionary with blocks and edges

    Schema Contract:
        Queries cfg_blocks and cfg_edges tables (guaranteed to exist)
    """
    # Normalize path
    file_path = file_path.replace("\\", "/")

    # Get all blocks for this function
    query = build_query('cfg_blocks',
        ['id', 'block_type', 'start_line', 'end_line', 'condition_expr'],
        where="file = ? AND function_name = ?",
        order_by="start_line"
    )
    cursor.execute(query, (file_path, function_name))
    
    blocks = []
    block_ids = set()
    for block_id, block_type, start_line, end_line, condition in cursor.fetchall():
        blocks.append({
            "id": block_id,
            "type": block_type,
            "start_line": start_line,
            "end_line": end_line,
            "condition": condition,
            "statements": get_block_statements(cursor, block_id)
        })
        block_ids.add(block_id)

    # Get all edges for this function
    edges_query = build_query('cfg_edges',
        ['source_block_id', 'target_block_id', 'edge_type'],
        where="file = ? AND function_name = ?"
    )
    cursor.execute(edges_query, (file_path, function_name))
    
    edges = []
    for source, target, edge_type in cursor.fetchall():
        # Only include edges between blocks in this function
        if source in block_ids and target in block_ids:
            edges.append({
                "source": source,
                "target": target,
                "type": edge_type
            })
    
    return {
        "function_name": function_name,
        "file": file_path,
        "blocks": blocks,
        "edges": edges
    }


def check_cfg_available(cursor: sqlite3.Cursor) -> bool:
    """
    Check if CFG tables exist and contain data.

    Args:
        cursor: Database cursor

    Returns:
        True if CFG data is available

    Schema Contract:
        Queries cfg_blocks table (guaranteed to exist)
        Table existence is guaranteed by schema contract
    """
    # Check if tables have data (no need to check existence)
    count_query = build_query('cfg_blocks', ['id'], limit=1)
    cursor.execute(count_query)

    return cursor.fetchone() is not None


# ============================================================================
# Object Literal Resolution - For Dynamic Dispatch Detection (v1.2+)
# ============================================================================

def resolve_object_literal_properties(
    cursor: sqlite3.Cursor,
    variable_name: str,
    property_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Resolve all properties of an object literal by variable name.

    Used for dynamic dispatch resolution: given `handlers[key]`, find all
    possible values that handlers[key] could resolve to.

    Args:
        cursor: Database cursor
        variable_name: Name of object variable (e.g., 'handlers', 'actions')
        property_types: Optional filter for property types
                       (e.g., ['function_ref', 'shorthand'] for functions only)

    Returns:
        List of property dictionaries with keys: property_name, property_value, property_type, line

    Example:
        >>> props = resolve_object_literal_properties(cursor, 'handlers', ['function_ref'])
        >>> # Returns: [{'property_name': 'create', 'property_value': 'createUser', ...}, ...]

    Schema Contract:
        Queries object_literals table (guaranteed to exist in v1.2+)
    """
    if property_types:
        # Build IN clause for property types
        placeholders = ','.join('?' * len(property_types))
        query = build_query('object_literals',
            ['property_name', 'property_value', 'property_type', 'line', 'file', 'nested_level'],
            where=f"variable_name = ? AND property_type IN ({placeholders})",
            order_by="line"
        )
        cursor.execute(query, (variable_name, *property_types))
    else:
        query = build_query('object_literals',
            ['property_name', 'property_value', 'property_type', 'line', 'file', 'nested_level'],
            where="variable_name = ?",
            order_by="line"
        )
        cursor.execute(query, (variable_name,))

    properties = []
    for prop_name, prop_value, prop_type, line, file, nested_level in cursor.fetchall():
        properties.append({
            'property_name': prop_name,
            'property_value': prop_value,
            'property_type': prop_type,
            'line': line,
            'file': file.replace("\\", "/"),
            'nested_level': nested_level
        })

    return properties


def find_dynamic_dispatch_targets(
    cursor: sqlite3.Cursor,
    variable_name: str
) -> List[str]:
    """
    Find all possible function targets for dynamic dispatch.

    Convenience wrapper around resolve_object_literal_properties that
    returns just the function names for handlers[key] patterns.

    Args:
        cursor: Database cursor
        variable_name: Name of handler map (e.g., 'handlers', 'actions', 'routes')

    Returns:
        List of function names that could be called

    Example:
        >>> targets = find_dynamic_dispatch_targets(cursor, 'handlers')
        >>> # Returns: ['createUser', 'updateUser', 'deleteUser']

    Schema Contract:
        Queries object_literals table (guaranteed to exist in v1.2+)
    """
    # Query for function references and shorthand properties only
    props = resolve_object_literal_properties(
        cursor,
        variable_name,
        property_types=['function_ref', 'shorthand']
    )

    # Extract just the property values (function names)
    return [prop['property_value'] for prop in props]


def check_object_literals_available(cursor: sqlite3.Cursor) -> bool:
    """
    Check if object_literals table contains data.

    Args:
        cursor: Database cursor

    Returns:
        True if object literal data is available

    Schema Contract:
        Queries object_literals table (guaranteed to exist in v1.2+)
        Table existence is guaranteed by schema contract

    Note:
        Uses schema-compliant query with LIMIT 1 for existence check
    """
    # Use schema-compliant query instead of COUNT(*)
    query = build_query('object_literals', ['id'], limit=1)
    cursor.execute(query)

    return cursor.fetchone() is not None