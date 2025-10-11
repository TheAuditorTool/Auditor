"""General Logic Analyzer - Database-First Approach.

Detects common programming mistakes and best practice violations using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Tables Used (guaranteed by schema contract):
- assignments: Variable assignments for money/float/division analysis
- function_call_args: Function calls for datetime, file, connection, transaction checks
- symbols: Symbol lookups for zero checks and context managers
- cfg_blocks: Control flow blocks for try/finally/with detection
- files: File metadata

Detects 12 types of issues:
- Business Logic: Money/float arithmetic, timezone-naive datetime, email regex, division by zero, percentage calc errors
- Resource Management: File handles, connections, transactions, sockets, streams, async operations, locks

Schema Contract Compliance: v1.1+ (Fail-Fast, Uses build_query())
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - SMART FILTERING
# ============================================================================

METADATA = RuleMetadata(
    name="general_logic_issues",
    category="logic",

    # Target ALL code files (logic issues exist everywhere)
    target_extensions=['.py', '.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs'],

    # Exclude patterns - skip migrations, tests, config, TheAuditor folders
    exclude_patterns=[
        'migrations/',
        '__tests__/',
        'test/',
        'tests/',
        'node_modules/',
        '.venv/',
        'venv/',
        'dist/',
        'build/',
        '.pf/',              # TheAuditor output directory
        '.auditor_venv/'     # TheAuditor sandboxed tools
    ],

    # Execution scope: database-wide analysis (runs once, not per-file)
    execution_scope='database',

    # This is a DATABASE-ONLY rule (no JSX)
    requires_jsx_pass=False
)


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
        # ========================================================
        # CHECK 1: Money/Float Arithmetic (Precision Loss)
        # ========================================================
        # Build parameterized conditions for money terms
        money_terms_list = list(MONEY_TERMS)
        money_placeholders = ','.join(['?' for _ in MONEY_TERMS])

        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           where=f"""(target_var IN ({money_placeholders}))
              AND (source_expr LIKE '%/%'
                   OR source_expr LIKE '%*%'
                   OR source_expr LIKE '%parseFloat%'
                   OR source_expr LIKE '%float(%'
                   OR source_expr LIKE '%.toFixed%')""",
                           order_by="file, line")
        cursor.execute(query, money_terms_list)

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
        float_funcs_list = list(FLOAT_FUNCTIONS)
        float_placeholders = ','.join('?' * len(float_funcs_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"""callee_function IN ({float_placeholders})
              AND ({money_arg_conditions})""",
                           order_by="file, line")
        cursor.execute(query, float_funcs_list)

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
        datetime_funcs_list = list(DATETIME_FUNCTIONS)
        datetime_placeholders = ','.join('?' * len(datetime_funcs_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"""callee_function IN ({datetime_placeholders})
              AND argument_expr NOT LIKE '%tz%'
              AND argument_expr NOT LIKE '%timezone%'
              AND argument_expr NOT LIKE '%UTC%'""",
                           order_by="file, line")
        cursor.execute(query, datetime_funcs_list)

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
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'])
        cursor.execute(query + """
            WHERE (callee_function IN ('re.match', 're.search', 're.compile', 'RegExp', 'test', 'match')
                   AND argument_expr LIKE '%@%'
                   AND (argument_expr LIKE '%email%'
                        OR argument_expr LIKE '%mail%'
                        OR argument_expr LIKE '%\\\\@%'))
            ORDER BY file, line
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
        query = build_query('assignments', ['file', 'line', 'source_expr'],
                           where="""source_expr LIKE '%/%'
              AND (source_expr LIKE '%count%'
                   OR source_expr LIKE '%length%'
                   OR source_expr LIKE '%size%'
                   OR source_expr LIKE '%.length%'
                   OR source_expr LIKE '%.size%'
                   OR source_expr LIKE '%.count%')""",
                           order_by="file, line")
        cursor.execute(query)
        # Store results before nested query loop (best practice, not a workaround)
        division_operations = cursor.fetchall()

        for file, line, expr in division_operations:
            # Try to check if there's a zero check nearby in assignment expressions
            assignments_query = build_query('assignments', ['source_expr'],
                                           where="""file = ?
                  AND line BETWEEN ? AND ?
                  AND (source_expr LIKE '%!= 0%'
                       OR source_expr LIKE '%> 0%'
                       OR source_expr LIKE '%if%!= 0%'
                       OR source_expr LIKE '%if%> 0%')""",
                                           limit=1)
            cursor.execute(assignments_query, (file, line - 5, line))

            has_check = cursor.fetchone() is not None

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
        # NOTE: Resource cleanup checks (5-12) use proximity heuristics.
        # They search for cleanup calls within N lines of resource acquisition.
        #
        # Known limitations (potential false positives):
        # - Class-based resource management (cleanup in __del__ or destructor)
        # - Callback-based cleanup (async patterns, event handlers)
        # - RAII patterns where cleanup is in different scope
        #
        # Mitigation: Checks for context managers (with/try-finally) reduce
        # false positives for Python. JavaScript patterns may still trigger.
        # ========================================================
        file_ops_list = list(FILE_OPERATIONS)
        file_cleanup_list = list(FILE_CLEANUP)
        ops_placeholders = ','.join('?' * len(file_ops_list))
        cleanup_placeholders = ','.join('?' * len(file_cleanup_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'caller_function'],
                           where=f"""callee_function IN ({ops_placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND fca2.caller_function = function_call_args.caller_function
                    AND fca2.callee_function IN ({cleanup_placeholders})
                    AND fca2.line > function_call_args.line
              )""",
                           order_by="file, line")
        cursor.execute(query, file_ops_list + file_cleanup_list)
        # Store results before nested query loop (best practice)
        file_operations = cursor.fetchall()

        for file, line, open_func, in_function in file_operations:
            # Check if it's in a with statement (Python) or try-finally
            has_context_manager = False

            # Check cfg_blocks for try/finally/with blocks
            cfg_query = build_query('cfg_blocks', ['id'],
                                   where="""file = ?
                  AND block_type IN ('try', 'finally', 'with')
                  AND ? BETWEEN start_line AND end_line""",
                                   limit=1)
            cursor.execute(cfg_query, (file, line))
            has_context_manager = cursor.fetchone() is not None

            # Check for __enter__ in symbols as backup (context manager indicator)
            if not has_context_manager:
                symbols_query = build_query('symbols', ['name'],
                                           where="""path = ?
                      AND line BETWEEN ? AND ?
                      AND name = '__enter__'""",
                                           limit=1)
                cursor.execute(symbols_query, (file, line - 5, line + 5))
                has_context_manager = cursor.fetchone() is not None

            if not has_context_manager:
                findings.append(StandardFinding(
                    rule_name='file-no-close',
                    message=f'File opened with {open_func} but not closed - resource leak',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='resource-management',
                    confidence=Confidence.MEDIUM,
                    snippet=f'{open_func}(...) in {in_function}',
                    cwe_id='CWE-404'
                ))
        
        # ========================================================
        # CHECK 6: Database Connections Without Cleanup
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function'])
        cursor.execute(query + """
            WHERE (callee_function LIKE '%connect%'
                   OR callee_function LIKE '%createConnection%'
                   OR callee_function LIKE '%getConnection%')
              AND callee_function NOT LIKE '%disconnect%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND (fca2.callee_function LIKE '%close%'
                         OR fca2.callee_function LIKE '%disconnect%'
                         OR fca2.callee_function LIKE '%end%'
                         OR fca2.callee_function LIKE '%release%')
                    AND fca2.line > function_call_args.line
                    AND fca2.line < function_call_args.line + 50
              )
            ORDER BY file, line
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
        trans_funcs_list = list(TRANSACTION_FUNCTIONS)
        trans_end_list = list(TRANSACTION_END)
        trans_placeholders = ','.join('?' * len(trans_funcs_list))
        end_placeholders = ','.join('?' * len(trans_end_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           where=f"""callee_function IN ({trans_placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND fca2.callee_function IN ({end_placeholders})
                    AND fca2.line > function_call_args.line
                    AND fca2.line < function_call_args.line + 100
              )""",
                           order_by="file, line")
        cursor.execute(query, trans_funcs_list + trans_end_list)

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
        query = build_query('function_call_args', ['file', 'line', 'callee_function'])
        cursor.execute(query + """
            WHERE (callee_function LIKE '%socket%'
                   OR callee_function LIKE '%Socket%'
                   OR callee_function = 'createSocket')
              AND callee_function NOT LIKE '%close%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND (fca2.callee_function LIKE '%close%'
                         OR fca2.callee_function LIKE '%destroy%'
                         OR fca2.callee_function LIKE '%end%')
                    AND fca2.line > function_call_args.line
                    AND fca2.line < function_call_args.line + 50
              )
            ORDER BY file, line
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
        query = build_query('assignments', ['file', 'line', 'source_expr'],
                           where="""(source_expr LIKE '%/ 100 *%'
                   OR source_expr LIKE '%/100*%'
                   OR source_expr LIKE '%/ 100.0 *%')
              AND source_expr NOT LIKE '%(%/ 100%)%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('function_call_args', ['file', 'line', 'callee_function'])
        cursor.execute(query + """
            WHERE callee_function IN (
                'createReadStream', 'createWriteStream', 'stream',
                'fs.createReadStream', 'fs.createWriteStream'
            )
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND (fca2.callee_function IN ('end', 'destroy', 'close', 'finish')
                         OR fca2.callee_function LIKE '%.on%error%'
                         OR fca2.callee_function LIKE '%.on%close%')
                    AND fca2.line > function_call_args.line
                    AND fca2.line < function_call_args.line + 30
              )
            ORDER BY file, line
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
        query = build_query('function_call_args', ['file', 'line', 'callee_function'])
        cursor.execute(query + """
            WHERE (callee_function LIKE '%.then%'
                   OR callee_function = 'await'
                   OR callee_function LIKE '%Promise%')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND fca2.line BETWEEN function_call_args.line AND function_call_args.line + 5
                    AND (fca2.callee_function LIKE '%.catch%'
                         OR fca2.callee_function = 'try')
              )
            ORDER BY file, line
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
        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           where="""(callee_function LIKE '%lock%'
                   OR callee_function LIKE '%Lock%'
                   OR callee_function LIKE '%acquire%'
                   OR callee_function LIKE '%mutex%')
              AND callee_function NOT LIKE '%unlock%'
              AND callee_function NOT LIKE '%release%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND (fca2.callee_function LIKE '%unlock%'
                         OR fca2.callee_function LIKE '%release%')
                    AND fca2.line > function_call_args.line
                    AND fca2.line < function_call_args.line + 50
              )""",
                           order_by="file, line")
        cursor.execute(query)

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