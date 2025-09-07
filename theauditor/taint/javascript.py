"""JavaScript/TypeScript-specific taint patterns.

This module implements taint tracking for JavaScript-specific constructs
that don't exist in other languages:
- Object destructuring
- Spread operators
- Bracket notation
- Array operations
- Type conversions
"""

import sqlite3
from typing import Set, List, Dict, Any


def track_destructuring(cursor: sqlite3.Cursor, source: Dict[str, Any], file_path: str) -> Set[str]:
    """
    Track object destructuring: const { x, y } = tainted_object.
    
    When a tainted object is destructured, all extracted properties
    become tainted.
    
    Args:
        cursor: Database cursor
        source: The tainted source
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from destructuring
    """
    tainted_vars = set()
    
    # Look for destructuring patterns in assignments
    # Pattern: const { ... } = source_pattern
    cursor.execute("""
        SELECT target_var, line, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND (target_var LIKE '%{%' OR target_var LIKE '%[%')
    """, (file_path, f"%{source['pattern']}%"))
    
    for target, line, expr in cursor.fetchall():
        # Parse destructuring pattern
        # Examples:
        # { username, password } = req.body
        # { data: userData } = response
        # [ first, second ] = array
        
        if '{' in target and '}' in target:
            # Object destructuring
            # Extract variable names between { and }
            start = target.index('{') + 1
            end = target.index('}')
            props = target[start:end]
            
            # Handle both simple and renamed destructuring
            for prop in props.split(','):
                prop = prop.strip()
                if ':' in prop:
                    # Renamed: { data: userData }
                    _, var_name = prop.split(':', 1)
                    var_name = var_name.strip()
                else:
                    # Simple: { username }
                    var_name = prop.strip()
                
                if var_name and not var_name.startswith('...'):
                    tainted_vars.add(var_name)
        
        elif '[' in target and ']' in target:
            # Array destructuring
            start = target.index('[') + 1
            end = target.index(']')
            elements = target[start:end]
            
            for element in elements.split(','):
                element = element.strip()
                if element and element != '_':  # Skip placeholders
                    tainted_vars.add(element)
    
    return tainted_vars


def track_spread_operators(cursor: sqlite3.Cursor, source: Dict[str, Any], file_path: str) -> Set[str]:
    """
    Track spread operators: const { ...rest } = tainted_object.
    
    When a tainted object is spread, the rest object becomes tainted.
    
    Args:
        cursor: Database cursor
        source: The tainted source
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from spread operations
    """
    tainted_vars = set()
    
    # Look for spread patterns in assignments
    cursor.execute("""
        SELECT target_var, line, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND target_var LIKE '%...%'
    """, (file_path, f"%{source['pattern']}%"))
    
    for target, line, expr in cursor.fetchall():
        # Extract spread variable names
        if '...' in target:
            # Find the variable after ...
            spread_index = target.index('...')
            after_spread = target[spread_index + 3:]
            
            # Extract variable name (could be in various contexts)
            # Examples:
            # { ...rest }
            # { x, ...rest }
            # [ ...items ]
            
            # Simple extraction - get the word after ...
            import re
            match = re.search(r'\.\.\.(\w+)', target)
            if match:
                var_name = match.group(1)
                tainted_vars.add(var_name)
    
    # Also check for spread in object/array construction
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
    """, (file_path, f"%...{source['pattern']}%"))
    
    for target, expr in cursor.fetchall():
        # If source is spread into new object/array, target is tainted
        tainted_vars.add(target)
    
    return tainted_vars


def track_bracket_notation(cursor: sqlite3.Cursor, source_pattern: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Track bracket notation access: obj['key'] or obj[variable].
    
    This is commonly used for accessing query parameters and headers.
    
    Args:
        cursor: Database cursor
        source_pattern: Pattern to search for (e.g., "req.query")
        file_path: Path to the file being analyzed
        
    Returns:
        List of sources/sinks found via bracket notation
    """
    results = []
    
    # Look for bracket notation patterns
    # Common patterns:
    # req.query['param']
    # req.headers['authorization']
    # obj[key]
    
    # Search in symbols for bracket access
    cursor.execute("""
        SELECT name, line, col, type
        FROM symbols
        WHERE path = ?
        AND (name LIKE ? OR name LIKE ?)
        ORDER BY line
    """, (file_path, f"%{source_pattern}[%", f"%{source_pattern}['%"))
    
    for name, line, col, sym_type in cursor.fetchall():
        results.append({
            "file": file_path,
            "name": name,
            "line": line,
            "column": col,
            "pattern": source_pattern,
            "type": "source",
            "access": "bracket"
        })
    
    # Also check in assignments for bracket notation
    cursor.execute("""
        SELECT DISTINCT line, source_expr
        FROM assignments
        WHERE file = ?
        AND (source_expr LIKE ? OR source_expr LIKE ?)
    """, (file_path, f"%{source_pattern}[%", f"%{source_pattern}['%"))
    
    for line, expr in cursor.fetchall():
        results.append({
            "file": file_path,
            "name": expr,
            "line": line,
            "column": 0,
            "pattern": source_pattern,
            "type": "source",
            "access": "bracket"
        })
    
    return results


def track_array_operations(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track array operations: map, filter, forEach, reduce, etc.
    
    When a tainted array is processed, the callback parameters become tainted.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted array variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from array operations
    """
    tainted_vars = set()
    
    # Array methods that propagate taint
    array_methods = [
        'map', 'filter', 'forEach', 'reduce', 'find', 'findIndex',
        'some', 'every', 'flatMap', 'reduceRight'
    ]
    
    for method in array_methods:
        # Look for calls like: tainted_var.method(...)
        cursor.execute("""
            SELECT name, line
            FROM symbols
            WHERE path = ?
            AND type = 'call'
            AND name LIKE ?
        """, (file_path, f"{tainted_var}.{method}%"))
        
        for name, line in cursor.fetchall():
            # The callback parameters are tainted
            # This is simplified - ideally we'd parse the callback signature
            # Common patterns:
            # items.map(item => ...)  // 'item' is tainted
            # items.filter((item, index) => ...)  // 'item' and 'index' are tainted
            
            # Look for arrow functions or function expressions near this line
            cursor.execute("""
                SELECT target_var
                FROM assignments
                WHERE file = ?
                AND line BETWEEN ? AND ?
                AND source_expr LIKE ?
            """, (file_path, line, line + 3, f"%{method}%"))
            
            for (target,) in cursor.fetchall():
                # Simplified: assume first parameter of callback is tainted
                tainted_vars.add(f"{target}_element")  # Placeholder for element parameter
    
    # Also track direct array access: tainted_array[0]
    cursor.execute("""
        SELECT target_var
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
    """, (file_path, f"{tainted_var}[%"))
    
    for (target,) in cursor.fetchall():
        tainted_vars.add(target)
    
    return tainted_vars


def track_type_conversions(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track type conversion functions that propagate taint.
    
    Functions like parseInt, String(), JSON.parse propagate taint
    from input to output.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from type conversions
    """
    tainted_vars = set()
    
    # Type conversion functions that propagate taint
    converters = [
        'parseInt', 'parseFloat', 'Number',
        'String', 'toString',
        'JSON.parse', 'JSON.stringify',
        'atob', 'btoa',  # Base64 encoding/decoding
        'encodeURIComponent', 'decodeURIComponent',
        'encodeURI', 'decodeURI'
    ]
    
    for converter in converters:
        # Look for conversions using the tainted variable
        cursor.execute("""
            SELECT target_var, source_expr
            FROM assignments
            WHERE file = ?
            AND source_expr LIKE ?
            AND source_expr LIKE ?
        """, (file_path, f"%{converter}%", f"%{tainted_var}%"))
        
        for target, expr in cursor.fetchall():
            # The result of conversion is tainted
            tainted_vars.add(target)
    
    # Also check for method calls on the tainted variable
    cursor.execute("""
        SELECT target_var
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
    """, (file_path, f"{tainted_var}.toString%"))
    
    for (target,) in cursor.fetchall():
        tainted_vars.add(target)
    
    return tainted_vars


def enhance_javascript_tracking(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    tainted_elements: Set[str],
    file_path: str
) -> Set[str]:
    """
    Main entry point for JavaScript-specific taint enhancements.
    
    This function applies all JavaScript-specific tracking to enhance
    the base taint analysis.
    
    Args:
        cursor: Database cursor
        source: The taint source
        tainted_elements: Current set of tainted elements
        file_path: Path to the file being analyzed
        
    Returns:
        Enhanced set of tainted elements
    """
    enhanced = set(tainted_elements)
    
    # Track destructuring
    destructured = track_destructuring(cursor, source, file_path)
    enhanced.update(destructured)
    
    # Track spread operators
    spread = track_spread_operators(cursor, source, file_path)
    enhanced.update(spread)
    
    # Track array operations for each tainted variable
    for element in list(enhanced):
        if ':' in element:
            _, var_name = element.split(':', 1)
        else:
            var_name = element
        
        array_tainted = track_array_operations(cursor, var_name, file_path)
        enhanced.update(array_tainted)
        
        # Track type conversions
        converted = track_type_conversions(cursor, var_name, file_path)
        enhanced.update(converted)
    
    return enhanced