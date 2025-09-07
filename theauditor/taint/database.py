"""Database operations for taint analysis.

This module contains all database query functions used by the taint analyzer.
"""

import sys
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from .sources import TAINT_SOURCES, SECURITY_SINKS


def find_taint_sources(cursor: sqlite3.Cursor, sources_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
    """Find all occurrences of taint sources in the codebase.
    
    Args:
        cursor: Database cursor
        sources_dict: Optional dictionary of sources to use instead of global TAINT_SOURCES
    
    Returns:
        List of source occurrences found in the codebase
    """
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
            cursor.execute("""
                SELECT path, name, line, col
                FROM symbols
                WHERE (type = 'call' OR type = 'property' OR type = 'symbol')
                AND name LIKE ?
                ORDER BY path, line
            """, (f"%{source_pattern}%",))
        else:
            # Look for simple function calls and symbols
            cursor.execute("""
                SELECT path, name, line, col
                FROM symbols
                WHERE (type = 'call' OR type = 'symbol')
                AND name = ?
                ORDER BY path, line
            """, (source_pattern,))
        
        for row in cursor.fetchall():
            sources.append({
                "file": row[0].replace("\\", "/"),  # Normalize path separators
                "name": row[1],
                "line": row[2],
                "column": row[3],
                "pattern": source_pattern,
                "type": "source"
            })
    
    return sources


def find_security_sinks(cursor: sqlite3.Cursor, sinks_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
    """Find all occurrences of security sinks in the codebase.
    
    Args:
        cursor: Database cursor
        sinks_dict: Optional dictionary of sinks to use instead of global SECURITY_SINKS
    
    Returns:
        List of sink occurrences found in the codebase
    """
    sinks = []
    
    # Use provided sinks or default to global
    sinks_to_use = sinks_dict if sinks_dict is not None else SECURITY_SINKS
    
    # Combine all sink patterns
    all_sinks = []
    sink_categories = {}
    for category, sink_list in sinks_to_use.items():
        for sink in sink_list:
            all_sinks.append(sink)
            sink_categories[sink] = category
    
    # Query for each sink pattern
    for sink_pattern in all_sinks:
        # CRITICAL FIX: Handle chained method patterns like "res.status().json"
        if '().' in sink_pattern:
            # Decompose pattern: "res.status().json" → "res.status" + "json"
            parts = sink_pattern.replace('().', '.').split('.')
            base_method = '.'.join(parts[:-1])
            final_method = parts[-1]
            
            # Performance optimization: Query for final method first (smaller result set)
            # Then verify base method exists on same line
            cursor.execute("""
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
            """, (final_method, f"%.{final_method}", f"%{base_method}%", base_method))
            
            for row in cursor.fetchall():
                sinks.append({
                    "file": row[0].replace("\\", "/"),  # Normalize path separators
                    "name": sink_pattern,  # Use full pattern for reporting
                    "line": row[1],
                    "column": row[2],
                    "pattern": sink_pattern,
                    "category": sink_categories.get(sink_pattern, ""),  # Empty not unknown
                    "type": "sink"
                })
        else:
            # Original logic for simple patterns
            cursor.execute("""
                SELECT path, name, line, col
                FROM symbols
                WHERE type = 'call'
                AND (name = ? OR name LIKE ?)
                ORDER BY path, line
            """, (sink_pattern, f"%.{sink_pattern}"))
            
            for row in cursor.fetchall():
                sinks.append({
                    "file": row[0].replace("\\", "/"),  # Normalize path separators
                    "name": row[1],
                    "line": row[2],
                    "column": row[3],
                    "pattern": sink_pattern,
                    "category": sink_categories.get(sink_pattern, ""),  # Empty not unknown
                    "type": "sink"
                })
    
    return sinks


def build_call_graph(cursor: sqlite3.Cursor) -> Dict[str, List[str]]:
    """Build a call graph mapping functions to their callees."""
    import os
    call_graph = defaultdict(list)
    
    # Get all function definitions
    cursor.execute("""
        SELECT path, name, line
        FROM symbols
        WHERE type = 'function'
        ORDER BY path, line
    """)
    
    functions = cursor.fetchall()
    
    for func_path, func_name, func_line in functions:
        # Normalize the path for consistency
        func_path = func_path.replace("\\", "/")
        # Use unified boundary detection
        func_start, func_end = get_function_boundaries(cursor, func_path, func_line)
        end_line = func_end
        
        # Find any nested functions within this function's range to exclude them
        cursor.execute("""
            SELECT line, name
            FROM symbols
            WHERE path = ?
            AND type = 'function'
            AND line > ?
            AND line < ?
            ORDER BY line
        """, (func_path, func_line, end_line))
        
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
    """Find the function containing a given code location."""
    cursor.execute("""
        SELECT name, line
        FROM symbols
        WHERE path = ?
        AND type = 'function'
        AND line <= ?
        ORDER BY line DESC
        LIMIT 1
    """, (location["file"], location["line"]))
    
    result = cursor.fetchone()
    if result:
        return {
            "file": location["file"].replace("\\", "/"),  # Normalize path separators
            "name": result[0],
            "line": result[1]
        }
    return None


def get_function_boundaries(cursor: sqlite3.Cursor, file_path: str,
                          function_line: int) -> Tuple[int, int]:
    """Get accurate start and end lines for a function.
    
    Uses next function start as current function end.
    Falls back to max line in file for last function.
    """
    # Find next function in same file
    cursor.execute("""
        SELECT line FROM symbols
        WHERE path = ? AND type = 'function' AND line > ?
        ORDER BY line LIMIT 1
    """, (file_path, function_line))
    
    next_func = cursor.fetchone()
    if next_func:
        # Function ends before next function starts
        return function_line, next_func[0] - 1
    
    # No next function, get max line in file
    cursor.execute("""
        SELECT MAX(line) FROM symbols WHERE path = ?
    """, (file_path,))
    
    max_line = cursor.fetchone()
    return function_line, max_line[0] if max_line and max_line[0] else function_line + 200


def get_code_snippet(file_path: str, line_num: int) -> str:
    """
    Get actual code line from file for enhanced path details.
    
    Args:
        file_path: Path to the source file
        line_num: Line number to extract (1-indexed)
        
    Returns:
        Stripped code line or empty string if unavailable
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if 0 <= line_num - 1 < len(lines):
                return lines[line_num - 1].strip()[:100]  # Limit to 100 chars for readability
    except (FileNotFoundError, IOError, OSError):
        pass
    return ""