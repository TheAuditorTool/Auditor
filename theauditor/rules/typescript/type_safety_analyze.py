"""SQL-based TypeScript type safety analyzer - ENHANCED.

This module provides comprehensive type safety detection for TypeScript projects
by querying the indexed database instead of traversing AST structures.
"""

import sqlite3
import re
from typing import List, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_type_safety_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """
    Detect TypeScript type safety issues using SQL queries.
    
    This enhanced version detects:
    - Explicit and implicit 'any' types
    - Missing return types and parameter types
    - Unsafe type assertions and non-null assertions
    - Dangerous type patterns (Function, Object, {})
    - Untyped API responses and JSON.parse
    - Missing error handling types
    - Interface and type definition issues
    - And much more...
    
    Args:
        context: StandardRuleContext with database path
        
    Returns:
        List of StandardFinding objects
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()
        
        # Only analyze TypeScript files
        cursor.execute("SELECT DISTINCT file FROM files WHERE extension IN ('ts', 'tsx')")
        ts_files = {row[0] for row in cursor.fetchall()}
        
        if not ts_files:
            return findings  # No TypeScript files in project
        
        # Pattern 1: Explicit 'any' types
        findings.extend(_find_explicit_any_types(cursor, ts_files))
        
        # Pattern 2: Missing return types
        findings.extend(_find_missing_return_types(cursor, ts_files))
        
        # Pattern 3: Missing parameter types
        findings.extend(_find_missing_parameter_types(cursor, ts_files))
        
        # Pattern 4: Unsafe type assertions (as any, as unknown)
        findings.extend(_find_unsafe_type_assertions(cursor, ts_files))
        
        # Pattern 5: Non-null assertions (!)
        findings.extend(_find_non_null_assertions(cursor, ts_files))
        
        # Pattern 6: Dangerous type patterns (Function, Object, {})
        findings.extend(_find_dangerous_type_patterns(cursor, ts_files))
        
        # Pattern 7: Untyped JSON.parse
        findings.extend(_find_untyped_json_parse(cursor, ts_files))
        
        # Pattern 8: Untyped API responses
        findings.extend(_find_untyped_api_responses(cursor, ts_files))
        
        # Pattern 9: Missing interface definitions
        findings.extend(_find_missing_interfaces(cursor, ts_files))
        
        # Pattern 10: Type suppression comments
        findings.extend(_find_type_suppression_comments(cursor, ts_files))
        
        # Pattern 11: Untyped catch blocks
        findings.extend(_find_untyped_catch_blocks(cursor, ts_files))
        
        # Pattern 12: Missing generic types
        findings.extend(_find_missing_generic_types(cursor, ts_files))
        
        # Pattern 13: Untyped event handlers
        findings.extend(_find_untyped_event_handlers(cursor, ts_files))
        
        # Pattern 14: Type mismatches in assignments
        findings.extend(_find_type_mismatches(cursor, ts_files))
        
        # Pattern 15: Unsafe property access
        findings.extend(_find_unsafe_property_access(cursor, ts_files))
        
        conn.close()
        
    except Exception:
        pass  # Return empty findings on error
    
    return findings


def _find_explicit_any_types(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find explicit 'any' type annotations."""
    findings = []
    
    # Check symbols table for 'any' types
    cursor.execute("""
        SELECT s.file, s.line, s.name, s.symbol_type
        FROM symbols s
        WHERE s.file IN ({})
          AND (s.name LIKE '%: any%' 
               OR s.name LIKE '%<any>%'
               OR s.name LIKE '%any[]%'
               OR s.name LIKE '%Array<any>%')
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    any_symbols = cursor.fetchall()
    
    for file, line, name, sym_type in any_symbols:
        findings.append(StandardFinding(
            rule_name='typescript-explicit-any',
            message=f"Explicit 'any' type in {sym_type}: {name}",
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='type-safety',
            snippet=name[:100],
            fix_suggestion="Replace 'any' with specific type or 'unknown' for better type safety",
            cwe_id='CWE-843'
        ))
    
    # Check assignments for any types
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({})
          AND (a.source_expr LIKE '%: any%' 
               OR a.source_expr LIKE '%as any%'
               OR a.target_var LIKE '%: any%')
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    any_assignments = cursor.fetchall()
    
    for file, line, var, expr in any_assignments:
        findings.append(StandardFinding(
            rule_name='typescript-any-assignment',
            message=f"Variable '{var}' uses 'any' type",
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='type-safety',
            snippet=f'{var}: any',
            fix_suggestion="Avoid 'any' type - use specific types or 'unknown' with type guards",
            cwe_id='CWE-843'
        ))
    
    return findings


def _find_missing_return_types(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find functions without explicit return types."""
    findings = []
    
    # Find function symbols without return type annotations
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.file IN ({})
          AND s.symbol_type = 'function'
          AND s.name NOT LIKE '%=>%void%'
          AND s.name NOT LIKE '%:%'
          AND s.name NOT LIKE '%Promise<%'
          AND s.name NOT LIKE '%async%'
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    untyped_functions = cursor.fetchall()
    
    for file, line, name in untyped_functions:
        # Skip constructors and React lifecycle methods
        if name not in ['constructor', 'render', 'componentDidMount', 'componentWillUnmount']:
            findings.append(StandardFinding(
                rule_name='typescript-missing-return-type',
                message=f"Function '{name}' missing explicit return type",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='type-safety',
                snippet=f'function {name}(...)',
                fix_suggestion='Add explicit return type annotation for better type safety',
                cwe_id='CWE-843'
            ))
    
    return findings


def _find_missing_parameter_types(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find function parameters without type annotations."""
    findings = []
    
    # Look for function calls with untyped parameters
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({})
          AND f.callee_function LIKE '%function%'
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    function_calls = cursor.fetchall()
    
    for file, line, func, args in function_calls:
        if args and 'function(' in args.lower():
            # Check if parameters have types
            if not ':' in args and '(' in args and ')' in args:
                findings.append(StandardFinding(
                    rule_name='typescript-untyped-parameters',
                    message='Function parameters without type annotations',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='type-safety',
                    snippet='function(param1, param2)',
                    fix_suggestion='Add type annotations to all function parameters',
                    cwe_id='CWE-843'
                ))
    
    return findings


def _find_unsafe_type_assertions(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find unsafe type assertions (as any, as unknown)."""
    findings = []
    
    # Check for type assertions in assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({})
          AND (a.source_expr LIKE '%as any%' 
               OR a.source_expr LIKE '%as unknown%'
               OR a.source_expr LIKE '%as Function%'
               OR a.source_expr LIKE '%<any>%')
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    type_assertions = cursor.fetchall()
    
    for file, line, var, expr in type_assertions:
        severity = Severity.HIGH if 'as any' in expr else Severity.MEDIUM
        findings.append(StandardFinding(
            rule_name='typescript-unsafe-assertion',
            message=f"Unsafe type assertion in '{var}'",
            file_path=file,
            line=line,
            severity=severity,
            category='type-safety',
            snippet=f'{var} = ... as any',
            fix_suggestion='Type assertions bypass compiler checks. Use type guards or proper typing',
            cwe_id='CWE-843'
        ))
    
    return findings


def _find_non_null_assertions(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find non-null assertions (!) that bypass null checks."""
    findings = []
    
    # Look for ! assertions in code
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.file IN ({})
          AND (a.source_expr LIKE '%!.%' 
               OR a.source_expr LIKE '%!)%'
               OR a.source_expr LIKE '%!;%')
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    non_null_assertions = cursor.fetchall()
    
    for file, line, expr in non_null_assertions:
        findings.append(StandardFinding(
            rule_name='typescript-non-null-assertion',
            message='Non-null assertion (!) bypasses null safety',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='type-safety',
            snippet='value!.property',
            fix_suggestion='Non-null assertions can cause runtime errors. Use optional chaining (?.)',
            cwe_id='CWE-476'
        ))
    
    return findings


def _find_dangerous_type_patterns(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find dangerous type patterns like Function, Object, {}."""
    findings = []
    
    dangerous_types = [
        ('Function', 'Use specific function signature like (arg: Type) => ReturnType'),
        ('Object', 'Use specific interface or type instead of Object'),
        ('{}', 'Empty object type accepts any non-null value - use Record<string, unknown> or specific type')
    ]
    
    for dangerous_type, recommendation in dangerous_types:
        cursor.execute("""
            SELECT s.file, s.line, s.name
            FROM symbols s
            WHERE s.file IN ({})
              AND (s.name LIKE '%: {}%' 
                   OR s.name LIKE '%<{}>%'
                   OR s.name LIKE '%{}[]%')
        """.format(','.join(['?' for _ in ts_files]), dangerous_type, dangerous_type, dangerous_type), 
        list(ts_files))
        
        dangerous_symbols = cursor.fetchall()
        
        for file, line, name in dangerous_symbols:
            findings.append(StandardFinding(
                rule_name=f'typescript-dangerous-type-{dangerous_type.lower()}',
                message=f"Dangerous type '{dangerous_type}' in {name}",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='type-safety',
                snippet=f': {dangerous_type}',
                fix_suggestion=recommendation,
                cwe_id='CWE-843'
            ))
    
    return findings


def _find_untyped_json_parse(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find JSON.parse without type validation."""
    findings = []
    
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({})
          AND f.callee_function LIKE '%JSON.parse%'
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    json_parses = cursor.fetchall()
    
    for file, line, func, args in json_parses:
        # Check if result is typed (look for type assertion or validation nearby)
        cursor.execute("""
            SELECT COUNT(*)
            FROM assignments a
            WHERE a.file = ?
              AND a.line BETWEEN ? AND ?
              AND (a.source_expr LIKE '%as %' 
                   OR a.source_expr LIKE '%zod%'
                   OR a.source_expr LIKE '%joi%'
                   OR a.source_expr LIKE '%validate%')
        """, (file, line, line + 5))
        
        has_validation = cursor.fetchone()[0] > 0
        
        if not has_validation:
            findings.append(StandardFinding(
                rule_name='typescript-untyped-json-parse',
                message='JSON.parse result not validated or typed',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='type-safety',
                snippet='JSON.parse(data)',
                fix_suggestion='JSON.parse returns any. Use schema validation (zod, joi) or type guards',
                cwe_id='CWE-843'
            ))
    
    return findings


def _find_untyped_api_responses(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find API calls without typed responses."""
    findings = []
    
    # Common API call patterns
    api_patterns = ['fetch', 'axios', 'request', 'http.get', 'http.post', 'ajax']
    
    for pattern in api_patterns:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.file IN ({})
              AND f.callee_function LIKE '%{}%'
        """.format(','.join(['?' for _ in ts_files]), pattern), list(ts_files))
        
        api_calls = cursor.fetchall()
        
        for file, line, func in api_calls:
            # Check if response is typed
            cursor.execute("""
                SELECT COUNT(*)
                FROM assignments a
                WHERE a.file = ?
                  AND a.line BETWEEN ? AND ?
                  AND (a.target_var LIKE '%: %' 
                       OR a.source_expr LIKE '%as %'
                       OR a.source_expr LIKE '%<%.%>%')
            """, (file, line - 2, line + 10))
            
            has_typing = cursor.fetchone()[0] > 0
            
            if not has_typing:
                findings.append(StandardFinding(
                    rule_name='typescript-untyped-api-response',
                    message=f'API call ({pattern}) without typed response',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='type-safety',
                    snippet=f'{pattern}(url)',
                    fix_suggestion='Type API responses with interfaces or use libraries with TypeScript generics',
                    cwe_id='CWE-843'
                ))
    
    return findings


def _find_missing_interfaces(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find objects that should have interface definitions."""
    findings = []
    
    # Find complex object assignments without interfaces
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({})
          AND a.source_expr LIKE '%{%}%'
          AND LENGTH(a.source_expr) > 50
          AND a.target_var NOT LIKE '%: %'
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    complex_objects = cursor.fetchall()
    
    for file, line, var, expr in complex_objects:
        # Check if it's a complex object (has multiple properties)
        if expr.count(':') > 2:
            findings.append(StandardFinding(
                rule_name='typescript-missing-interface',
                message=f"Complex object '{var}' without interface definition",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='type-safety',
                snippet=f'{var} = {{ ... }}',
                fix_suggestion='Define an interface for complex objects to ensure type safety',
                cwe_id='CWE-843'
            ))
    
    return findings


def _find_type_suppression_comments(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find @ts-ignore, @ts-nocheck, and @ts-expect-error comments."""
    findings = []
    
    suppressions = [
        ('@ts-ignore', Severity.HIGH, 'Completely disables type checking for next line'),
        ('@ts-nocheck', Severity.CRITICAL, 'Disables ALL type checking for entire file'),
        ('@ts-expect-error', Severity.MEDIUM, 'Suppresses expected errors but may hide real issues')
    ]
    
    for suppression, severity, description in suppressions:
        cursor.execute("""
            SELECT s.file, s.line, s.name
            FROM symbols s
            WHERE s.file IN ({})
              AND s.symbol_type = 'comment'
              AND s.name LIKE '%{}%'
        """.format(','.join(['?' for _ in ts_files]), suppression), list(ts_files))
        
        suppression_comments = cursor.fetchall()
        
        for file, line, comment in suppression_comments:
            findings.append(StandardFinding(
                rule_name=f'typescript-suppression-{suppression.replace("@", "").replace("-", "_")}',
                message=f'TypeScript error suppression: {suppression}',
                file_path=file,
                line=line,
                severity=severity,
                category='type-safety',
                snippet=f'// {suppression}',
                fix_suggestion=description,
                cwe_id='CWE-843'
            ))
    
    return findings


def _find_untyped_catch_blocks(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find catch blocks without typed errors."""
    findings = []
    
    # Look for catch blocks
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.file IN ({})
          AND s.symbol_type = 'catch'
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    catch_blocks = cursor.fetchall()
    
    for file, line, name in catch_blocks:
        # Check if error is typed (TypeScript 4.0+ allows typed catch)
        if 'unknown' not in name and ':' not in name:
            findings.append(StandardFinding(
                rule_name='typescript-untyped-catch',
                message='Catch block with untyped error (defaults to any)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='type-safety',
                snippet='catch (error)',
                fix_suggestion='In TypeScript 4.0+, use catch (error: unknown) and type guards',
                cwe_id='CWE-843'
            ))
    
    return findings


def _find_missing_generic_types(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find usage of generic types without type parameters."""
    findings = []
    
    # Common generics that should have type parameters
    generic_types = ['Array', 'Promise', 'Map', 'Set', 'WeakMap', 'WeakSet', 'Record']
    
    for generic in generic_types:
        cursor.execute("""
            SELECT s.file, s.line, s.name
            FROM symbols s
            WHERE s.file IN ({})
              AND (s.name LIKE '%: {}%' OR s.name LIKE '%new {}%')
              AND s.name NOT LIKE '%<%.%>%'
        """.format(','.join(['?' for _ in ts_files]), generic, generic), list(ts_files))
        
        untyped_generics = cursor.fetchall()
        
        for file, line, name in untyped_generics:
            findings.append(StandardFinding(
                rule_name=f'typescript-untyped-{generic.lower()}',
                message=f'{generic} without type parameter defaults to any',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='type-safety',
                snippet=f': {generic}',
                fix_suggestion=f'Specify type parameter: {generic}<Type> for better type safety',
                cwe_id='CWE-843'
            ))
    
    return findings


def _find_untyped_event_handlers(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find event handlers without proper typing."""
    findings = []
    
    # Common event handler patterns
    event_patterns = ['onClick', 'onChange', 'onSubmit', 'addEventListener', 'on(']
    
    for pattern in event_patterns:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.file IN ({})
              AND (f.callee_function LIKE '%{}%' OR f.argument_expr LIKE '%{}%')
        """.format(','.join(['?' for _ in ts_files]), pattern, pattern), list(ts_files))
        
        event_handlers = cursor.fetchall()
        
        for file, line, func, args in event_handlers:
            if args and 'event' in args.lower() and ':' not in args:
                findings.append(StandardFinding(
                    rule_name='typescript-untyped-event',
                    message='Event handler without typed event parameter',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='type-safety',
                    snippet='(event) => {...}',
                    fix_suggestion='Type event parameters: (event: MouseEvent), etc.',
                    cwe_id='CWE-843'
                ))
    
    return findings


def _find_type_mismatches(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find potential type mismatches in assignments."""
    findings = []
    
    # Look for suspicious assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({})
          AND ((a.target_var LIKE '%string%' AND a.source_expr LIKE '%number%')
               OR (a.target_var LIKE '%number%' AND a.source_expr LIKE '%string%')
               OR (a.target_var LIKE '%boolean%' AND a.source_expr NOT LIKE '%true%' AND a.source_expr NOT LIKE '%false%'))
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    mismatches = cursor.fetchall()
    
    for file, line, var, expr in mismatches:
        findings.append(StandardFinding(
            rule_name='typescript-type-mismatch',
            message=f'Potential type mismatch in assignment to {var}',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='type-safety',
            snippet=f'{var} = ...',
            fix_suggestion='Ensure assignment matches declared type to prevent runtime errors',
            cwe_id='CWE-843'
        ))
    
    return findings


def _find_unsafe_property_access(cursor, ts_files: Set[str]) -> List[StandardFinding]:
    """Find unsafe property access patterns."""
    findings = []
    
    # Look for bracket notation without guards
    cursor.execute("""
        SELECT s.file, s.line, s.name, s.property_access
        FROM symbols s
        WHERE s.file IN ({})
          AND s.property_access LIKE '%[%]%'
    """.format(','.join(['?' for _ in ts_files])), list(ts_files))
    
    bracket_accesses = cursor.fetchall()
    
    for file, line, name, prop_access in bracket_accesses:
        # Check if it's dynamic property access
        if prop_access and not prop_access.strip().startswith('"') and not prop_access.strip().startswith("'"):
            findings.append(StandardFinding(
                rule_name='typescript-unsafe-property-access',
                message='Dynamic property access without type safety',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='type-safety',
                snippet='obj[dynamicKey]',
                fix_suggestion='Use optional chaining (?.) or type guards when accessing dynamic properties',
                cwe_id='CWE-843'
            ))
    
    return findings


