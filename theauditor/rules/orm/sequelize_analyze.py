"""Sequelize ORM Analyzer - Database-First Approach.

Detects Sequelize ORM anti-patterns and performance issues using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows golden standard patterns from compose_analyze.py:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
- Proper confidence levels
"""

import sqlite3
import json
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Use Frozensets)
# ============================================================================

# Sequelize query methods that need pagination
UNBOUNDED_METHODS = frozenset([
    'findAll', 'findAndCountAll', 'scope'
])

# Sequelize write operations that may need transactions
WRITE_METHODS = frozenset([
    'create', 'bulkCreate', 'update', 'bulkUpdate',
    'destroy', 'bulkDestroy', 'upsert', 'save',
    'increment', 'decrement', 'restore'
])

# Methods that can have race conditions
RACE_CONDITION_METHODS = frozenset([
    'findOrCreate', 'findOrBuild', 'findCreateFind'
])

# Raw query methods that could have SQL injection
RAW_QUERY_METHODS = frozenset([
    'sequelize.query', 'query', 'Sequelize.literal',
    'literal', 'sequelize.fn', 'Sequelize.fn',
    'sequelize.col', 'Sequelize.col', 'sequelize.where'
])

# Association methods for detecting relationships
ASSOCIATION_METHODS = frozenset([
    'belongsTo', 'hasOne', 'hasMany', 'belongsToMany'
])

# Transaction-related methods
TRANSACTION_METHODS = frozenset([
    'transaction', 'commit', 'rollback', 't.commit', 't.rollback'
])

# Dangerous query options
DANGEROUS_OPTIONS = frozenset([
    'all: true', 'nested: true', 'raw: true', 'paranoid: false'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_sequelize_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Sequelize ORM anti-patterns and performance issues.

    Detects:
    - Death queries (include all with nested)
    - N+1 query patterns
    - Unbounded queries without limits
    - Race conditions in findOrCreate
    - Missing transactions for multiple writes
    - Unsafe raw SQL queries
    - Excessive eager loading

    Args:
        context: Standardized rule context with database path

    Returns:
        List of Sequelize ORM issues found
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Check if required tables exist (Golden Standard)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'function_call_args', 'cfg_blocks', 'assignments',
                'sql_queries', 'files'
            )
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Minimum required table for ORM analysis
        if 'function_call_args' not in existing_tables:
            return findings  # Can't analyze without function call data

        # Track which tables are available for graceful degradation
        has_function_calls = 'function_call_args' in existing_tables
        has_cfg_blocks = 'cfg_blocks' in existing_tables
        has_assignments = 'assignments' in existing_tables
        has_sql_queries = 'sql_queries' in existing_tables
        has_files = 'files' in existing_tables

        # ========================================================
        # CHECK 1: Death Queries (all: true + nested: true)
        # ========================================================
        if has_function_calls:
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE (callee_function LIKE '%.findAll'
                       OR callee_function LIKE '%.findOne'
                       OR callee_function LIKE '%.findAndCountAll')
                  AND argument_expr IS NOT NULL
                ORDER BY file, line
            """)

            for file, line, method, args in cursor.fetchall():
                if args and isinstance(args, str):
                    # Check for death query pattern
                    has_all = 'all: true' in args or 'all:true' in args
                    has_nested = 'nested: true' in args or 'nested:true' in args

                    if has_all and has_nested:
                        findings.append(StandardFinding(
                            rule_name='sequelize-death-query',
                            message=f'Death query: {method} with all:true and nested:true',
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category='orm-performance',
                            confidence=Confidence.HIGH,
                            fix_suggestion='Never use all:true with nested:true. Specify exact associations needed.',
                            cwe_id='CWE-400'
                        ))

        # ========================================================
        # CHECK 2: N+1 Query Patterns
        # ========================================================
        if has_function_calls:
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE (callee_function LIKE '%.findAll'
                       OR callee_function LIKE '%.findAndCountAll')
                ORDER BY file, line
            """)

            for file, line, method, args in cursor.fetchall():
                model = method.split('.')[0] if '.' in method else 'Model'

                # Check if includes are missing
                has_include = args and 'include' in str(args)

                if not has_include:
                    findings.append(StandardFinding(
                        rule_name='sequelize-n-plus-one',
                        message=f'Potential N+1: {method} without include option',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='orm-performance',
                        confidence=Confidence.MEDIUM,
                        fix_suggestion='Use include option to eager load associations and avoid N+1 queries',
                        cwe_id='CWE-400'
                    ))

        # ========================================================
        # CHECK 3: Unbounded Queries Without Limit
        # ========================================================
        if has_function_calls:
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE '%.findAll'
                   OR callee_function LIKE '%.findAndCountAll'
                ORDER BY file, line
            """)

            for file, line, method, args in cursor.fetchall():
                # Check if limit is present
                has_limit = args and ('limit' in str(args) or 'take' in str(args))

                if not has_limit:
                    findings.append(StandardFinding(
                        rule_name='sequelize-unbounded-query',
                        message=f'Unbounded query: {method} without limit',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category='orm-performance',
                        confidence=Confidence.HIGH,
                        fix_suggestion='Add limit and offset for pagination to prevent memory issues',
                        cwe_id='CWE-400'
                    ))

        # ========================================================
        # CHECK 4: Race Conditions in findOrCreate
        # ========================================================
        if has_function_calls:
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE '%.findOrCreate'
                   OR callee_function LIKE '%.findOrBuild'
                ORDER BY file, line
            """)

            for file, line, method, args in cursor.fetchall():
                # Check if there's a transaction nearby
                has_transaction = False

                if has_function_calls:
                    # Check for transaction in same file within 30 lines
                    cursor.execute("""
                        SELECT COUNT(*) FROM function_call_args
                        WHERE file = ?
                          AND callee_function LIKE '%transaction%'
                          AND ABS(line - ?) <= 30
                    """, (file, line))
                    has_transaction = cursor.fetchone()[0] > 0

                if not has_transaction:
                    findings.append(StandardFinding(
                        rule_name='sequelize-race-condition',
                        message=f'Race condition risk: {method} without transaction',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='orm-concurrency',
                        confidence=Confidence.MEDIUM if has_cfg_blocks else Confidence.LOW,
                        fix_suggestion='Wrap findOrCreate in a transaction to prevent race conditions',
                        cwe_id='CWE-362'
                    ))

        # ========================================================
        # CHECK 5: Missing Transactions for Multiple Writes
        # ========================================================
        if has_function_calls:
            # Get all write operations grouped by file
            cursor.execute("""
                SELECT file, line, callee_function
                FROM function_call_args
                WHERE callee_function LIKE '%.create'
                   OR callee_function LIKE '%.bulkCreate'
                   OR callee_function LIKE '%.update'
                   OR callee_function LIKE '%.bulkUpdate'
                   OR callee_function LIKE '%.destroy'
                   OR callee_function LIKE '%.bulkDestroy'
                   OR callee_function LIKE '%.upsert'
                   OR callee_function LIKE '%.save'
                ORDER BY file, line
            """)

            # Group operations by file
            file_operations = {}
            for file, line, method in cursor.fetchall():
                if file not in file_operations:
                    file_operations[file] = []
                file_operations[file].append({
                    'line': line,
                    'method': method
                })

            # Check for close operations without transactions
            for file, operations in file_operations.items():
                for i in range(len(operations) - 1):
                    op1 = operations[i]
                    op2 = operations[i + 1]

                    # Operations within 20 lines
                    if op2['line'] - op1['line'] <= 20:
                        # Check for transaction
                        cursor.execute("""
                            SELECT COUNT(*) FROM function_call_args
                            WHERE file = ?
                              AND callee_function LIKE '%transaction%'
                              AND line BETWEEN ? AND ?
                        """, (file, op1['line'] - 5, op2['line'] + 5))

                        has_transaction = cursor.fetchone()[0] > 0

                        if not has_transaction:
                            findings.append(StandardFinding(
                                rule_name='sequelize-missing-transaction',
                                message=f"Multiple writes without transaction: {op1['method']} and {op2['method']}",
                                file_path=file,
                                line=op1['line'],
                                severity=Severity.HIGH,
                                category='orm-data-integrity',
                                confidence=Confidence.HIGH,
                                fix_suggestion='Wrap multiple write operations in sequelize.transaction()',
                                cwe_id='CWE-662'
                            ))
                            break  # One finding per cluster

        # ========================================================
        # CHECK 6: Unsafe Raw SQL Queries
        # ========================================================
        if has_function_calls:
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE '%sequelize.query%'
                   OR callee_function LIKE '%Sequelize.literal%'
                   OR callee_function = 'query'
                   OR callee_function = 'literal'
                ORDER BY file, line
            """)

            for file, line, func, args in cursor.fetchall():
                # Check for string concatenation or interpolation
                if args:
                    args_str = str(args)
                    has_interpolation = any(pattern in args_str for pattern in [
                        '${', '"+', '" +', '` +', 'concat', '+', '${', '`'
                    ])

                    # Higher severity for literal() as it's commonly misused
                    is_literal = 'literal' in func.lower()

                    if has_interpolation:
                        findings.append(StandardFinding(
                            rule_name='sequelize-sql-injection',
                            message=f'Potential SQL injection in {func}',
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL if is_literal else Severity.HIGH,
                            category='orm-security',
                            confidence=Confidence.HIGH if is_literal else Confidence.MEDIUM,
                            fix_suggestion='Use parameterized queries with replacements or bind parameters',
                            cwe_id='CWE-89'
                        ))

        # ========================================================
        # CHECK 7: Excessive Eager Loading
        # ========================================================
        if has_function_calls:
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE (callee_function LIKE '%.findAll'
                       OR callee_function LIKE '%.findOne'
                       OR callee_function LIKE '%.findAndCountAll')
                  AND argument_expr LIKE '%include%'
                ORDER BY file, line
            """)

            for file, line, method, args in cursor.fetchall():
                if args:
                    # Count include occurrences (rough estimate)
                    include_count = str(args).count('include:')

                    # Check for excessive includes
                    if include_count > 3:
                        findings.append(StandardFinding(
                            rule_name='sequelize-excessive-eager-loading',
                            message=f'Excessive eager loading: {include_count} includes in {method}',
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category='orm-performance',
                            confidence=Confidence.MEDIUM,
                            fix_suggestion='Reduce number of eager loaded associations or use separate queries',
                            cwe_id='CWE-400'
                        ))

                    # Check for deeply nested includes
                    if 'include: [' in args and args.count('[') > 3:
                        findings.append(StandardFinding(
                            rule_name='sequelize-deep-nesting',
                            message=f'Deeply nested includes in {method}',
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category='orm-performance',
                            confidence=Confidence.LOW,
                            fix_suggestion='Flatten nested includes or use separate queries for deep relations',
                            cwe_id='CWE-400'
                        ))

        # ========================================================
        # CHECK 8: Paranoid Mode Disabled
        # ========================================================
        if has_function_calls:
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE (callee_function LIKE '%.destroy'
                       OR callee_function LIKE '%.restore')
                  AND argument_expr LIKE '%paranoid: false%'
                ORDER BY file, line
            """)

            for file, line, method, args in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='sequelize-hard-delete',
                    message=f'Hard delete with paranoid:false in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='orm-data-integrity',
                    confidence=Confidence.HIGH,
                    fix_suggestion='Consider using soft deletes (paranoid:true) for data recovery',
                    cwe_id='CWE-471'
                ))

        # ========================================================
        # CHECK 9: Raw Queries in SQL Queries Table
        # ========================================================
        if has_sql_queries:
            # Check for raw SQL that bypasses ORM
            cursor.execute("""
                SELECT file_path, line_number, query_text, command
                FROM sql_queries
                WHERE command IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
                  AND file_path NOT LIKE '%migration%'
                  AND file_path NOT LIKE '%seed%'
                ORDER BY file_path, line_number
            """)

            for file, line, query, command in cursor.fetchall():
                # Check if it's likely a Sequelize raw query
                if 'sequelize' not in query.lower():
                    findings.append(StandardFinding(
                        rule_name='sequelize-bypass',
                        message=f'Raw {command} query bypassing ORM',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category='orm-consistency',
                        confidence=Confidence.LOW,
                        fix_suggestion='Consider using Sequelize query builder instead of raw SQL',
                        cwe_id='CWE-213'
                    ))

    finally:
        conn.close()

    return findings


def register_taint_patterns(taint_registry):
    """Register Sequelize-specific taint patterns.

    This function is called by the orchestrator to register
    ORM-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """
    # Register Sequelize raw query methods as SQL sinks
    for pattern in RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, 'sql', 'javascript')

    # Register Sequelize input sources
    SEQUELIZE_SOURCES = frozenset([
        'findAll', 'findOne', 'findByPk', 'findOrCreate',
        'where', 'attributes', 'order', 'group'
    ])

    for pattern in SEQUELIZE_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')

    # Register transaction methods
    for pattern in TRANSACTION_METHODS:
        taint_registry.register_sink(pattern, 'transaction', 'javascript')