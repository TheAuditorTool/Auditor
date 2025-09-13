"""JavaScript/TypeScript Async and Concurrency Analyzer - Database-First Approach.

Detects race conditions, async issues, and concurrency problems using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces async_concurrency_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


def find_async_concurrency_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect async and concurrency issues in JavaScript/TypeScript using indexed data.
    
    Detects:
    - Race conditions (check-then-act patterns)
    - Shared state modifications without protection
    - Async calls without await
    - Promise.all with write operations
    - setTimeout/sleep in loops
    - Retry logic without backoff
    - Promise chains without error handling
    - Workers/processes not terminated
    - Streams without cleanup
    - Global variable increments without protection
    
    Returns:
        List of async/concurrency issues found
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # Check if this is a JavaScript/TypeScript project
        cursor.execute("""
            SELECT COUNT(*) FROM files
            WHERE ext IN ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')
        """)
        
        if cursor.fetchone()[0] == 0:
            return findings  # Not a JS/TS project
        
        # ========================================================
        # CHECK 1: Async Calls Without Await
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.caller_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%async%'
                   OR f.callee_function LIKE '%.then%'
                   OR f.callee_function LIKE '%Promise%'
                   OR f.callee_function LIKE '%fetch%'
                   OR f.callee_function LIKE '%axios%'
                   OR f.callee_function LIKE '%.save%'
                   OR f.callee_function LIKE '%.create%'
                   OR f.callee_function LIKE '%.update%'
                   OR f.callee_function LIKE '%.delete%')
              AND f.file LIKE '%.%s'
              AND NOT EXISTS (
                  SELECT 1 FROM symbols s
                  WHERE s.path = f.file
                    AND s.line = f.line
                    AND (s.name = 'await' OR s.name LIKE '%.then%' OR s.name LIKE '%.catch%')
              )
            ORDER BY f.file, f.line
        """ % ('js%',))  # Covers .js, .jsx, .ts, .tsx
        
        for file, line, async_func, in_function in cursor.fetchall():
            # Skip if it's in a sync function or top-level
            if in_function and 'async' not in in_function:
                continue
                
            findings.append(StandardFinding(
                rule_name='async-without-await',
                message=f'Async operation {async_func} called without await',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='async',
                confidence=Confidence.MEDIUM,
                snippet=f'{async_func}(...) in {in_function or "module"}',
                fix_suggestion='Add await or handle with .then()/.catch()',
                cwe_id='CWE-367'
            ))
        
        # ========================================================
        # CHECK 2: Promise Chains Without Error Handling
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function LIKE '%.then%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND f2.line BETWEEN f.line AND f.line + 5
                    AND (f2.callee_function LIKE '%.catch%' 
                         OR f2.callee_function LIKE '%.finally%')
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, promise_method in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='promise-no-catch',
                message='Promise chain without error handling (.catch)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='error-handling',
                confidence=Confidence.HIGH,
                snippet=promise_method,
                fix_suggestion='Add .catch() to handle promise rejections',
                cwe_id='CWE-248'
            ))
        
        # ========================================================
        # CHECK 3: Promise.all With Write Operations (Parallel Writes)
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('Promise.all', 'Promise.allSettled')
              AND (f.argument_expr LIKE '%save%'
                   OR f.argument_expr LIKE '%update%'
                   OR f.argument_expr LIKE '%insert%'
                   OR f.argument_expr LIKE '%delete%'
                   OR f.argument_expr LIKE '%write%'
                   OR f.argument_expr LIKE '%create%'
                   OR f.argument_expr LIKE '%put%'
                   OR f.argument_expr LIKE '%post%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='parallel-writes-no-sync',
                message='Parallel write operations in Promise.all without synchronization',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='concurrency',
                confidence=Confidence.HIGH,
                snippet=args[:100] if len(args) > 100 else args,
                fix_suggestion='Use sequential operations or database transactions',
                cwe_id='CWE-362'
            ))
        
        # ========================================================
        # CHECK 4: Global/Shared State Modifications Without Protection
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE 'global.%'
                   OR a.target_var LIKE 'window.%'
                   OR a.target_var LIKE 'process.%'
                   OR a.target_var LIKE 'module.exports%'
                   OR a.target_var LIKE 'exports.%')
              AND a.file LIKE '%.%s'
            ORDER BY a.file, a.line
        """ % ('js%',))
        
        for file, line, var_name, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='shared-state-no-lock',
                message=f'Global/shared state "{var_name}" modified without synchronization',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='concurrency',
                confidence=Confidence.MEDIUM,
                snippet=f'{var_name} = {expr[:50]}...' if len(expr) > 50 else f'{var_name} = {expr}',
                fix_suggestion='Use locks, mutexes, or immutable updates',
                cwe_id='CWE-362'
            ))
        
        # ========================================================
        # CHECK 5: Unprotected Counter Increments
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.source_expr LIKE '%++%'
                   OR a.source_expr LIKE '%--%'
                   OR a.source_expr LIKE '%+= 1%'
                   OR a.source_expr LIKE '%-= 1%'
                   OR a.source_expr LIKE '%+ 1%'
                   OR a.source_expr LIKE '%- 1%')
              AND (a.target_var LIKE '%count%'
                   OR a.target_var LIKE '%counter%'
                   OR a.target_var LIKE '%total%'
                   OR a.target_var LIKE '%sum%'
                   OR a.target_var LIKE '%index%')
              AND a.file LIKE '%.%s'
            ORDER BY a.file, a.line
        """ % ('js%',))
        
        for file, line, var_name, expr in cursor.fetchall():
            # Check if it's in an async context
            cursor.execute("""
                SELECT COUNT(*) FROM symbols
                WHERE path = ?
                  AND line BETWEEN ? AND ?
                  AND (name = 'async' OR name = 'Promise' OR name = 'await')
            """, (file, line - 10, line + 10))
            
            in_async_context = cursor.fetchone()[0] > 0
            
            if in_async_context:
                findings.append(StandardFinding(
                    rule_name='unprotected-global-increment',
                    message=f'Counter "{var_name}" incremented without atomic operations',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='concurrency',
                    confidence=Confidence.MEDIUM,
                    snippet=expr,
                    fix_suggestion='Use Atomics API or synchronization for thread-safe increments',
                    cwe_id='CWE-362'
                ))
        
        # ========================================================
        # CHECK 6: setTimeout/setInterval in Loops
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.caller_function
            FROM function_call_args f
            WHERE f.callee_function IN ('setTimeout', 'setInterval', 'sleep', 'delay')
              AND f.caller_function LIKE '%loop%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, timer_func, in_function in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='sleep-in-loop',
                message=f'{timer_func} in loop can cause performance issues',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='performance',
                confidence=Confidence.LOW,
                snippet=f'{timer_func} in {in_function}',
                fix_suggestion='Use async/await with Promise-based delays',
                cwe_id='CWE-407'
            ))
        
        # Also check for common loop patterns
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function IN ('setTimeout', 'setInterval')
              AND EXISTS (
                  SELECT 1 FROM symbols s
                  WHERE s.path = f.file
                    AND s.line BETWEEN f.line - 5 AND f.line
                    AND s.name IN ('for', 'while', 'do')
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, timer_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='sleep-in-loop',
                message=f'{timer_func} inside loop - performance anti-pattern',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='performance',
                confidence=Confidence.HIGH,
                snippet=timer_func,
                fix_suggestion='Move timer outside loop or use async iteration',
                cwe_id='CWE-407'
            ))
        
        # ========================================================
        # CHECK 7: Workers/Processes Not Terminated
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%Worker%'
                   OR f.callee_function LIKE '%fork%'
                   OR f.callee_function LIKE '%spawn%'
                   OR f.callee_function LIKE '%exec%')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND f2.line > f.line
                    AND f2.line < f.line + 100
                    AND (f2.callee_function LIKE '%terminate%'
                         OR f2.callee_function LIKE '%kill%'
                         OR f2.callee_function LIKE '%disconnect%'
                         OR f2.callee_function LIKE '%close%')
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, worker_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='worker-no-terminate',
                message=f'Worker/process created with {worker_func} but not terminated',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='resource-management',
                confidence=Confidence.MEDIUM,
                snippet=worker_func,
                fix_suggestion='Ensure proper cleanup with terminate() or disconnect()',
                cwe_id='CWE-404'
            ))
        
        # ========================================================
        # CHECK 8: Streams Without Cleanup
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%createReadStream%'
                   OR f.callee_function LIKE '%createWriteStream%'
                   OR f.callee_function LIKE '%pipe%'
                   OR f.callee_function LIKE '%stream%')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND f2.line > f.line
                    AND f2.line < f.line + 50
                    AND (f2.callee_function LIKE '%.close%'
                         OR f2.callee_function LIKE '%.destroy%'
                         OR f2.callee_function LIKE '%.end%'
                         OR f2.callee_function LIKE '%.on%error%'
                         OR f2.callee_function LIKE '%.on%close%')
              )
            ORDER BY f.file, f.line
        """)
        
        for file, line, stream_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='stream-no-close',
                message=f'Stream created with {stream_func} without cleanup handlers',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='resource-management',
                confidence=Confidence.MEDIUM,
                snippet=stream_func,
                fix_suggestion='Add error and close handlers to streams',
                cwe_id='CWE-404'
            ))
        
        # ========================================================
        # CHECK 9: Check-Then-Act (TOCTOU) Race Conditions
        # ========================================================
        cursor.execute("""
            SELECT f1.file, f1.line, f1.callee_function
            FROM function_call_args f1
            WHERE (f1.callee_function LIKE '%exists%'
                   OR f1.callee_function LIKE '%.has%'
                   OR f1.callee_function LIKE '%.includes%'
                   OR f1.callee_function LIKE '%.contains%')
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.line BETWEEN f1.line + 1 AND f1.line + 10
                    AND (f2.callee_function LIKE '%write%'
                         OR f2.callee_function LIKE '%create%'
                         OR f2.callee_function LIKE '%mkdir%'
                         OR f2.callee_function LIKE '%save%'
                         OR f2.callee_function LIKE '%set%'
                         OR f2.callee_function LIKE '%add%')
              )
            ORDER BY f1.file, f1.line
        """)
        
        for file, line, check_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='check-then-act',
                message=f'Time-of-check-time-of-use (TOCTOU) race condition: {check_func} then write',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='race-condition',
                confidence=Confidence.HIGH,
                snippet=check_func,
                fix_suggestion='Use atomic operations or locks to prevent race conditions',
                cwe_id='CWE-367'
            ))
        
        # ========================================================
        # CHECK 10: Retry Logic Without Backoff
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE '%retry%'
                   OR a.target_var LIKE '%attempt%'
                   OR a.target_var LIKE '%tries%')
              AND NOT (a.source_expr LIKE '%Math.pow%'
                       OR a.source_expr LIKE '%**%'
                       OR a.source_expr LIKE '%exponential%'
                       OR a.source_expr LIKE '%backoff%'
                       OR a.source_expr LIKE '%*=%')
              AND a.file LIKE '%.%s'
            ORDER BY a.file, a.line
        """ % ('js%',))
        
        for file, line, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='retry-without-backoff',
                message='Retry logic without exponential backoff',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='performance',
                confidence=Confidence.LOW,
                snippet=expr[:100] if len(expr) > 100 else expr,
                fix_suggestion='Implement exponential backoff: delay *= 2',
                cwe_id='CWE-407'
            ))
        
        # ========================================================
        # CHECK 11: Singleton Pattern Without Proper Synchronization
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var
            FROM assignments a
            WHERE (a.target_var LIKE '%instance%'
                   OR a.target_var LIKE '%singleton%')
              AND a.source_expr LIKE '%new %'
              AND NOT EXISTS (
                  SELECT 1 FROM symbols s
                  WHERE s.path = a.file
                    AND s.line BETWEEN a.line - 5 AND a.line + 5
                    AND (s.name LIKE '%lock%' OR s.name LIKE '%mutex%' OR s.name LIKE '%synchronized%')
              )
              AND a.file LIKE '%.%s'
            ORDER BY a.file, a.line
        """ % ('js%',))
        
        for file, line, var_name in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='singleton-race',
                message=f'Singleton pattern "{var_name}" without proper synchronization',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='concurrency',
                confidence=Confidence.LOW,
                snippet=var_name,
                fix_suggestion='Use double-checked locking or module-level initialization',
                cwe_id='CWE-362'
            ))
        
        # ========================================================
        # CHECK 12: EventEmitter Memory Leaks
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%.on%'
                   OR f.callee_function LIKE '%.addEventListener%'
                   OR f.callee_function LIKE '%.addListener%')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND (f2.callee_function LIKE '%.off%'
                         OR f2.callee_function LIKE '%.removeEventListener%'
                         OR f2.callee_function LIKE '%.removeListener%'
                         OR f2.callee_function LIKE '%.removeAllListeners%')
              )
            ORDER BY f.file, f.line
            LIMIT 20
        """)
        
        for file, line, listener_func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='event-listener-leak',
                message=f'Event listener added with {listener_func} but never removed',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='memory-leak',
                confidence=Confidence.LOW,
                snippet=listener_func,
                fix_suggestion='Remove event listeners when no longer needed',
                cwe_id='CWE-401'
            ))
    
    finally:
        conn.close()
    
    return findings


def register_taint_patterns(taint_registry):
    """Register JavaScript/TypeScript concurrency-related patterns.
    
    Args:
        taint_registry: TaintRegistry instance
    """
    # Register shared state sources
    SHARED_STATE_SOURCES = [
        'global', 'window', 'globalThis', 'process.env',
        'module.exports', 'exports', 'self',
        'localStorage', 'sessionStorage', 'document',
        'SharedArrayBuffer', 'Atomics'
    ]
    
    for pattern in SHARED_STATE_SOURCES:
        taint_registry.register_source(pattern, 'shared_state', 'javascript')
    
    # Register async operations as sinks
    ASYNC_SINKS = [
        'Promise.all', 'Promise.race', 'Promise.allSettled', 'Promise.any',
        'async', 'await', 'then', 'catch', 'finally',
        'setTimeout', 'setInterval', 'setImmediate',
        'process.nextTick', 'queueMicrotask'
    ]
    
    for pattern in ASYNC_SINKS:
        taint_registry.register_sink(pattern, 'async_operation', 'javascript')
    
    # Register worker/thread operations as sinks
    WORKER_SINKS = [
        'Worker', 'SharedWorker', 'ServiceWorker',
        'worker_threads', 'cluster.fork', 'child_process.spawn',
        'child_process.fork', 'child_process.exec',
        'postMessage', 'terminate', 'disconnect'
    ]
    
    for pattern in WORKER_SINKS:
        taint_registry.register_sink(pattern, 'worker_thread', 'javascript')
    
    # Register stream operations as sinks
    STREAM_SINKS = [
        'createReadStream', 'createWriteStream',
        'pipe', 'pipeline', 'stream.Readable', 'stream.Writable',
        'fs.watch', 'fs.watchFile', 'chokidar.watch'
    ]
    
    for pattern in STREAM_SINKS:
        taint_registry.register_sink(pattern, 'stream_operation', 'javascript')
    
    # Register file system operations as sinks
    FS_SINKS = [
        'fs.readFile', 'fs.writeFile', 'fs.readFileSync', 'fs.writeFileSync',
        'fs.mkdir', 'fs.mkdirSync', 'fs.unlink', 'fs.unlinkSync',
        'fs.promises.readFile', 'fs.promises.writeFile'
    ]
    
    for pattern in FS_SINKS:
        taint_registry.register_sink(pattern, 'filesystem', 'javascript')