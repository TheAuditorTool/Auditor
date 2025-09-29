"""General Logic Analyzer - Database-First Approach.

Detects common programming mistakes and best practice violations using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces general_logic_analyzer.py with a faster, cleaner implementation.
Follows golden standard patterns from compose_analyze.py.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Use Frozensets)
# ============================================================================

# Money-related variable/parameter patterns
MONEY_TERMS = frozenset([
    'price', 'cost', 'amount', 'total', 'balance',
    'payment', 'fee', 'money', 'charge', 'refund',
    'salary', 'wage', 'tax', 'discount', 'revenue'
])

# Float conversion functions
FLOAT_FUNCTIONS = frozenset([
    'parseFloat', 'float', 'Number.parseFloat',
    'toFixed', 'toPrecision', 'parseDouble'
])

# Datetime functions that need timezone awareness
DATETIME_FUNCTIONS = frozenset([
    'datetime.now', 'datetime.today', 'datetime.utcnow',
    'Date.now', 'new Date', 'Date', 'Date.parse',
    'moment', 'new moment', 'dayjs'
])

# Regex functions for email validation anti-pattern
REGEX_FUNCTIONS = frozenset([
    're.match', 're.search', 're.compile',
    'RegExp', 'test', 'match', 'exec'
])

# Division-risky denominator patterns
DIVISION_RISK_TERMS = frozenset([
    'count', 'length', 'size', 'total', 'sum', 'num',
    'items', 'records', 'rows', 'elements'
])

# File operation functions
FILE_OPERATIONS = frozenset([
    'open', 'fopen', 'fs.open',
    'fs.createReadStream', 'fs.createWriteStream',
    'createReadStream', 'createWriteStream'
])

# File cleanup functions
FILE_CLEANUP = frozenset([
    'close', 'fclose', 'end', 'destroy', 'finish'
])

# Connection functions
CONNECTION_FUNCTIONS = frozenset([
    'connect', 'createConnection', 'getConnection',
    'createPool', 'getPool', 'createClient'
])

# Connection cleanup functions
CONNECTION_CLEANUP = frozenset([
    'close', 'disconnect', 'end', 'release', 'destroy'
])

# Transaction functions
TRANSACTION_FUNCTIONS = frozenset([
    'begin', 'beginTransaction', 'begin_transaction',
    'startTransaction', 'start_transaction', 'START TRANSACTION'
])

# Transaction end functions
TRANSACTION_END = frozenset([
    'commit', 'rollback', 'end', 'abort', 'COMMIT', 'ROLLBACK'
])

# Socket functions
SOCKET_FUNCTIONS = frozenset([
    'socket', 'Socket', 'createSocket', 'createServer',
    'net.createConnection', 'net.createServer'
])

# Stream functions
STREAM_FUNCTIONS = frozenset([
    'createReadStream', 'createWriteStream', 'stream',
    'fs.createReadStream', 'fs.createWriteStream',
    'Readable', 'Writable', 'Transform'
])

# Stream cleanup handlers
STREAM_HANDLERS = frozenset([
    'end', 'destroy', 'close', 'finish', 'error',
    '.on', '.once', '.addListener'
])

# Async patterns
ASYNC_PATTERNS = frozenset([
    '.then', 'await', 'Promise', 'async', '.catch'
])

# Lock/Mutex patterns
LOCK_FUNCTIONS = frozenset([
    'lock', 'Lock', 'acquire', 'mutex', 'Mutex',
    'semaphore', 'Semaphore', 'RLock'
])

# Lock release functions
LOCK_RELEASE = frozenset([
    'unlock', 'release', 'free', 'signal'
])


def find_logic_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect common logic and resource management issues using indexed data.

    Detects:
    Business Logic Issues:
    - Money/float arithmetic precision problems
    - Timezone-naive datetime usage
    - Email regex validation anti-pattern
    - Division by zero risks
    - Percentage calculation errors

    Resource Management Issues:
    - File handles not closed properly
    - Database connections without cleanup
    - Transactions without commit/rollback
    - Sockets without proper cleanup
    - Streams without cleanup

    Returns:
        List of logic and resource issues found
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
                'assignments', 'function_call_args', 'symbols',
                'cfg_blocks', 'files'
            )
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Minimum required tables for analysis
        if 'assignments' not in existing_tables and 'function_call_args' not in existing_tables:
            return findings  # Can't analyze without basic data

        # Track which tables are available for graceful degradation
        has_assignments = 'assignments' in existing_tables
        has_function_calls = 'function_call_args' in existing_tables
        has_cfg_blocks = 'cfg_blocks' in existing_tables
        has_symbols = 'symbols' in existing_tables
        # ========================================================
        # CHECK 1: Money/Float Arithmetic (Precision Loss)
        # ========================================================
        if has_assignments:
            # Build SQL conditions for money terms
            money_conditions = ' OR '.join([f"a.target_var LIKE '%{term}%'" for term in MONEY_TERMS])

            cursor.execute(f"""
                SELECT DISTINCT a.file, a.line, a.target_var, a.source_expr
                FROM assignments a
                WHERE ({money_conditions})
                  AND (a.source_expr LIKE '%/%'
                       OR a.source_expr LIKE '%*%'
                       OR a.source_expr LIKE '%parseFloat%'
                       OR a.source_expr LIKE '%float(%'
                       OR a.source_expr LIKE '%.toFixed%')
                ORDER BY a.file, a.line
            """)

            for file, line, var_name, expr in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='money-float-arithmetic',
                    message=f'Using float/double for money calculations in {var_name} - precision loss risk',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='business-logic',
                    confidence=Confidence.HIGH,
                    snippet=expr[:100] if len(expr) > 100 else expr,
                    cwe_id='CWE-682'
                ))
        
        # Also check function calls with money parameters
        if has_function_calls:
            float_funcs_list = list(FLOAT_FUNCTIONS)
            placeholders = ','.join('?' * len(float_funcs_list))
            money_arg_conditions = ' OR '.join([f"f.argument_expr LIKE '%{term}%'" for term in MONEY_TERMS])

            cursor.execute(f"""
                SELECT f.file, f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE f.callee_function IN ({placeholders})
                  AND ({money_arg_conditions})
                ORDER BY f.file, f.line
            """, float_funcs_list)

            for file, line, func, arg in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='money-float-conversion',
                    message=f'Converting money value to float using {func} - precision loss risk',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='business-logic',
                    confidence=Confidence.HIGH,
                    snippet=f'{func}({arg[:50]}...)' if len(arg) > 50 else f'{func}({arg})',
                    cwe_id='CWE-682'
                ))
        
        # ========================================================
        # CHECK 2: Timezone-Naive Datetime Usage
        # ========================================================
        if has_function_calls:
            datetime_funcs_list = list(DATETIME_FUNCTIONS)
            placeholders = ','.join('?' * len(datetime_funcs_list))

            cursor.execute(f"""
                SELECT f.file, f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE f.callee_function IN ({placeholders})
                  AND f.argument_expr NOT LIKE '%tz%'
                  AND f.argument_expr NOT LIKE '%timezone%'
                  AND f.argument_expr NOT LIKE '%UTC%'
                ORDER BY f.file, f.line
            """, datetime_funcs_list)

            for file, line, datetime_func, args in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='timezone-naive-datetime',
                    message=f'Using {datetime_func} without timezone awareness',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='datetime',
                    confidence=Confidence.MEDIUM,
                    snippet=f'{datetime_func}({args[:30]}...)' if len(args) > 30 else f'{datetime_func}({args})',
                    cwe_id='CWE-20'
                ))
        
        # ========================================================
        # CHECK 3: Email Regex Validation (Anti-pattern)
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function IN ('re.match', 're.search', 're.compile', 'RegExp', 'test', 'match')
                   AND f.argument_expr LIKE '%@%'
                   AND (f.argument_expr LIKE '%email%' 
                        OR f.argument_expr LIKE '%mail%'
                        OR f.argument_expr LIKE '%\\\\@%'))
            ORDER BY f.file, f.line
        """)
        
        for file, line, regex_func, pattern in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='email-regex-validation',
                message='Using regex for email validation - use proper email validation library',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='validation',
                confidence=Confidence.HIGH,
                snippet=pattern[:100] if len(pattern) > 100 else pattern,
                cwe_id='CWE-20'
            ))
        
        # ========================================================
        # CHECK 4: Division by Zero Risks
        # ========================================================
        # Look for division operations with risky denominators
        cursor.execute("""
            SELECT DISTINCT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%/%'
              AND (a.source_expr LIKE '%count%'
                   OR a.source_expr LIKE '%length%'
                   OR a.source_expr LIKE '%size%'
                   OR a.source_expr LIKE '%.length%'
                   OR a.source_expr LIKE '%.size%'
                   OR a.source_expr LIKE '%.count%')
            ORDER BY a.file, a.line
        """)
        
        for file, line, expr in cursor.fetchall():
            # Try to check if there's a zero check nearby
            cursor.execute("""
                SELECT COUNT(*) FROM symbols
                WHERE path = ?
                  AND line BETWEEN ? AND ?
                  AND (name LIKE '%!= 0%' OR name LIKE '%> 0%' OR name LIKE '%if %')
            """, (file, line - 5, line))
            
            has_check = cursor.fetchone()[0] > 0
            
            if not has_check:
                findings.append(StandardFinding(
                    rule_name='divide-by-zero-risk',
                    message='Division without zero check - potential divide by zero',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='error-handling',
                    confidence=Confidence.MEDIUM,
                    snippet=expr[:100] if len(expr) > 100 else expr,
                    cwe_id='CWE-369'
                ))
        
        # ========================================================
        # CHECK 5: File Handles Not Closed (Resource Leak)
        # ========================================================
        if has_function_calls:
            file_ops_list = list(FILE_OPERATIONS)
            file_cleanup_list = list(FILE_CLEANUP)
            ops_placeholders = ','.join('?' * len(file_ops_list))
            cleanup_placeholders = ','.join('?' * len(file_cleanup_list))

            cursor.execute(f"""
                SELECT f.file, f.line, f.callee_function, f.caller_function
                FROM function_call_args f
                WHERE f.callee_function IN ({ops_placeholders})
                  AND NOT EXISTS (
                      SELECT 1 FROM function_call_args f2
                      WHERE f2.file = f.file
                        AND f2.caller_function = f.caller_function
                        AND f2.callee_function IN ({cleanup_placeholders})
                        AND f2.line > f.line
                  )
                ORDER BY f.file, f.line
            """, file_ops_list + file_cleanup_list)

            for file, line, open_func, in_function in cursor.fetchall():
                # Check if it's in a with statement (Python) or try-finally
                # FIXED: Check cfg_blocks for try/finally blocks, not symbols
                has_context_manager = False

                if has_cfg_blocks:
                    cursor.execute("""
                        SELECT COUNT(*) FROM cfg_blocks
                        WHERE file = ?
                          AND block_type IN ('try', 'finally', 'with')
                          AND ? BETWEEN start_line AND end_line
                    """, (file, line))
                    has_context_manager = cursor.fetchone()[0] > 0

                # Check for __enter__ in symbols as backup (context manager indicator)
                if not has_context_manager and has_symbols:
                    cursor.execute("""
                        SELECT COUNT(*) FROM symbols
                        WHERE path = ?
                          AND line BETWEEN ? AND ?
                          AND name = '__enter__'
                    """, (file, line - 5, line + 5))
                    has_context_manager = cursor.fetchone()[0] > 0

                if not has_context_manager:
                    findings.append(StandardFinding(
                        rule_name='file-no-close',
                        message=f'File opened with {open_func} but not closed - resource leak',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='resource-management',
                        confidence=Confidence.MEDIUM if has_cfg_blocks else Confidence.LOW,
                        snippet=f'{open_func}(...) in {in_function}',
                        cwe_id='CWE-404'
                    ))
        
        # ========================================================
        # CHECK 6: Database Connections Without Cleanup
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%connect%'
                   OR f.callee_function LIKE '%createConnection%'
                   OR f.callee_function LIKE '%getConnection%')
              AND f.callee_function NOT LIKE '%disconnect%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND (f2.callee_function LIKE '%close%'
                         OR f2.callee_function LIKE '%disconnect%'
                         OR f2.callee_function LIKE '%end%'
                         OR f2.callee_function LIKE '%release%')
                    AND f2.line > f.line
                    AND f2.line < f.line + 50
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, connect_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='connection-no-close',
                message=f'Database connection from {connect_func} without explicit cleanup',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='resource-management',
                confidence=Confidence.MEDIUM,
                snippet=connect_func,
                cwe_id='CWE-404'
            ))
        
        # ========================================================
        # CHECK 7: Transactions Without Commit/Rollback
        # ========================================================
        if has_function_calls:
            trans_funcs_list = list(TRANSACTION_FUNCTIONS)
            trans_end_list = list(TRANSACTION_END)
            trans_placeholders = ','.join('?' * len(trans_funcs_list))
            end_placeholders = ','.join('?' * len(trans_end_list))

            cursor.execute(f"""
                SELECT f.file, f.line, f.callee_function
                FROM function_call_args f
                WHERE f.callee_function IN ({trans_placeholders})
                  AND NOT EXISTS (
                      SELECT 1 FROM function_call_args f2
                      WHERE f2.file = f.file
                        AND f2.callee_function IN ({end_placeholders})
                        AND f2.line > f.line
                        AND f2.line < f.line + 100
                  )
                ORDER BY f.file, f.line
            """, trans_funcs_list + trans_end_list)

            for file, line, trans_func in cursor.fetchall():
                findings.append(StandardFinding(
                    rule_name='transaction-no-end',
                    message=f'Transaction started with {trans_func} but no commit/rollback found',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='database',
                    confidence=Confidence.MEDIUM,
                    snippet=trans_func,
                    cwe_id='CWE-404'
                ))
        
        # ========================================================
        # CHECK 8: Sockets Without Cleanup
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%socket%'
                   OR f.callee_function LIKE '%Socket%'
                   OR f.callee_function = 'createSocket')
              AND f.callee_function NOT LIKE '%close%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND (f2.callee_function LIKE '%close%'
                         OR f2.callee_function LIKE '%destroy%'
                         OR f2.callee_function LIKE '%end%')
                    AND f2.line > f.line
                    AND f2.line < f.line + 50
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, socket_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='socket-no-close',
                message=f'Socket created with {socket_func} but not properly closed',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='resource-management',
                confidence=Confidence.MEDIUM,
                snippet=socket_func,
                cwe_id='CWE-404'
            ))
        
        # ========================================================
        # CHECK 9: Percentage Calculation Errors
        # ========================================================
        # Look for patterns like value / 100 * something (missing parentheses)
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE (a.source_expr LIKE '%/ 100 *%'
                   OR a.source_expr LIKE '%/100*%'
                   OR a.source_expr LIKE '%/ 100.0 *%')
              AND a.source_expr NOT LIKE '%(%/ 100%)%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='percentage-calc-error',
                message='Potential percentage calculation error - missing parentheses around division',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='calculation',
                confidence=Confidence.HIGH,
                snippet=expr[:100] if len(expr) > 100 else expr,
                cwe_id='CWE-682'
            ))
        
        # ========================================================
        # CHECK 10: Stream Operations Without Cleanup
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function IN (
                'createReadStream', 'createWriteStream', 'stream',
                'fs.createReadStream', 'fs.createWriteStream'
            )
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND (f2.callee_function IN ('end', 'destroy', 'close', 'finish')
                         OR f2.callee_function LIKE '%.on%error%'
                         OR f2.callee_function LIKE '%.on%close%')
                    AND f2.line > f.line
                    AND f2.line < f.line + 30
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, stream_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='stream-no-cleanup',
                message=f'Stream created with {stream_func} without proper cleanup handlers',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='resource-management',
                confidence=Confidence.MEDIUM,
                snippet=stream_func,
                cwe_id='CWE-404'
            ))
        
        # ========================================================
        # CHECK 11: Async Operations Without Error Handling
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%.then%'
                   OR f.callee_function = 'await'
                   OR f.callee_function LIKE '%Promise%')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND f2.line BETWEEN f.line AND f.line + 5
                    AND (f2.callee_function LIKE '%.catch%'
                         OR f2.callee_function = 'try')
              )
            ORDER BY f.file, f.line
            LIMIT 10
        """)
        
        for file, line, async_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='async-no-error-handling',
                message='Async operation without error handling',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='error-handling',
                confidence=Confidence.LOW,
                snippet=async_func,
                cwe_id='CWE-248'
            ))
        
        # ========================================================
        # CHECK 12: Lock/Mutex Without Release
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%lock%'
                   OR f.callee_function LIKE '%Lock%'
                   OR f.callee_function LIKE '%acquire%'
                   OR f.callee_function LIKE '%mutex%')
              AND f.callee_function NOT LIKE '%unlock%'
              AND f.callee_function NOT LIKE '%release%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND (f2.callee_function LIKE '%unlock%'
                         OR f2.callee_function LIKE '%release%')
                    AND f2.line > f.line
                    AND f2.line < f.line + 50
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, lock_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='lock-no-release',
                message=f'Lock acquired with {lock_func} but not released',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='concurrency',
                confidence=Confidence.MEDIUM,
                snippet=lock_func,
                cwe_id='CWE-667'
            ))
    
    finally:
        conn.close()
    
    return findings


def register_taint_patterns(taint_registry):
    """Register logic-related patterns with the taint analysis registry.
    
    Args:
        taint_registry: TaintRegistry instance
    """
    # Register datetime sources (can be dangerous if used for security decisions)
    DATETIME_SOURCES = [
        'datetime.now', 'datetime.today', 'datetime.utcnow',
        'Date.now', 'new Date', 'Date.parse',
        'time.time', 'time.localtime', 'time.gmtime'
    ]
    
    for pattern in DATETIME_SOURCES:
        taint_registry.register_source(pattern, 'datetime', 'any')
    
    # Register resource operation sinks (need proper cleanup)
    RESOURCE_SINKS = [
        'open', 'createReadStream', 'createWriteStream',
        'socket', 'createSocket', 'connect', 'createConnection',
        'begin_transaction', 'start_transaction', 'beginTransaction',
        'acquire', 'lock', 'getLock'
    ]
    
    for pattern in RESOURCE_SINKS:
        taint_registry.register_sink(pattern, 'resource', 'any')
    
    # Register money/financial operation sinks (precision-sensitive)
    MONEY_SINKS = [
        'parseFloat', 'float', 'toFixed', 'toPrecision',
        'price', 'cost', 'amount', 'total', 'balance',
        'payment', 'fee', 'money', 'charge', 'refund'
    ]
    
    for pattern in MONEY_SINKS:
        taint_registry.register_sink(pattern, 'financial', 'any')
    
    # Register division operations as sinks (divide by zero risk)
    DIVISION_SINKS = [
        'divide', 'div', 'quotient', 'average', 'mean'
    ]
    
    for pattern in DIVISION_SINKS:
        taint_registry.register_sink(pattern, 'division', 'any')