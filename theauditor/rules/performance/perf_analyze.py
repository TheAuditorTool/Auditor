"""Performance Analyzer - Database-First Approach.

Detects performance anti-patterns and inefficiencies using ONLY
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

# Database operations that shouldn't be in loops
DB_OPERATIONS = frozenset([
    # SQL operations
    'query', 'execute', 'fetch', 'fetchone', 'fetchall', 'fetchmany',
    'select', 'insert', 'update', 'delete',

    # ORM operations - Sequelize
    'findAll', 'findOne', 'findByPk', 'findOrCreate',
    'create', 'bulkCreate', 'bulkUpdate', 'destroy',

    # ORM operations - Prisma
    'findMany', 'findFirst', 'findUnique', 'findUniqueOrThrow',
    'createMany', 'updateMany', 'deleteMany', 'upsert',

    # ORM operations - TypeORM
    'find', 'findOneBy', 'findAndCount', 'save', 'remove',

    # MongoDB operations
    'find_one', 'find_one_and_update', 'insert_one', 'update_one',
    'delete_one', 'aggregate', 'count_documents',

    # Generic ORM
    'filter', 'filter_by', 'get', 'all', 'first', 'one',
    'count', 'exists', 'scalar'
])

# Expensive I/O operations
EXPENSIVE_OPS = frozenset([
    # File I/O
    'open', 'read', 'write', 'readFile', 'writeFile',
    'readFileSync', 'writeFileSync', 'createReadStream', 'createWriteStream',

    # Network operations
    'fetch', 'axios', 'request', 'get', 'post', 'put', 'delete',
    'http.get', 'http.post', 'https.get', 'https.post',

    # Regex compilation
    'compile', 're.compile', 'RegExp', 'new RegExp',

    # Sleep/delays
    'sleep', 'time.sleep', 'setTimeout', 'setInterval',

    # Cryptographic operations
    'hash', 'encrypt', 'decrypt', 'bcrypt', 'pbkdf2', 'scrypt',
    'crypto.createHash', 'crypto.createCipher', 'crypto.pbkdf2'
])

# Synchronous operations that block event loop
SYNC_BLOCKERS = frozenset([
    'readFileSync', 'writeFileSync', 'existsSync', 'mkdirSync',
    'readdirSync', 'statSync', 'unlinkSync', 'rmSync',
    'execSync', 'spawnSync', 'time.sleep', 'requests.get', 'requests.post'
])

# String concatenation operations
STRING_CONCAT_OPS = frozenset([
    '+=', '+', 'concat', 'join', 'append'
])

# Memory intensive operations
MEMORY_OPS = frozenset([
    'sort', 'sorted', 'reverse', 'deepcopy', 'clone',
    'JSON.parse', 'JSON.stringify', 'Buffer.from', 'Buffer.alloc'
])

# Array iteration methods (JavaScript)
ARRAY_METHODS = frozenset([
    'forEach', 'map', 'filter', 'reduce', 'some', 'every',
    'find', 'findIndex', 'flatMap', 'reduceRight'
])

# Promise/async indicators
ASYNC_INDICATORS = frozenset([
    'async', 'await', 'promise', 'then', 'catch', 'finally',
    'Promise.all', 'Promise.race', 'Promise.allSettled'
])

# Common property chains that indicate performance issues
PROPERTY_CHAIN_PATTERNS = frozenset([
    'req.body', 'req.params', 'req.query', 'req.headers',
    'res.status', 'res.send', 'res.json', 'res.render'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_performance_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect performance anti-patterns and inefficiencies.

    Detects:
    - Database queries in loops (N+1 problem)
    - Expensive operations in loops
    - Inefficient string concatenation
    - Synchronous I/O blocking event loop
    - Unbounded operations
    - Deep property access chains
    - Unoptimized taint flows

    Args:
        context: Standardized rule context with database path

    Returns:
        List of performance issues found
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
                'cfg_blocks', 'function_call_args', 'assignments',
                'symbols', 'api_endpoints', 'sql_queries', 'files'
            )
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Minimum required tables for any analysis
        if 'function_call_args' not in existing_tables:
            return findings  # Can't analyze without function call data

        # Track which tables are available for graceful degradation
        has_cfg_blocks = 'cfg_blocks' in existing_tables
        has_assignments = 'assignments' in existing_tables
        has_symbols = 'symbols' in existing_tables
        has_api_endpoints = 'api_endpoints' in existing_tables
        has_sql_queries = 'sql_queries' in existing_tables
        has_files = 'files' in existing_tables

        # ========================================================
        # CHECK 1: Database Queries in Loops (N+1 Problem)
        # ========================================================
        if has_cfg_blocks:
            findings.extend(_find_queries_in_loops(cursor, has_cfg_blocks))

        # ========================================================
        # CHECK 2: Expensive Operations in Loops
        # ========================================================
        if has_cfg_blocks:
            findings.extend(_find_expensive_operations_in_loops(cursor))

        # ========================================================
        # CHECK 3: Inefficient String Concatenation
        # ========================================================
        if has_assignments and has_cfg_blocks:
            findings.extend(_find_inefficient_string_concat(cursor))

        # ========================================================
        # CHECK 4: Synchronous I/O Operations
        # ========================================================
        findings.extend(_find_synchronous_io_patterns(cursor, has_api_endpoints))

        # ========================================================
        # CHECK 5: Unbounded Operations
        # ========================================================
        findings.extend(_find_unbounded_operations(cursor))

        # ========================================================
        # CHECK 6: Deep Property Access Chains
        # ========================================================
        if has_symbols:
            findings.extend(_find_deep_property_chains(cursor))

        # ========================================================
        # CHECK 7: Unoptimized Taint Flows
        # ========================================================
        if has_symbols:
            findings.extend(_find_unoptimized_taint_flows(cursor))

        # ========================================================
        # CHECK 8: Repeated Expensive Calls
        # ========================================================
        findings.extend(_find_repeated_expensive_calls(cursor))

        # ========================================================
        # CHECK 9: Large Object Operations
        # ========================================================
        if has_assignments:
            findings.extend(_find_large_object_operations(cursor))

    finally:
        conn.close()

    return findings


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def _find_queries_in_loops(cursor, has_cfg_blocks: bool) -> List[StandardFinding]:
    """Find database queries executed inside loops (N+1 problem)."""
    findings = []

    if not has_cfg_blocks:
        return findings

    # Build query conditions for DB operations
    db_ops_list = list(DB_OPERATIONS)
    placeholders = ','.join('?' * len(db_ops_list))

    # Find all loop blocks
    cursor.execute("""
        SELECT DISTINCT cb.file, cb.function_name, cb.start_line, cb.end_line
        FROM cfg_blocks cb
        WHERE cb.block_type IN ('loop', 'for_loop', 'while_loop', 'do_while')
           OR cb.block_type LIKE '%loop%'
        ORDER BY cb.file, cb.start_line
    """)

    loops = cursor.fetchall()

    for file, function, loop_start, loop_end in loops:
        # Find DB operations within loop
        cursor.execute(f"""
            SELECT f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line >= ?
              AND f.line <= ?
              AND f.callee_function IN ({placeholders})
            ORDER BY f.line
        """, [file, loop_start, loop_end] + db_ops_list)

        for line, operation, args in cursor.fetchall():
            # Check for nested loops
            cursor.execute("""
                SELECT COUNT(*) FROM cfg_blocks
                WHERE file = ?
                  AND start_line < ?
                  AND end_line > ?
                  AND block_type LIKE '%loop%'
            """, (file, loop_start, loop_end))

            nested_count = cursor.fetchone()[0]
            severity = Severity.CRITICAL if nested_count > 0 else Severity.HIGH

            findings.append(StandardFinding(
                rule_name='perf-query-in-loop',
                message=f'Database query "{operation}" in {"nested " if nested_count else ""}loop - N+1 problem',
                file_path=file,
                line=line,
                severity=severity,
                category='performance',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'  # Excessive Platform Resource Consumption
            ))

    # Also check array methods with DB operations
    array_methods_list = list(ARRAY_METHODS)
    array_placeholders = ','.join('?' * len(array_methods_list))

    cursor.execute(f"""
        SELECT DISTINCT f1.file, f1.line, f1.callee_function, f1.caller_function
        FROM function_call_args f1
        WHERE f1.callee_function IN ({array_placeholders})
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.caller_function = f1.caller_function
                AND f2.callee_function IN ({placeholders})
                AND ABS(f2.line - f1.line) <= 10
          )
        ORDER BY f1.file, f1.line
    """, array_methods_list + db_ops_list)

    for file, line, method, _ in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-query-in-array-method',
            message=f'Database operations in array.{method}() creates implicit loop',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_expensive_operations_in_loops(cursor) -> List[StandardFinding]:
    """Find expensive operations that should be moved outside loops."""
    findings = []

    # Get all loops
    cursor.execute("""
        SELECT DISTINCT file, start_line, end_line
        FROM cfg_blocks
        WHERE block_type LIKE '%loop%'
    """)

    loops = cursor.fetchall()

    for file, loop_start, loop_end in loops:
        # Check for expensive operations
        expensive_ops_list = list(EXPENSIVE_OPS)
        placeholders = ','.join('?' * len(expensive_ops_list))

        cursor.execute(f"""
            SELECT line, callee_function, argument_expr
            FROM function_call_args
            WHERE file = ?
              AND line >= ?
              AND line <= ?
              AND callee_function IN ({placeholders})
            ORDER BY line
        """, [file, loop_start, loop_end] + expensive_ops_list)

        for line, operation, args in cursor.fetchall():
            # Determine severity based on operation type
            if operation in ['sleep', 'time.sleep', 'execSync', 'spawnSync']:
                severity = Severity.CRITICAL
                message = f'Blocking operation "{operation}" in loop severely degrades performance'
            elif operation in ['fetch', 'axios', 'request', 'http.get', 'https.get']:
                severity = Severity.CRITICAL
                message = f'HTTP request "{operation}" in loop causes severe performance issues'
            elif operation in ['readFile', 'writeFile', 'open']:
                severity = Severity.HIGH
                message = f'File I/O operation "{operation}" in loop is expensive'
            elif operation in ['bcrypt', 'pbkdf2', 'scrypt']:
                severity = Severity.CRITICAL
                message = f'CPU-intensive crypto "{operation}" in loop blocks execution'
            else:
                severity = Severity.HIGH
                message = f'Expensive operation "{operation}" in loop'

            findings.append(StandardFinding(
                rule_name='perf-expensive-in-loop',
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='performance',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))

    return findings


def _find_inefficient_string_concat(cursor) -> List[StandardFinding]:
    """Find inefficient string concatenation in loops (O(n²) complexity)."""
    findings = []

    # Find loops
    cursor.execute("""
        SELECT DISTINCT file, start_line, end_line, function_name
        FROM cfg_blocks
        WHERE block_type LIKE '%loop%'
    """)

    loops = cursor.fetchall()

    for file, loop_start, loop_end, function in loops:
        # Find string concatenation assignments within loop
        cursor.execute("""
            SELECT line, target_var, source_expr
            FROM assignments
            WHERE file = ?
              AND line >= ?
              AND line <= ?
              AND (
                  source_expr LIKE '%+=%'
                  OR source_expr LIKE '%+ %'
                  OR source_expr LIKE '% + %'
                  OR source_expr LIKE '%concat%'
              )
              AND (
                  target_var LIKE '%str%'
                  OR target_var LIKE '%text%'
                  OR target_var LIKE '%result%'
                  OR target_var LIKE '%output%'
                  OR target_var LIKE '%html%'
                  OR target_var LIKE '%message%'
                  OR source_expr LIKE '"%'
                  OR source_expr LIKE "'%"
                  OR source_expr LIKE '`%'
              )
            ORDER BY line
        """, (file, loop_start, loop_end))

        for line, var_name, expr in cursor.fetchall():
            # Check if it looks like string concatenation
            if any(op in expr for op in ['+', '+=', 'concat']):
                findings.append(StandardFinding(
                    rule_name='perf-string-concat-loop',
                    message=f'String concatenation "{var_name} += ..." in loop has O(n²) complexity',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='performance',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1050'
                ))

    return findings


def _find_synchronous_io_patterns(cursor, has_api_endpoints: bool) -> List[StandardFinding]:
    """Find synchronous I/O operations that block the event loop."""
    findings = []

    sync_ops_list = list(SYNC_BLOCKERS)
    placeholders = ','.join('?' * len(sync_ops_list))

    cursor.execute(f"""
        SELECT file, line, callee_function, caller_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
        ORDER BY file, line
    """, sync_ops_list)

    for file, line, operation, caller, args in cursor.fetchall():
        # Check if in async context
        is_async_context = False
        confidence = Confidence.MEDIUM

        # Check caller function name for async indicators
        if caller:
            caller_lower = caller.lower()
            if any(indicator in caller_lower for indicator in ['async', 'await', 'promise']):
                is_async_context = True
                confidence = Confidence.HIGH

        # Check if in API route context
        if has_api_endpoints:
            cursor.execute("""
                SELECT COUNT(*) FROM api_endpoints
                WHERE file = ? AND ? BETWEEN line - 50 AND line + 50
            """, (file, line))

            if cursor.fetchone()[0] > 0:
                is_async_context = True
                confidence = Confidence.HIGH

        severity = Severity.CRITICAL if is_async_context else Severity.HIGH

        findings.append(StandardFinding(
            rule_name='perf-sync-io',
            message=f'Synchronous operation "{operation}" blocks event loop',
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            confidence=confidence,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_unbounded_operations(cursor) -> List[StandardFinding]:
    """Find operations without proper limits that could cause memory issues."""
    findings = []

    # Check for database queries without limits
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ('find', 'findMany', 'findAll', 'select', 'query', 'all')
          AND (argument_expr IS NULL OR argument_expr = '' OR (
              argument_expr NOT LIKE '%limit%'
              AND argument_expr NOT LIKE '%take%'
              AND argument_expr NOT LIKE '%first%'
              AND argument_expr NOT LIKE '%pageSize%'
              AND argument_expr NOT LIKE '%max%'
          ))
        ORDER BY file, line
    """)

    for file, line, operation, args in cursor.fetchall():
        # Skip if it's a count or single-result operation
        if operation in ['findOne', 'findUnique', 'first', 'get']:
            continue

        findings.append(StandardFinding(
            rule_name='perf-unbounded-query',
            message=f'Query "{operation}" without limit could return excessive data',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-770'  # Allocation of Resources Without Limits
        ))

    # Check for readFile on potentially large files
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ('readFile', 'readFileSync', 'read')
          AND (
              argument_expr LIKE '%.log%'
              OR argument_expr LIKE '%.csv%'
              OR argument_expr LIKE '%.json%'
              OR argument_expr LIKE '%.xml%'
              OR argument_expr LIKE '%.sql%'
              OR argument_expr LIKE '%.txt%'
          )
    """)

    for file, line, operation, file_arg in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-large-file-read',
            message=f'Reading potentially large file entirely into memory',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='performance',
            confidence=Confidence.LOW,
            cwe_id='CWE-770'
        ))

    # Check for memory-intensive array operations
    memory_ops_list = list(MEMORY_OPS)
    placeholders = ','.join('?' * len(memory_ops_list))

    cursor.execute(f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
          AND line IN (
              SELECT line FROM function_call_args
              WHERE callee_function IN ('find', 'findMany', 'findAll', 'query')
                AND file = function_call_args.file
                AND ABS(line - function_call_args.line) <= 5
          )
        ORDER BY file, line
    """, memory_ops_list)

    for file, line, operation in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-memory-intensive',
            message=f'Memory-intensive operation "{operation}" on potentially large dataset',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='performance',
            confidence=Confidence.LOW,
            cwe_id='CWE-770'
        ))

    return findings


def _find_deep_property_chains(cursor) -> List[StandardFinding]:
    """Find deep property access chains that impact performance."""
    findings = []

    # Find property accesses with multiple dots
    cursor.execute("""
        SELECT path, name, line
        FROM symbols
        WHERE type = 'property'
          AND LENGTH(name) - LENGTH(REPLACE(name, '.', '')) >= 3
        ORDER BY path, line
    """)

    for file, prop_chain, line in cursor.fetchall():
        # Count dots to determine depth
        depth = prop_chain.count('.')

        if depth >= 4:
            severity = Severity.HIGH
            message = f'Very deep property chain "{prop_chain}" ({depth} levels)'
        elif depth == 3:
            severity = Severity.MEDIUM
            message = f'Deep property chain "{prop_chain}" impacts performance'
        else:
            continue

        findings.append(StandardFinding(
            rule_name='perf-deep-property-chain',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1050'
        ))

    # Check for repeated deep property access in same function
    cursor.execute("""
        SELECT path, name, COUNT(*) as count, MIN(line) as first_line
        FROM symbols
        WHERE type = 'property'
          AND LENGTH(name) - LENGTH(REPLACE(name, '.', '')) >= 2
        GROUP BY path, name
        HAVING count > 3
        ORDER BY count DESC
    """)

    for file, prop_chain, count, line in cursor.fetchall():
        if count > 5:
            findings.append(StandardFinding(
                rule_name='perf-repeated-property-access',
                message=f'Property "{prop_chain}" accessed {count} times - cache it',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='performance',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))

    return findings


def _find_unoptimized_taint_flows(cursor) -> List[StandardFinding]:
    """Find unoptimized taint flows (e.g., req.body → res.send without validation)."""
    findings = []

    # Find direct req → res flows
    cursor.execute("""
        SELECT DISTINCT s1.path, s1.line, s1.name as source, s2.name as sink
        FROM symbols s1
        JOIN symbols s2 ON s1.path = s2.path
        WHERE s1.name LIKE 'req.%'
          AND s2.name LIKE 'res.%'
          AND ABS(s1.line - s2.line) <= 5
          AND s1.line < s2.line
        ORDER BY s1.path, s1.line
    """)

    for file, line, source, sink in cursor.fetchall():
        # Check for particularly dangerous combinations
        if 'req.body' in source and 'res.send' in sink:
            severity = Severity.CRITICAL
            message = 'Direct flow from req.body to res.send - potential XSS'
            cwe = 'CWE-79'  # Cross-site Scripting
        elif 'req.query' in source and 'res.render' in sink:
            severity = Severity.HIGH
            message = 'Query parameter passed to render - potential template injection'
            cwe = 'CWE-94'  # Code Injection
        elif 'req.params' in source and any(db in sink for db in ['query', 'find', 'execute']):
            severity = Severity.CRITICAL
            message = 'Request parameter in database query - potential SQL injection'
            cwe = 'CWE-89'  # SQL Injection
        else:
            continue

        findings.append(StandardFinding(
            rule_name='perf-unoptimized-taint',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='performance-security',
            confidence=Confidence.MEDIUM,
            cwe_id=cwe
        ))

    return findings


def _find_repeated_expensive_calls(cursor) -> List[StandardFinding]:
    """Find expensive functions called multiple times in same context."""
    findings = []

    # Find repeated expensive calls in same function
    expensive_ops_list = list(EXPENSIVE_OPS)
    placeholders = ','.join('?' * len(expensive_ops_list))

    cursor.execute(f"""
        SELECT file, caller_function, callee_function, COUNT(*) as count, MIN(line) as first_line
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
          AND caller_function IS NOT NULL
        GROUP BY file, caller_function, callee_function
        HAVING count > 2
        ORDER BY count DESC
    """, expensive_ops_list)

    for file, caller, callee, count, line in cursor.fetchall():
        if count > 5:
            severity = Severity.HIGH
            message = f'Expensive operation "{callee}" called {count} times in {caller}'
        elif count > 3:
            severity = Severity.MEDIUM
            message = f'Operation "{callee}" repeated {count} times in {caller}'
        else:
            continue

        findings.append(StandardFinding(
            rule_name='perf-repeated-expensive-call',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            confidence=Confidence.HIGH,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_large_object_operations(cursor) -> List[StandardFinding]:
    """Find operations on large objects that could cause performance issues."""
    findings = []

    # Find JSON operations on large data
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE (source_expr LIKE '%JSON.parse%' OR source_expr LIKE '%JSON.stringify%')
          AND LENGTH(source_expr) > 500
        ORDER BY file, line
    """)

    for file, line, var_name, expr in cursor.fetchall():
        expr_len = len(expr)

        if expr_len > 2000:
            severity = Severity.HIGH
            message = 'Very large JSON operation detected'
        elif expr_len > 1000:
            severity = Severity.MEDIUM
            message = 'Large JSON operation may impact performance'
        else:
            continue

        findings.append(StandardFinding(
            rule_name='perf-large-json-operation',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            confidence=Confidence.LOW,
            cwe_id='CWE-770'
        ))

    # Find very long assignment expressions (potential large object copies)
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE LENGTH(source_expr) > 1000
          AND (source_expr LIKE '%{%}%' OR source_expr LIKE '%[%]%')
        ORDER BY LENGTH(source_expr) DESC
        LIMIT 10
    """)

    for file, line, var_name, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-large-object-copy',
            message=f'Large object assignment to {var_name} may impact memory',
            file_path=file,
            line=line,
            severity=Severity.LOW,
            category='performance',
            confidence=Confidence.LOW,
            cwe_id='CWE-770'
        ))

    return findings


def register_taint_patterns(taint_registry):
    """Register performance-related taint patterns.

    This function is called by the orchestrator to register
    performance-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """
    # Register database operations as sinks
    for pattern in DB_OPERATIONS:
        taint_registry.register_sink(pattern, 'database', 'all')

    # Register expensive operations as sinks
    for pattern in EXPENSIVE_OPS:
        taint_registry.register_sink(pattern, 'expensive_op', 'all')

    # Register common sources that lead to performance issues
    PERF_SOURCES = frozenset([
        'req.body', 'req.query', 'req.params',
        'process.argv', 'process.env',
        'fs.readFile', 'fs.readdir'
    ])

    for pattern in PERF_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'all')