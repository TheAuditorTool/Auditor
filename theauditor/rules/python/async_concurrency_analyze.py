"""Python Async and Concurrency Analyzer - Database-Driven Implementation.

Detects race conditions, async issues, and concurrency problems using indexed data.
NO AST TRAVERSAL. Just efficient SQL queries.

This rule follows the TRUE golden standard:
1. Query the database for pre-indexed data
2. Process results with simple logic  
3. Return findings

Detects:
- Race conditions (check-then-act/TOCTOU)
- Shared state modifications without locks
- Async functions not awaited
- Parallel writes without synchronization
- Threading/multiprocessing issues
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_async_concurrency_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect async and concurrency issues using indexed data.
    
    Main entry point that delegates to specific detectors.
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # Run each concurrency check
        findings.extend(_find_race_conditions(cursor))
        findings.extend(_find_shared_state_no_lock(cursor))
        findings.extend(_find_async_without_await(cursor))
        findings.extend(_find_parallel_writes(cursor))
        findings.extend(_find_threading_issues(cursor))
        findings.extend(_find_sleep_in_loops(cursor))
        findings.extend(_find_retry_without_backoff(cursor))
        findings.extend(_find_lock_issues(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# CHECK 1: Race Conditions (TOCTOU - Time-of-Check-Time-of-Use)
# ============================================================================

def _find_race_conditions(cursor) -> List[StandardFinding]:
    """Find check-then-act race conditions.
    
    Pattern: if not exists: create
    This creates a race where another thread could create between check and act.
    """
    findings = []
    
    # Look for file existence checks followed by file operations
    cursor.execute("""
        SELECT DISTINCT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.callee_function IN ('exists', 'isfile', 'isdir', 'path.exists', 'os.path.exists')
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.line > f1.line
                AND f2.line <= f1.line + 10
                AND f2.callee_function IN ('open', 'mkdir', 'makedirs', 'create', 'write')
          )
        ORDER BY f1.file, f1.line
    """)
    
    for file, line, check_func in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-toctou',
            message=f'Time-of-check-time-of-use race: {check_func} followed by file operation',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='concurrency',
            snippet=f'if not {check_func}(): create()',
            fix_suggestion='Use atomic operations or locks to prevent race conditions',
            cwe_id='CWE-367'  # TOCTOU
        ))
    
    # Look for membership checks followed by modifications
    cursor.execute("""
        SELECT DISTINCT a.file, a.line, a.target_var
        FROM assignments a
        WHERE a.source_expr LIKE '%if % not in %'
           OR a.source_expr LIKE '%if % in %'
           OR a.source_expr LIKE '%.get(%'
        ORDER BY a.file, a.line
    """)
    
    for file, line, var in cursor.fetchall():
        # Check if there's a subsequent modification
        cursor.execute("""
            SELECT 1 FROM assignments a2
            WHERE a2.file = ?
              AND a2.line > ?
              AND a2.line <= ? + 5
              AND (a2.target_var = ? OR a2.source_expr LIKE ?)
            LIMIT 1
        """, [file, line, line, var, f'%{var}%'])
        
        if cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='concurrency-check-then-act',
                message='Check-then-act pattern detected - potential race condition',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='concurrency',
                snippet='',
                fix_suggestion='Use locks or atomic operations for thread-safe access',
                cwe_id='CWE-367'
            ))
    
    return findings


# ============================================================================
# CHECK 2: Shared State Without Locks
# ============================================================================

def _find_shared_state_no_lock(cursor) -> List[StandardFinding]:
    """Find global/class variables modified without synchronization."""
    findings = []
    
    # Find global variable modifications
    cursor.execute("""
        SELECT DISTINCT a.file, a.line, a.target_var, a.in_function
        FROM assignments a
        WHERE (a.target_var LIKE 'self.%' 
               OR a.target_var LIKE 'cls.%'
               OR a.target_var IN (
                   SELECT s.name FROM symbols s 
                   WHERE s.path = a.file AND s.type = 'global'
               ))
          AND EXISTS (
              SELECT 1 FROM refs r
              WHERE r.src = a.file
                AND (r.value LIKE '%threading%' 
                     OR r.value LIKE '%multiprocessing%'
                     OR r.value LIKE '%asyncio%'
                     OR r.value LIKE '%concurrent%')
          )
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, function in cursor.fetchall():
        # Check if there's lock protection nearby
        cursor.execute("""
            SELECT 1 FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function IN ('acquire', 'lock', 'Lock', 'RLock', '__enter__', '__exit__')
              AND f.line >= ? - 5
              AND f.line <= ? + 5
              AND f.caller_function = ?
            LIMIT 1
        """, [file, line, line, function])
        
        if not cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='concurrency-shared-state-no-lock',
                message=f'Shared state "{var}" modified without synchronization',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='concurrency',
                snippet=f'{var} = ...',
                fix_suggestion='Use threading.Lock() or asyncio.Lock() to protect concurrent modifications',
                cwe_id='CWE-362'  # Race Condition
            ))
    
    # Find increment operations on shared state (+=, -=, etc.)
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%+=%' 
               OR a.source_expr LIKE '%-=%'
               OR a.source_expr LIKE '%*=%'
               OR a.source_expr LIKE '%/=%')
          AND (a.target_var LIKE 'self.%' 
               OR a.target_var LIKE 'cls.%'
               OR a.target_var IN (
                   SELECT s.name FROM symbols s 
                   WHERE s.path = a.file AND s.type = 'global'
               ))
    """)
    
    for file, line, var, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-unprotected-increment',
            message=f'Unprotected increment/modification of shared variable "{var}"',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='concurrency',
            snippet=expr[:50],
            fix_suggestion='Use locks to protect counter increments in concurrent code',
            cwe_id='CWE-362'
        ))
    
    return findings


# ============================================================================
# CHECK 3: Async Without Await
# ============================================================================

def _find_async_without_await(cursor) -> List[StandardFinding]:
    """Find async function calls that aren't awaited."""
    findings = []
    
    # Find async function calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.caller_function
        FROM function_call_args f
        WHERE (f.callee_function LIKE 'async_%' 
               OR f.callee_function IN (
                   SELECT s.name FROM symbols s 
                   WHERE s.path = f.file 
                     AND s.type = 'function'
                     AND s.name IN (
                         SELECT DISTINCT caller_function 
                         FROM function_call_args 
                         WHERE callee_function LIKE '%await%'
                     )
               ))
          AND f.argument_expr NOT LIKE '%await%'
          AND f.callee_function NOT IN ('asyncio.create_task', 'asyncio.ensure_future', 
                                        'create_task', 'ensure_future')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, caller in cursor.fetchall():
        # Check if it's in an async context
        if caller and 'async' in caller.lower():
            findings.append(StandardFinding(
                rule_name='concurrency-async-no-await',
                message=f'Async function "{func}" called without await',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='concurrency',
                snippet=f'{func}() # missing await',
                fix_suggestion='Add "await" or use asyncio.create_task() for fire-and-forget',
                cwe_id='CWE-667'  # Improper Locking
            ))
    
    return findings


# ============================================================================
# CHECK 4: Parallel Writes Without Sync
# ============================================================================

def _find_parallel_writes(cursor) -> List[StandardFinding]:
    """Find asyncio.gather or parallel operations with write operations."""
    findings = []
    
    # Find asyncio.gather calls
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('gather', 'asyncio.gather', 'wait', 'as_completed')
        ORDER BY f.file, f.line
    """)
    
    for file, line, args in cursor.fetchall():
        # Check if arguments contain write operations
        write_ops = ['save', 'update', 'insert', 'write', 'delete', 'remove', 'create']
        if any(op in args.lower() for op in write_ops):
            findings.append(StandardFinding(
                rule_name='concurrency-parallel-writes',
                message='Parallel write operations without synchronization detected',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='concurrency',
                snippet='asyncio.gather(*write_operations)',
                fix_suggestion='Use locks or transactions when performing parallel writes',
                cwe_id='CWE-362'
            ))
    
    # Find ThreadPoolExecutor/ProcessPoolExecutor with writes
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function IN ('ThreadPoolExecutor', 'ProcessPoolExecutor', 'map', 'submit')
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f.file
                AND f2.line >= f.line - 10
                AND f2.line <= f.line + 10
                AND f2.callee_function IN ('save', 'update', 'write', 'insert', 'delete')
          )
    """)
    
    for file, line, executor in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-executor-writes',
            message=f'Parallel executor "{executor}" performing write operations',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='concurrency',
            snippet='',
            fix_suggestion='Ensure thread-safe operations or use locks in worker functions',
            cwe_id='CWE-362'
        ))
    
    return findings


# ============================================================================
# CHECK 5: Threading Issues
# ============================================================================

def _find_threading_issues(cursor) -> List[StandardFinding]:
    """Find thread creation without join, workers not terminated."""
    findings = []
    
    # Find Thread.start() without corresponding join()
    cursor.execute("""
        SELECT DISTINCT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.callee_function IN ('start', 'Thread.start')
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.callee_function IN ('join', 'Thread.join')
                AND f2.line > f1.line
          )
    """)
    
    for file, line, _ in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-thread-no-join',
            message='Thread started but never joined',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='concurrency',
            snippet='thread.start() # no join()',
            fix_suggestion='Call thread.join() to wait for thread completion',
            cwe_id='CWE-404'  # Improper Resource Shutdown
        ))
    
    # Find worker/process creation without termination
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function IN ('Process', 'Worker', 'Pool', 'fork', 'spawn')
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f.file
                AND f2.callee_function IN ('terminate', 'close', 'shutdown', 'kill', 'join')
                AND f2.line > f.line
          )
    """)
    
    for file, line, worker_type in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-worker-no-terminate',
            message=f'{worker_type} created but may not be properly terminated',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='concurrency',
            snippet='',
            fix_suggestion='Ensure proper cleanup with terminate() or close()',
            cwe_id='CWE-404'
        ))
    
    return findings


# ============================================================================
# CHECK 6: Sleep in Loops
# ============================================================================

def _find_sleep_in_loops(cursor) -> List[StandardFinding]:
    """Find sleep/delay operations inside loops."""
    findings = []
    
    # Find sleep in loops using control flow blocks
    cursor.execute("""
        SELECT DISTINCT cb.file, f.line, f.callee_function
        FROM cfg_blocks cb
        JOIN function_call_args f ON f.file = cb.file
        WHERE cb.block_type IN ('loop', 'for_loop', 'while_loop')
          AND f.line >= cb.start_line
          AND f.line <= cb.end_line
          AND f.callee_function IN ('sleep', 'time.sleep', 'delay', 'wait')
        ORDER BY cb.file, f.line
    """)
    
    for file, line, sleep_func in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-sleep-in-loop',
            message=f'Sleep/delay "{sleep_func}" in loop causes performance issues',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='performance',
            snippet=f'{sleep_func}() in loop',
            fix_suggestion='Consider using async patterns or event-driven approaches',
            cwe_id='CWE-1050'
        ))
    
    return findings


# ============================================================================
# CHECK 7: Retry Without Backoff
# ============================================================================

def _find_retry_without_backoff(cursor) -> List[StandardFinding]:
    """Find retry loops without exponential backoff."""
    findings = []
    
    # Find retry patterns
    cursor.execute("""
        SELECT DISTINCT cb.file, cb.start_line, cb.end_line
        FROM cfg_blocks cb
        WHERE cb.block_type IN ('loop', 'while_loop')
          AND EXISTS (
              SELECT 1 FROM assignments a
              WHERE a.file = cb.file
                AND a.line >= cb.start_line
                AND a.line <= cb.end_line
                AND (a.target_var LIKE '%retry%' 
                     OR a.target_var LIKE '%attempt%'
                     OR a.target_var LIKE '%tries%')
          )
    """)
    
    for file, start_line, end_line in cursor.fetchall():
        # Check if there's exponential backoff
        cursor.execute("""
            SELECT 1 FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ?
              AND (a.source_expr LIKE '%**%' 
                   OR a.source_expr LIKE '%exponential%'
                   OR a.source_expr LIKE '%backoff%'
                   OR a.source_expr LIKE '%*= 2%')
            LIMIT 1
        """, [file, start_line, end_line])
        
        if not cursor.fetchone():
            # Check if there's at least a sleep
            cursor.execute("""
                SELECT 1 FROM function_call_args f
                WHERE f.file = ?
                  AND f.line >= ?
                  AND f.line <= ?
                  AND f.callee_function IN ('sleep', 'time.sleep', 'delay')
                LIMIT 1
            """, [file, start_line, end_line])
            
            if cursor.fetchone():
                findings.append(StandardFinding(
                    rule_name='concurrency-retry-no-backoff',
                    message='Retry logic without exponential backoff',
                    file_path=file,
                    line=start_line,
                    severity=Severity.MEDIUM,
                    category='performance',
                    snippet='',
                    fix_suggestion='Use exponential backoff to avoid overwhelming the system',
                    cwe_id='CWE-1050'
                ))
    
    return findings


# ============================================================================
# CHECK 8: Lock Issues
# ============================================================================

def _find_lock_issues(cursor) -> List[StandardFinding]:
    """Find lock-related issues: no timeout, nested locks, wrong order."""
    findings = []
    
    # Find lock acquisitions without timeout
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('acquire', 'Lock', 'RLock', 'Semaphore')
          AND f.argument_expr NOT LIKE '%timeout%'
          AND f.argument_expr NOT LIKE '%blocking%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, lock_func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-lock-no-timeout',
            message=f'Lock acquisition "{lock_func}" without timeout - infinite wait risk',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='concurrency',
            snippet=f'{lock_func}({args[:30]}...)',
            fix_suggestion='Use acquire(timeout=...) to prevent deadlocks',
            cwe_id='CWE-667'
        ))
    
    # Find potential nested locks (multiple lock calls in same function)
    cursor.execute("""
        SELECT f1.file, f1.caller_function, COUNT(*) as lock_count
        FROM function_call_args f1
        WHERE f1.callee_function IN ('acquire', 'Lock', 'RLock', '__enter__')
        GROUP BY f1.file, f1.caller_function
        HAVING COUNT(*) > 1
    """)
    
    for file, function, count in cursor.fetchall():
        if count > 1:
            findings.append(StandardFinding(
                rule_name='concurrency-nested-locks',
                message=f'Multiple lock acquisitions ({count}) in function "{function}" - potential deadlock',
                file_path=file,
                line=1,  # Would need to query for exact line
                severity=Severity.CRITICAL,
                category='concurrency',
                snippet='',
                fix_suggestion='Avoid acquiring multiple locks or ensure consistent ordering',
                cwe_id='CWE-833'  # Deadlock
            ))
    
    # Find singleton pattern without synchronization
    cursor.execute("""
        SELECT a.file, a.line, a.target_var
        FROM assignments a
        WHERE (a.target_var LIKE '%instance%' OR a.target_var LIKE '%singleton%')
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f
              WHERE f.file = a.file
                AND f.callee_function IN ('Lock', 'RLock', 'acquire')
                AND ABS(f.line - a.line) <= 5
          )
    """)
    
    for file, line, var in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='concurrency-singleton-race',
            message=f'Singleton pattern "{var}" without proper synchronization',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='concurrency',
            snippet='',
            fix_suggestion='Use locks or thread-safe initialization for singleton',
            cwe_id='CWE-362'
        ))
    
    return findings