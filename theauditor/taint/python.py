"""Python-specific taint tracking patterns.

This module implements taint tracking for Python-specific constructs
that don't exist in other languages:
- F-strings with tainted variables
- List/dict comprehensions
- Unpacking operations (*args, **kwargs)
- Decorators that modify data flow
- Context managers
- String formatting operations
"""

import sqlite3
from typing import Set, List, Dict, Any


def track_fstrings(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track f-strings: f'{tainted_var}' propagates taint.
    
    When a tainted variable is used in an f-string, the resulting
    string becomes tainted.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from f-string formatting
    """
    tainted_vars = set()
    
    # Look for f-string assignments containing the tainted variable
    # Pattern: target = f"...{tainted_var}..."
    cursor.execute("""
        SELECT target_var, source_expr, line
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND (source_expr LIKE 'f"%' OR source_expr LIKE "f'%")
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr, line in cursor.fetchall():
        # F-string result is tainted
        tainted_vars.add(target)
    
    # Also check for str.format() with tainted variables
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND source_expr LIKE '%.format(%'
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        tainted_vars.add(target)
    
    # Check for % formatting
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND source_expr LIKE '%%%s%%'
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        tainted_vars.add(target)
    
    return tainted_vars


def track_comprehensions(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track list/dict comprehensions with tainted sources.
    
    When a comprehension iterates over tainted data or uses tainted
    variables in expressions, the result is tainted.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from comprehensions
    """
    tainted_vars = set()
    
    # List comprehensions: [expr for item in tainted_var]
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND source_expr LIKE '[%for%in%]'
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        tainted_vars.add(target)
        
        # Also extract the loop variable (item) as tainted
        # Simplified extraction - would need proper AST parsing for accuracy
        if ' for ' in expr and ' in ' in expr:
            parts = expr.split(' for ')
            if len(parts) > 1:
                loop_part = parts[1].split(' in ')[0].strip()
                # Remove brackets and get variable name
                loop_var = loop_part.replace('[', '').replace(']', '').strip()
                if loop_var and loop_var.isidentifier():
                    tainted_vars.add(loop_var)
    
    # Dict comprehensions: {k: v for k, v in tainted_var}
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND source_expr LIKE '{%for%in%}'
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        tainted_vars.add(target)
    
    # Generator expressions: (expr for item in tainted_var)
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND source_expr LIKE '(%for%in%)'
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        tainted_vars.add(target)
    
    return tainted_vars


def track_unpacking(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track unpacking operations: *args, **kwargs, tuple unpacking.
    
    When tainted data is unpacked, all unpacked variables become tainted.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from unpacking
    """
    tainted_vars = set()
    
    # Tuple unpacking: a, b, c = tainted_var
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr = ?
        AND target_var LIKE '%,%'
    """, (file_path, tainted_var))
    
    for target, expr in cursor.fetchall():
        # Split comma-separated targets
        for var in target.split(','):
            var = var.strip()
            if var and var.isidentifier():
                tainted_vars.add(var)
    
    # *args unpacking in function calls
    cursor.execute("""
        SELECT name, line
        FROM symbols
        WHERE path = ?
        AND type = 'call'
        AND name LIKE ?
    """, (file_path, f"%*{tainted_var}%"))
    
    for name, line in cursor.fetchall():
        # Arguments become tainted when unpacked
        # This would need more context to track properly
        pass
    
    # **kwargs unpacking
    cursor.execute("""
        SELECT name, line
        FROM symbols
        WHERE path = ?
        AND type = 'call'
        AND name LIKE ?
    """, (file_path, f"%**{tainted_var}%"))
    
    for name, line in cursor.fetchall():
        # Keyword arguments become tainted when unpacked
        pass
    
    return tainted_vars


def track_decorators(cursor: sqlite3.Cursor, function_name: str, file_path: str) -> Dict[str, Any]:
    """
    Track decorators that might modify data flow.
    
    Some decorators can transform or validate data, affecting taint flow.
    
    Args:
        cursor: Database cursor
        function_name: Function being analyzed
        file_path: Path to the file being analyzed
        
    Returns:
        Dictionary with decorator information
    """
    decorator_info = {
        'has_validation': False,
        'has_transformation': False,
        'decorators': []
    }
    
    # Check for common validation decorators
    validation_decorators = [
        'validate', 'validates', 'validator',
        'sanitize', 'clean', 'escape',
        'auth_required', 'login_required'
    ]
    
    # Check for transformation decorators
    transformation_decorators = [
        'cache', 'memoize', 'lru_cache',
        'async', 'sync', 'convert'
    ]
    
    # Query for decorators on this function
    cursor.execute("""
        SELECT name, line
        FROM symbols
        WHERE path = ?
        AND type = 'decorator'
        AND line < (
            SELECT line FROM symbols
            WHERE path = ? AND name = ? AND type = 'function'
            LIMIT 1
        )
        ORDER BY line DESC
        LIMIT 10
    """, (file_path, file_path, function_name))
    
    for dec_name, line in cursor.fetchall():
        decorator_info['decorators'].append(dec_name)
        
        # Check if it's a validation decorator
        if any(val in dec_name.lower() for val in validation_decorators):
            decorator_info['has_validation'] = True
        
        # Check if it's a transformation decorator
        if any(trans in dec_name.lower() for trans in transformation_decorators):
            decorator_info['has_transformation'] = True
    
    return decorator_info


def track_context_managers(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track context managers: with statements that might propagate taint.
    
    Context managers can transform data on enter/exit.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from context managers
    """
    tainted_vars = set()
    
    # With statements: with open(...) as f:
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE 'with %'
        AND source_expr LIKE ?
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        # The 'as' variable becomes tainted if source is tainted
        if ' as ' in expr:
            as_part = expr.split(' as ')[-1]
            # Extract variable name (simplified)
            as_var = as_part.split(':')[0].strip()
            if as_var and as_var.isidentifier():
                tainted_vars.add(as_var)
    
    return tainted_vars


def track_string_operations(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track string operations that propagate taint.
    
    Operations like split, join, replace, etc. propagate taint.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from string operations
    """
    tainted_vars = set()
    
    # String methods that propagate taint
    string_methods = [
        'split', 'join', 'replace', 'strip', 'lstrip', 'rstrip',
        'upper', 'lower', 'capitalize', 'title',
        'encode', 'decode', 'format', 'expandtabs',
        'center', 'ljust', 'rjust', 'zfill',
        'partition', 'rpartition', 'splitlines',
        'translate', 'swapcase'
    ]
    
    for method in string_methods:
        # Look for method calls on tainted variable
        cursor.execute("""
            SELECT target_var, source_expr
            FROM assignments
            WHERE file = ?
            AND source_expr LIKE ?
        """, (file_path, f"{tainted_var}.{method}%"))
        
        for target, expr in cursor.fetchall():
            tainted_vars.add(target)
    
    # String concatenation with +
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE ?
        AND source_expr LIKE '%+%'
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        # If tainted variable is concatenated, result is tainted
        tainted_vars.add(target)
    
    # String join operations
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE '%.join(%'
        AND source_expr LIKE ?
    """, (file_path, f"%{tainted_var}%"))
    
    for target, expr in cursor.fetchall():
        tainted_vars.add(target)
    
    return tainted_vars


def track_exception_propagation(cursor: sqlite3.Cursor, tainted_var: str, file_path: str) -> Set[str]:
    """
    Track taint through exception handling.
    
    When tainted data is caught in exceptions, it can propagate.
    
    Args:
        cursor: Database cursor
        tainted_var: The tainted variable
        file_path: Path to the file being analyzed
        
    Returns:
        Set of newly tainted variables from exception handling
    """
    tainted_vars = set()
    
    # Try to find exception handlers that might use tainted data
    cursor.execute("""
        SELECT target_var, source_expr
        FROM assignments
        WHERE file = ?
        AND source_expr LIKE 'except%as%'
        AND line > (
            SELECT MIN(line) FROM assignments
            WHERE file = ? AND target_var = ?
        )
    """, (file_path, file_path, tainted_var))
    
    for target, expr in cursor.fetchall():
        # If exception uses tainted data, exception variable is tainted
        if ' as ' in expr:
            except_var = expr.split(' as ')[-1].strip(':').strip()
            if except_var and except_var.isidentifier():
                # Check if tainted_var is used in the exception context
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM symbols
                    WHERE path = ?
                    AND name LIKE ?
                    AND line > ?
                    AND line < ?
                """, (file_path, f"%{tainted_var}%", 
                     cursor.lastrowid - 5, cursor.lastrowid + 10))
                
                if cursor.fetchone()[0] > 0:
                    tainted_vars.add(except_var)
    
    return tainted_vars


def enhance_python_tracking(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    tainted_elements: Set[str],
    file_path: str
) -> Set[str]:
    """
    Main entry point for Python-specific taint enhancements.
    
    This function applies all Python-specific tracking to enhance
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
    
    # Process each tainted variable
    for element in list(enhanced):
        if ':' in element:
            _, var_name = element.split(':', 1)
        else:
            var_name = element
        
        # Track f-strings
        fstring_tainted = track_fstrings(cursor, var_name, file_path)
        enhanced.update(fstring_tainted)
        
        # Track comprehensions
        comp_tainted = track_comprehensions(cursor, var_name, file_path)
        enhanced.update(comp_tainted)
        
        # Track unpacking
        unpack_tainted = track_unpacking(cursor, var_name, file_path)
        enhanced.update(unpack_tainted)
        
        # Track context managers
        context_tainted = track_context_managers(cursor, var_name, file_path)
        enhanced.update(context_tainted)
        
        # Track string operations
        string_tainted = track_string_operations(cursor, var_name, file_path)
        enhanced.update(string_tainted)
        
        # Track exception propagation
        except_tainted = track_exception_propagation(cursor, var_name, file_path)
        enhanced.update(except_tainted)
    
    return enhanced