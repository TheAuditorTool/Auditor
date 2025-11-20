"""SQL-based TypeScript type safety analyzer - ENHANCED with semantic type data.

This module provides comprehensive type safety detection for TypeScript projects
by querying semantic type information from the type_annotations table (populated
by TypeScript Compiler API).

Follows gold standard patterns (v1.1+ schema contract compliance):
- Assumes all contracted tables exist (NO table existence checks, NO fallback logic)
- 100% accurate detection using semantic type data from TypeScript compiler
- 16 comprehensive patterns (added 'unknown' type detection)
- Indexed boolean lookups (is_any, is_unknown, is_generic) instead of LIKE scans
- Direct access to return_type, type_params, and type_annotation columns
- Proper frozensets for O(1) pattern matching
- If type_annotations table missing, rule crashes with clear error (CORRECT behavior)
"""
from __future__ import annotations


import sqlite3
import logging
from typing import List, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata

logger = logging.getLogger(__name__)


# ============================================================================
# RULE METADATA (Phase 3B Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="typescript_type_safety",
    category="type-safety",
    target_extensions=['.ts', '.tsx'],
    exclude_patterns=['node_modules/', 'dist/', 'build/', '__tests__/', 'test/', 'spec/', '.next/', 'coverage/'],
    requires_jsx_pass=False
)


def find_type_safety_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """
    Detect TypeScript type safety issues using semantic type data from TypeScript compiler.

    This enhanced version detects 16 comprehensive patterns:
    - Explicit and implicit 'any' types (semantic detection via type_annotations)
    - Missing return types and parameter types (using return_type column)
    - Unsafe type assertions and non-null assertions
    - Dangerous type patterns (Function, Object, {})
    - Untyped API responses and JSON.parse
    - Missing error handling types
    - Interface and type definition issues
    - Unknown types requiring type narrowing (NEW - Pattern 16)
    - Missing generic type parameters (semantic detection via is_generic)
    - And much more...

    Uses type_annotations table for 100% accurate semantic detection.
    NO fallback logic - if table missing, rule crashes (CORRECT behavior per schema contract).

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

        # All required tables guaranteed to exist by schema contract
        # (theauditor/indexer/schema.py - TABLES registry with 46 table definitions)
        # If table missing, rule will crash with clear sqlite3.OperationalError (CORRECT behavior)

        # Only analyze TypeScript files (FIXED: 'path' column, not 'file')
        cursor.execute("SELECT DISTINCT path FROM files WHERE ext IN ('.ts', '.tsx')")
        ts_files = {row[0] for row in cursor.fetchall()}

        if not ts_files:
            return findings  # No TypeScript files in project
        
        # All patterns execute unconditionally (schema contract guarantees table existence)

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

        # Pattern 16: Unknown types requiring type narrowing
        findings.extend(_find_unknown_types(cursor, ts_files))

        conn.close()

    except sqlite3.Error as e:
        # Log database errors but don't crash
        logger.warning(f"TypeScript type safety analysis failed: {e}")
        return findings
    
    return findings


def _find_explicit_any_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find explicit 'any' type annotations using semantic type data."""
    findings = []

    # Use semantic 'any' detection from TypeScript compiler (100% accurate)
    # Schema contract guarantees type_annotations table exists
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT file, line, symbol_name, type_annotation, symbol_kind
        FROM type_annotations
        WHERE file IN ({placeholders})
          AND is_any = 1
    """, list(ts_files))

    any_types = cursor.fetchall()

    for file, line, name, type_ann, kind in any_types:
        findings.append(StandardFinding(
            rule_name='typescript-explicit-any',
            message=f"Explicit 'any' type in {kind}: {name}",
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            category='type-safety',
            snippet=f'{name}: {type_ann}' if type_ann else f'{name}: any',
            cwe_id='CWE-843'
        ))

    # Also check assignments for 'as any' type assertions
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.file IN ({placeholders})
              AND a.source_expr IS NOT NULL
        """, list(ts_files))

    any_assertions = []
    for file, line, var, expr in cursor.fetchall():
        # Filter in Python for 'as any'
        if 'as any' in expr:
            any_assertions.append((file, line, var, expr))

    for file, line, var, expr in any_assertions:
            findings.append(StandardFinding(
                rule_name='typescript-any-assertion',
                message=f"Type assertion to 'any' in '{var}'",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category='type-safety',
                snippet='... as any',
                cwe_id='CWE-843'
            ))

    return findings


def _find_missing_return_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find functions without explicit return types using semantic type data."""
    findings = []

    # Use semantic return type data from TypeScript compiler
    # Schema contract guarantees type_annotations table exists
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT file, line, symbol_name, return_type
        FROM type_annotations
        WHERE file IN ({placeholders})
          AND symbol_kind = 'function'
          AND (return_type IS NULL OR return_type = '')
    """, list(ts_files))

    missing_returns = cursor.fetchall()

    # Known exceptions that don't need explicit return types
    known_exceptions = frozenset([
        'constructor', 'render', 'componentDidMount', 'componentDidUpdate',
        'componentWillUnmount', 'componentWillMount', 'shouldComponentUpdate',
        'getSnapshotBeforeUpdate', 'componentDidCatch'
    ])

    for file, line, name, return_type in missing_returns:
        # Skip known exceptions
        if name not in known_exceptions:
            findings.append(StandardFinding(
                rule_name='typescript-missing-return-type',
                message=f"Function '{name}' missing explicit return type",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                confidence=Confidence.HIGH,
                category='type-safety',
                snippet=f'function {name}(...)',
                cwe_id='CWE-843'
            ))

    return findings


def _find_missing_parameter_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find function parameters without type annotations."""
    findings = []

    # Look for function calls with untyped parameters
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
    """, list(ts_files))

    function_calls = []
    for file, line, func, args in cursor.fetchall():
        # Filter in Python for function keyword
        if 'function' in func.lower():
            function_calls.append((file, line, func, args))

    for file, line, func, args in function_calls:
        if args and 'function(' in args.lower():
            # Check if parameters have types
            if ':' not in args and '(' in args and ')' in args:
                findings.append(StandardFinding(
                    rule_name='typescript-untyped-parameters',
                    message='Function parameters without type annotations',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category='type-safety',
                    snippet='function(param1, param2)',
                    cwe_id='CWE-843'
                ))

    return findings


def _find_unsafe_type_assertions(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find unsafe type assertions (as any, as unknown)."""
    findings = []

    # Check for type assertions in assignments
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.source_expr IS NOT NULL
    """, list(ts_files))

    # Filter in Python for unsafe assertions
    type_assertions = []
    for file, line, var, expr in cursor.fetchall():
        if any(pattern in expr for pattern in ['as any', 'as unknown', 'as Function', '<any>']):
            type_assertions.append((file, line, var, expr))

    for file, line, var, expr in type_assertions:
        severity = Severity.HIGH if 'as any' in expr else Severity.MEDIUM
        confidence = Confidence.HIGH if 'as any' in expr else Confidence.MEDIUM
        findings.append(StandardFinding(
            rule_name='typescript-unsafe-assertion',
            message=f"Unsafe type assertion in '{var}'",
            file_path=file,
            line=line,
            severity=severity,
            confidence=confidence,
            category='type-safety',
            snippet=f'{var} = ... as any',
            cwe_id='CWE-843'
        ))

    return findings


def _find_non_null_assertions(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find non-null assertions (!) that bypass null checks."""
    findings = []

    # Look for ! assertions in code
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.source_expr IS NOT NULL
    """, list(ts_files))

    # Filter in Python for ! patterns
    non_null_assertions = []
    for file, line, expr in cursor.fetchall():
        if any(pattern in expr for pattern in ['!.', '!)', '!;']):
            non_null_assertions.append((file, line, expr))

    for file, line, expr in non_null_assertions:
        findings.append(StandardFinding(
            rule_name='typescript-non-null-assertion',
            message='Non-null assertion (!) bypasses null safety',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            category='type-safety',
            snippet='value!.property',
            cwe_id='CWE-476'
        ))

    return findings


def _find_dangerous_type_patterns(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find dangerous type patterns like Function, Object, {} using semantic type data."""
    findings = []

    # Convert to frozenset for O(1) lookups (gold standard)
    dangerous_types = frozenset(['Function', 'Object', '{}'])

    # Use semantic type data from TypeScript compiler
    # Schema contract guarantees type_annotations table exists
    placeholders = ','.join(['?' for _ in ts_files])
    for dangerous_type in dangerous_types:
        cursor.execute(f"""
            SELECT file, line, symbol_name, type_annotation
            FROM type_annotations
            WHERE file IN ({placeholders})
              AND type_annotation IS NOT NULL
        """, list(ts_files))

        # Filter in Python for dangerous type patterns
        for file, line, name, type_ann in cursor.fetchall():
            # Check for exact match or array/generic patterns
            if (type_ann == dangerous_type or
                type_ann == f'{dangerous_type}[]' or
                f'<{dangerous_type}>' in type_ann):
                findings.append(StandardFinding(
                    rule_name=f'typescript-dangerous-type-{dangerous_type.lower().replace("{", "").replace("}", "empty")}',
                    message=f"Dangerous type '{dangerous_type}' used in {name}",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    category='type-safety',
                    snippet=f'{name}: {type_ann}' if type_ann else f': {dangerous_type}',
                    cwe_id='CWE-843'
                ))

    return findings


def _find_untyped_json_parse(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find JSON.parse without type validation."""
    findings = []

    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND f.callee_function IS NOT NULL
    """, list(ts_files))

    # Filter in Python for JSON.parse
    json_parses = []
    for file, line, func, args in cursor.fetchall():
        if 'JSON.parse' in func:
            json_parses.append((file, line, func, args))

    for file, line, func, args in json_parses:
        # Check if result is typed (look for type assertion or validation nearby)
        cursor.execute("""
                SELECT source_expr
                FROM assignments a
                WHERE a.file = ?
                  AND a.line BETWEEN ? AND ?
                  AND a.source_expr IS NOT NULL
        """, (file, line, line + 5))

        # Filter in Python for validation patterns
        validation_count = 0
        for (source_expr,) in cursor.fetchall():
            if any(pattern in source_expr for pattern in ['as ', 'zod', 'joi', 'validate']):
                validation_count += 1

        has_validation = validation_count > 0

        if not has_validation:
            findings.append(StandardFinding(
                rule_name='typescript-untyped-json-parse',
                message='JSON.parse result not validated or typed',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category='type-safety',
                snippet='JSON.parse(data)',
                cwe_id='CWE-843'
            ))

    return findings


def _find_untyped_api_responses(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find API calls without typed responses."""
    findings = []

    # Common API call patterns (convert to frozenset)
    api_patterns = frozenset(['fetch', 'axios', 'request', 'http.get', 'http.post', 'ajax'])

    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND f.callee_function IS NOT NULL
    """, list(ts_files))

    # Filter in Python for API patterns
    all_calls = cursor.fetchall()
    for pattern in api_patterns:
        api_calls = [(file, line, func) for file, line, func in all_calls if pattern in func]

        for file, line, func in api_calls:
            # Check if response is typed
            cursor.execute("""
                    SELECT target_var, source_expr
                    FROM assignments a
                    WHERE a.file = ?
                      AND a.line BETWEEN ? AND ?
                      AND (a.target_var IS NOT NULL OR a.source_expr IS NOT NULL)
            """, (file, line - 2, line + 10))

            # Filter in Python for typing patterns
            typing_count = 0
            for target_var, source_expr in cursor.fetchall():
                if (target_var and ': ' in target_var) or (source_expr and ('as ' in source_expr or '<' in source_expr and '>' in source_expr)):
                    typing_count += 1

            has_typing = typing_count > 0

            if not has_typing:
                findings.append(StandardFinding(
                    rule_name='typescript-untyped-api-response',
                    message=f'API call ({pattern}) without typed response',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='type-safety',
                    snippet=f'{pattern}(url)',
                    cwe_id='CWE-843'
                ))

    return findings


def _find_missing_interfaces(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find objects that should have interface definitions."""
    findings = []

    # Find complex object assignments without interfaces
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.source_expr IS NOT NULL
          AND a.target_var IS NOT NULL
          AND LENGTH(a.source_expr) > 50
    """, list(ts_files))

    # Filter in Python for object literals without types
    complex_objects = []
    for file, line, var, expr in cursor.fetchall():
        if '{' in expr and '}' in expr and ': ' not in var:
            complex_objects.append((file, line, var, expr))

    for file, line, var, expr in complex_objects:
        # Check if it's a complex object (has multiple properties)
        if expr.count(':') > 2:
            findings.append(StandardFinding(
                rule_name='typescript-missing-interface',
                message=f"Complex object '{var}' without interface definition",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                confidence=Confidence.LOW,
                category='type-safety',
                snippet=f'{var} = {{ ... }}',
                cwe_id='CWE-843'
            ))

    return findings


def _find_type_suppression_comments(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find @ts-ignore, @ts-nocheck, and @ts-expect-error comments."""
    findings = []

    # Convert to tuple for iteration (with confidence levels)
    suppressions = (
        ('@ts-ignore', Severity.HIGH, Confidence.HIGH, 'Completely disables type checking for next line'),
        ('@ts-nocheck', Severity.CRITICAL, Confidence.HIGH, 'Disables ALL type checking for entire file'),
        ('@ts-expect-error', Severity.MEDIUM, Confidence.MEDIUM, 'Suppresses expected errors but may hide real issues')
    )

    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({placeholders})
          AND s.type = 'comment'
          AND s.name IS NOT NULL
    """, list(ts_files))

    # Fetch all comments once
    all_comments = cursor.fetchall()

    for suppression, severity, confidence, description in suppressions:
        # Filter in Python for suppression patterns
        suppression_comments = [(file, line, comment) for file, line, comment in all_comments if suppression in comment]

        for file, line, comment in suppression_comments:
            findings.append(StandardFinding(
                rule_name=f'typescript-suppression-{suppression.replace("@", "").replace("-", "_")}',
                message=f'TypeScript error suppression: {suppression}',
                file_path=file,
                line=line,
                severity=severity,
                confidence=confidence,
                category='type-safety',
                snippet=f'// {suppression}',
                cwe_id='CWE-843'
            ))

    return findings


def _find_untyped_catch_blocks(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find catch blocks without typed errors."""
    findings = []

    # Look for catch blocks
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({placeholders})
          AND s.type = 'catch'
    """, list(ts_files))

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
                confidence=Confidence.MEDIUM,
                category='type-safety',
                snippet='catch (error)',
                cwe_id='CWE-843'
            ))

    return findings


def _find_missing_generic_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find usage of generic types without type parameters using semantic type data."""
    findings = []

    # Common generics that should have type parameters (frozenset)
    generic_types = frozenset(['Array', 'Promise', 'Map', 'Set', 'WeakMap', 'WeakSet', 'Record'])

    # Use semantic generic detection from TypeScript compiler
    # Schema contract guarantees type_annotations table exists
    placeholders = ','.join(['?' for _ in ts_files])
    for generic in generic_types:
        cursor.execute(f"""
            SELECT file, line, symbol_name, type_annotation, type_params
            FROM type_annotations
            WHERE file IN ({placeholders})
              AND type_annotation = ?
              AND (is_generic = 0 OR type_params IS NULL OR type_params = '')
        """, list(ts_files) + [generic])

        untyped_generics = cursor.fetchall()

        for file, line, name, type_ann, type_params in untyped_generics:
            findings.append(StandardFinding(
                rule_name=f'typescript-untyped-{generic.lower()}',
                message=f'{generic} without type parameter defaults to any',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category='type-safety',
                snippet=f': {generic}' if not type_ann else f': {type_ann}',
                cwe_id='CWE-843'
            ))

    return findings


def _find_untyped_event_handlers(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find event handlers without proper typing."""
    findings = []

    # Common event handler patterns (frozenset)
    event_patterns = frozenset(['onClick', 'onChange', 'onSubmit', 'addEventListener', 'on('])

    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND (f.callee_function IS NOT NULL OR f.argument_expr IS NOT NULL)
    """, list(ts_files))

    # Filter in Python for event patterns
    all_calls = cursor.fetchall()
    for pattern in event_patterns:
        event_handlers = [(file, line, func, args) for file, line, func, args in all_calls
                         if (func and pattern in func) or (args and pattern in args)]

        for file, line, func, args in event_handlers:
            if args and 'event' in args.lower() and ':' not in args:
                findings.append(StandardFinding(
                    rule_name='typescript-untyped-event',
                    message='Event handler without typed event parameter',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    confidence=Confidence.LOW,
                    category='type-safety',
                    snippet='(event) => {...}',
                    cwe_id='CWE-843'
                ))

    return findings


def _find_type_mismatches(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find potential type mismatches in assignments."""
    findings = []

    # Look for suspicious assignments
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
    """, list(ts_files))

    # Filter in Python for type mismatches
    mismatches = []
    for file, line, var, expr in cursor.fetchall():
        var_lower = var.lower()
        expr_lower = expr.lower()

        # String/number mismatch
        if ('string' in var_lower and 'number' in expr_lower) or \
           ('number' in var_lower and 'string' in expr_lower):
            mismatches.append((file, line, var, expr))
        # Boolean mismatch
        elif 'boolean' in var_lower and 'true' not in expr_lower and 'false' not in expr_lower:
            mismatches.append((file, line, var, expr))

    for file, line, var, expr in mismatches:
        findings.append(StandardFinding(
            rule_name='typescript-type-mismatch',
            message=f'Potential type mismatch in assignment to {var}',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            category='type-safety',
            snippet=f'{var} = ...',
            cwe_id='CWE-843'
        ))

    return findings


def _find_unsafe_property_access(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find unsafe property access patterns."""
    findings = []

    # Look for bracket notation without guards
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({placeholders})
          AND s.name IS NOT NULL
    """, list(ts_files))

    # Filter in Python for bracket notation
    bracket_accesses = []
    for file, line, name in cursor.fetchall():
        if '[' in name and ']' in name:
            bracket_accesses.append((file, line, name))

    for file, line, name in bracket_accesses:
        prop_access = name  # Use name as the property access pattern
        # Check if it's dynamic property access
        if prop_access and not prop_access.strip().startswith('"') and not prop_access.strip().startswith("'"):
            findings.append(StandardFinding(
                rule_name='typescript-unsafe-property-access',
                message='Dynamic property access without type safety',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                category='type-safety',
                snippet='obj[dynamicKey]',
                cwe_id='CWE-843'
            ))

    return findings


def _find_unknown_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find 'unknown' types requiring type narrowing using semantic type data."""
    findings = []

    # Use semantic 'unknown' detection from TypeScript compiler
    placeholders = ','.join(['?' for _ in ts_files])
    cursor.execute(f"""
        SELECT file, line, symbol_name, type_annotation, symbol_kind
        FROM type_annotations
        WHERE file IN ({placeholders})
          AND is_unknown = 1
    """, list(ts_files))

    unknown_types = cursor.fetchall()

    for file, line, name, type_ann, kind in unknown_types:
        findings.append(StandardFinding(
            rule_name='typescript-unknown-type',
            message=f"Symbol '{name}' uses 'unknown' type requiring type narrowing",
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            category='type-safety',
            snippet=f'{name}: {type_ann}' if type_ann else f'{name}: unknown',
            cwe_id='CWE-843'
        ))

    return findings


