"""Golden Standard JavaScript/TypeScript Async and Concurrency Analyzer.

Detects race conditions, async issues, and concurrency problems via database analysis.
Demonstrates database-aware rule pattern using finite pattern matching.

MIGRATION STATUS: Golden Standard Implementation [2024-12-29]
Signature: context: StandardRuleContext -> List[StandardFinding]
"""

import json
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# PATTERN CONFIGURATION - Finite Pattern Sets
# ============================================================================

@dataclass(frozen=True)
class AsyncPatterns:
    """Configuration for JavaScript async/concurrency patterns."""

    # Async function indicators
    ASYNC_FUNCTIONS = frozenset([
        'async', 'await', 'Promise', 'then', 'catch', 'finally',
        'fetch', 'axios', 'ajax', 'request', 'http.get', 'https.get'
    ])

    # Promise methods
    PROMISE_METHODS = frozenset([
        'Promise.all', 'Promise.race', 'Promise.allSettled', 'Promise.any',
        'Promise.resolve', 'Promise.reject', 'then', 'catch', 'finally'
    ])

    # Timer functions
    TIMER_FUNCTIONS = frozenset([
        'setTimeout', 'setInterval', 'setImmediate', 'clearTimeout',
        'clearInterval', 'process.nextTick', 'queueMicrotask'
    ])

    # Worker/process functions
    WORKER_FUNCTIONS = frozenset([
        'Worker', 'SharedWorker', 'ServiceWorker', 'fork', 'spawn',
        'exec', 'execFile', 'cluster.fork', 'child_process'
    ])

    # Stream functions
    STREAM_FUNCTIONS = frozenset([
        'createReadStream', 'createWriteStream', 'pipe', 'pipeline',
        'stream.Readable', 'stream.Writable', 'fs.watch', 'fs.watchFile'
    ])

    # Shared state patterns
    SHARED_STATE = frozenset([
        'global', 'window', 'globalThis', 'process.env', 'process',
        'module.exports', 'exports', 'self', 'localStorage', 'sessionStorage',
        'document', 'SharedArrayBuffer', 'Atomics'
    ])

    # Write operations
    WRITE_OPERATIONS = frozenset([
        'save', 'update', 'insert', 'delete', 'write', 'create',
        'put', 'post', 'patch', 'remove', 'set', 'add', 'push'
    ])

    # Check operations (for TOCTOU)
    CHECK_OPERATIONS = frozenset([
        'exists', 'has', 'includes', 'contains', 'indexOf',
        'hasOwnProperty', 'in', 'get', 'find', 'some', 'every'
    ])

    # Counter variable patterns
    COUNTER_PATTERNS = frozenset([
        'count', 'counter', 'total', 'sum', 'index', 'idx',
        'num', 'amount', 'size', 'length', 'qty', 'quantity'
    ])

    # Singleton patterns
    SINGLETON_PATTERNS = frozenset([
        'instance', 'singleton', '_instance', '_singleton',
        'sharedInstance', 'defaultInstance', 'globalInstance'
    ])

    # Loop keywords
    LOOP_KEYWORDS = frozenset([
        'for', 'while', 'do', 'forEach', 'map', 'reduce',
        'filter', 'find', 'some', 'every', 'loop'
    ])

    # Cleanup functions
    CLEANUP_FUNCTIONS = frozenset([
        'close', 'destroy', 'end', 'terminate', 'kill', 'disconnect',
        'abort', 'cancel', 'unsubscribe', 'removeListener', 'removeAllListeners',
        'off', 'removeEventListener', 'clearInterval', 'clearTimeout'
    ])


# ============================================================================
# MAIN ENTRY POINT (Orchestrator Pattern)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect async and concurrency issues in JavaScript/TypeScript.

    This is the main entry point called by the orchestrator.

    Args:
        context: Standardized rule context with project metadata

    Returns:
        List of async/concurrency security findings
    """
    analyzer = AsyncConcurrencyAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# ANALYZER CLASS
# ============================================================================

class AsyncConcurrencyAnalyzer:
    """Main analyzer for JavaScript async and concurrency issues."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with context."""
        self.context = context
        self.patterns = AsyncPatterns()
        self.findings: List[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

    def analyze(self) -> List[StandardFinding]:
        """Run complete async/concurrency analysis."""
        if not self._is_javascript_project():
            return self.findings

        # Run all security checks
        self._check_async_without_await()
        self._check_promise_no_catch()
        self._check_promise_all_no_catch()
        self._check_parallel_writes()
        self._check_shared_state_modifications()
        self._check_unprotected_counters()
        self._check_sleep_in_loops()
        self._check_workers_not_terminated()
        self._check_streams_without_cleanup()
        self._check_toctou_race_conditions()
        self._check_retry_without_backoff()
        self._check_singleton_race_conditions()
        self._check_event_listener_leaks()
        self._check_callback_hell()

        return self.findings

    def _is_javascript_project(self) -> bool:
        """Check if this is a JavaScript/TypeScript project."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM files
                WHERE ext IN ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')
            """)

            count = cursor.fetchone()[0]
            conn.close()
            return count > 0

        except (sqlite3.Error, Exception):
            return False

    def _check_async_without_await(self) -> None:
        """Check for async operations called without await."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all function calls that look async
            cursor.execute("""
                SELECT f.file, f.line, f.callee_function, f.caller_function
                FROM function_call_args f
                WHERE f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                   OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx'
                   OR f.file LIKE '%.mjs' OR f.file LIKE '%.cjs'
                ORDER BY f.file, f.line
            """)

            for file, line, callee, caller in cursor.fetchall():
                # Check if function name indicates async
                is_async_call = False
                for pattern in self.patterns.ASYNC_FUNCTIONS:
                    if pattern in callee.lower():
                        is_async_call = True
                        break

                if is_async_call:
                    # Check if there's an await nearby
                    cursor.execute("""
                        SELECT COUNT(*) FROM symbols
                        WHERE path = ?
                          AND line = ?
                          AND (name = 'await' OR name LIKE '%.then%' OR name LIKE '%.catch%')
                    """, (file, line))

                    has_await = cursor.fetchone()[0] > 0

                    if not has_await and caller and 'async' not in caller:
                        self.findings.append(StandardFinding(
                            rule_name='async-without-await',
                            message=f'Async operation {callee} called without await',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='async',
                            confidence=Confidence.MEDIUM,
                            snippet=f'{callee}(...)',
                            fix_suggestion='Add await or handle with .then()/.catch()'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_promise_no_catch(self) -> None:
        """Check for promise chains without error handling."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

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

            for file, line, method in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='promise-no-catch',
                    message='Promise chain without error handling',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='error-handling',
                    confidence=Confidence.HIGH,
                    snippet=method,
                    fix_suggestion='Add .catch() to handle promise rejections'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_promise_all_no_catch(self) -> None:
        """Check for Promise.all without error handling."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.file, f.line
                FROM function_call_args f
                WHERE f.callee_function IN ('Promise.all', 'Promise.allSettled', 'Promise.race')
                  AND NOT EXISTS (
                      SELECT 1 FROM function_call_args f2
                      WHERE f2.file = f.file
                        AND f2.line BETWEEN f.line AND f.line + 5
                        AND f2.callee_function LIKE '%.catch%'
                  )
                ORDER BY f.file, f.line
            """)

            for file, line in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='promise-all-no-catch',
                    message='Promise.all without error handling',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='error-handling',
                    confidence=Confidence.HIGH,
                    snippet='Promise.all(...)',
                    fix_suggestion='Add .catch() to handle any promise rejection'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_parallel_writes(self) -> None:
        """Check for Promise.all with write operations."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.file, f.line, f.argument_expr
                FROM function_call_args f
                WHERE f.callee_function IN ('Promise.all', 'Promise.allSettled')
                ORDER BY f.file, f.line
            """)

            for file, line, args in cursor.fetchall():
                # Check if arguments contain write operations
                has_writes = False
                for write_op in self.patterns.WRITE_OPERATIONS:
                    if write_op in args.lower():
                        has_writes = True
                        break

                if has_writes:
                    self.findings.append(StandardFinding(
                        rule_name='parallel-writes-no-sync',
                        message='Parallel write operations in Promise.all',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='concurrency',
                        confidence=Confidence.HIGH,
                        snippet=args[:100] if len(args) > 100 else args,
                        fix_suggestion='Use sequential operations or database transactions'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_shared_state_modifications(self) -> None:
        """Check for shared/global state modifications."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE file LIKE '%.js' OR file LIKE '%.jsx'
                   OR file LIKE '%.ts' OR file LIKE '%.tsx'
                ORDER BY file, line
            """)

            for file, line, target, source in cursor.fetchall():
                # Check if target is shared state
                is_shared = False
                for pattern in self.patterns.SHARED_STATE:
                    if pattern in target:
                        is_shared = True
                        break

                if is_shared:
                    self.findings.append(StandardFinding(
                        rule_name='shared-state-no-lock',
                        message=f'Shared state "{target}" modified without synchronization',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='concurrency',
                        confidence=Confidence.MEDIUM,
                        snippet=f'{target} = ...',
                        fix_suggestion='Use locks, mutexes, or immutable updates'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unprotected_counters(self) -> None:
        """Check for unprotected counter increments."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT a.file, a.line, a.target_var, a.source_expr
                FROM assignments a
                WHERE (a.source_expr LIKE '%++%'
                       OR a.source_expr LIKE '%--%'
                       OR a.source_expr LIKE '%+= 1%'
                       OR a.source_expr LIKE '%-= 1%')
                  AND (a.file LIKE '%.js' OR a.file LIKE '%.jsx'
                       OR a.file LIKE '%.ts' OR a.file LIKE '%.tsx')
                ORDER BY a.file, a.line
            """)

            for file, line, target, expr in cursor.fetchall():
                # Check if variable name suggests a counter
                is_counter = False
                for pattern in self.patterns.COUNTER_PATTERNS:
                    if pattern in target.lower():
                        is_counter = True
                        break

                if is_counter:
                    # Check if in async context
                    cursor.execute("""
                        SELECT COUNT(*) FROM symbols
                        WHERE path = ?
                          AND line BETWEEN ? AND ?
                          AND (name = 'async' OR name = 'Promise' OR name = 'await')
                    """, (file, line - 10, line + 10))

                    in_async = cursor.fetchone()[0] > 0

                    if in_async:
                        self.findings.append(StandardFinding(
                            rule_name='unprotected-global-increment',
                            message=f'Counter "{target}" incremented without atomic operations',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='concurrency',
                            confidence=Confidence.MEDIUM,
                            snippet=expr,
                            fix_suggestion='Use Atomics API or synchronization'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_sleep_in_loops(self) -> None:
        """Check for setTimeout/setInterval in loops."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check by function context
            cursor.execute("""
                SELECT f.file, f.line, f.callee_function
                FROM function_call_args f
                WHERE f.callee_function IN ('setTimeout', 'setInterval', 'sleep', 'delay')
                  AND f.caller_function LIKE '%loop%'
                ORDER BY f.file, f.line
            """)

            for file, line, func in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='sleep-in-loop',
                    message=f'{func} in loop causes performance issues',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='performance',
                    confidence=Confidence.MEDIUM,
                    snippet=func,
                    fix_suggestion='Use async/await with Promise-based delays'
                ))

            # Check by proximity to loop keywords
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

            for file, line, func in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='sleep-in-loop',
                    message=f'{func} inside loop - performance anti-pattern',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='performance',
                    confidence=Confidence.HIGH,
                    snippet=func,
                    fix_suggestion='Move timer outside loop or use async iteration'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_workers_not_terminated(self) -> None:
        """Check for workers/processes not properly terminated."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.file, f.line, f.callee_function
                FROM function_call_args f
                WHERE f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                   OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx'
                ORDER BY f.file, f.line
            """)

            for file, line, func in cursor.fetchall():
                # Check if it's a worker function
                is_worker = False
                for pattern in self.patterns.WORKER_FUNCTIONS:
                    if pattern in func:
                        is_worker = True
                        break

                if is_worker:
                    # Check for cleanup nearby
                    cursor.execute("""
                        SELECT COUNT(*) FROM function_call_args
                        WHERE file = ?
                          AND line > ?
                          AND line < ? + 100
                    """, (file, line, line))

                    following_calls = cursor.fetchone()[0]

                    if following_calls > 0:
                        # Check if any cleanup functions called
                        cursor.execute("""
                            SELECT COUNT(*) FROM function_call_args f
                            WHERE f.file = ?
                              AND f.line > ?
                              AND f.line < ? + 100
                              AND f.callee_function IN ('terminate', 'kill', 'disconnect', 'close')
                        """, (file, line, line))

                        has_cleanup = cursor.fetchone()[0] > 0

                        if not has_cleanup:
                            self.findings.append(StandardFinding(
                                rule_name='worker-no-terminate',
                                message=f'Worker created with {func} but not terminated',
                                file_path=file,
                                line=line,
                                severity=Severity.MEDIUM,
                                category='resource-management',
                                confidence=Confidence.MEDIUM,
                                snippet=func,
                                fix_suggestion='Ensure cleanup with terminate() or disconnect()'
                            ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_streams_without_cleanup(self) -> None:
        """Check for streams without cleanup handlers."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.file, f.line, f.callee_function
                FROM function_call_args f
                WHERE f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                   OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx'
                ORDER BY f.file, f.line
            """)

            for file, line, func in cursor.fetchall():
                # Check if it's a stream function
                is_stream = False
                for pattern in self.patterns.STREAM_FUNCTIONS:
                    if pattern in func:
                        is_stream = True
                        break

                if is_stream:
                    # Check for cleanup handlers
                    cursor.execute("""
                        SELECT COUNT(*) FROM function_call_args
                        WHERE file = ?
                          AND line > ?
                          AND line < ? + 50
                          AND (callee_function LIKE '%.close%'
                               OR callee_function LIKE '%.destroy%'
                               OR callee_function LIKE '%.end%'
                               OR callee_function LIKE '%.on%error%')
                    """, (file, line, line))

                    has_cleanup = cursor.fetchone()[0] > 0

                    if not has_cleanup:
                        self.findings.append(StandardFinding(
                            rule_name='stream-no-close',
                            message=f'Stream created with {func} without cleanup',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='resource-management',
                            confidence=Confidence.MEDIUM,
                            snippet=func,
                            fix_suggestion='Add error and close handlers'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_toctou_race_conditions(self) -> None:
        """Check for time-of-check-time-of-use race conditions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f1.file, f1.line, f1.callee_function, f2.callee_function
                FROM function_call_args f1
                JOIN function_call_args f2 ON f1.file = f2.file
                WHERE f2.line BETWEEN f1.line + 1 AND f1.line + 10
                ORDER BY f1.file, f1.line
            """)

            for file, line, check_func, write_func in cursor.fetchall():
                # Check if first is a check operation
                is_check = False
                for pattern in self.patterns.CHECK_OPERATIONS:
                    if pattern in check_func:
                        is_check = True
                        break

                # Check if second is a write operation
                is_write = False
                for pattern in self.patterns.WRITE_OPERATIONS:
                    if pattern in write_func:
                        is_write = True
                        break

                if is_check and is_write:
                    self.findings.append(StandardFinding(
                        rule_name='check-then-act',
                        message=f'TOCTOU race: {check_func} then {write_func}',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='race-condition',
                        confidence=Confidence.HIGH,
                        snippet=f'{check_func} -> {write_func}',
                        fix_suggestion='Use atomic operations or locks'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_retry_without_backoff(self) -> None:
        """Check for retry logic without exponential backoff."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE (target_var LIKE '%retry%'
                       OR target_var LIKE '%attempt%'
                       OR target_var LIKE '%tries%')
                  AND NOT (source_expr LIKE '%Math.pow%'
                           OR source_expr LIKE '%**%'
                           OR source_expr LIKE '%exponential%'
                           OR source_expr LIKE '%backoff%'
                           OR source_expr LIKE '%*=%')
                  AND (file LIKE '%.js' OR file LIKE '%.jsx'
                       OR file LIKE '%.ts' OR file LIKE '%.tsx')
                ORDER BY file, line
            """)

            for file, line, var, expr in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='retry-without-backoff',
                    message='Retry logic without exponential backoff',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='performance',
                    confidence=Confidence.LOW,
                    snippet=expr[:100] if len(expr) > 100 else expr,
                    fix_suggestion='Implement exponential backoff: delay *= 2'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_singleton_race_conditions(self) -> None:
        """Check for singleton patterns without synchronization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, target_var
                FROM assignments
                WHERE source_expr LIKE '%new %'
                  AND (file LIKE '%.js' OR file LIKE '%.jsx'
                       OR file LIKE '%.ts' OR file LIKE '%.tsx')
                ORDER BY file, line
            """)

            for file, line, var in cursor.fetchall():
                # Check if variable suggests singleton
                is_singleton = False
                for pattern in self.patterns.SINGLETON_PATTERNS:
                    if pattern in var.lower():
                        is_singleton = True
                        break

                if is_singleton:
                    # Check for synchronization nearby
                    cursor.execute("""
                        SELECT COUNT(*) FROM symbols
                        WHERE path = ?
                          AND line BETWEEN ? AND ?
                          AND (name LIKE '%lock%' OR name LIKE '%mutex%'
                               OR name LIKE '%synchronized%')
                    """, (file, line - 5, line + 5))

                    has_sync = cursor.fetchone()[0] > 0

                    if not has_sync:
                        self.findings.append(StandardFinding(
                            rule_name='singleton-race',
                            message=f'Singleton "{var}" without synchronization',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='concurrency',
                            confidence=Confidence.LOW,
                            snippet=var,
                            fix_suggestion='Use double-checked locking'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_event_listener_leaks(self) -> None:
        """Check for event listeners that are never removed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

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
                             OR f2.callee_function LIKE '%.removeListener%')
                  )
                ORDER BY f.file, f.line
                LIMIT 20
            """)

            for file, line, func in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='event-listener-leak',
                    message=f'Event listener {func} never removed',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='memory-leak',
                    confidence=Confidence.LOW,
                    snippet=func,
                    fix_suggestion='Remove listeners when no longer needed'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_callback_hell(self) -> None:
        """Check for deeply nested callbacks (callback hell)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Look for nested function patterns in arguments
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE (argument_expr LIKE '%function%function%'
                       OR argument_expr LIKE '%=>%=>%'
                       OR argument_expr LIKE '%callback%callback%')
                  AND (file LIKE '%.js' OR file LIKE '%.jsx'
                       OR file LIKE '%.ts' OR file LIKE '%.tsx')
                ORDER BY file, line
                LIMIT 50
            """)

            for file, line, func, args in cursor.fetchall():
                # Count nesting depth by counting function keywords
                nesting = max(
                    args.lower().count('function'),
                    args.count('=>')
                )

                if nesting >= 2:
                    self.findings.append(StandardFinding(
                        rule_name='callback-hell',
                        message=f'Deeply nested callbacks detected (depth: {nesting})',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM if nesting == 2 else Severity.HIGH,
                        category='code-quality',
                        confidence=Confidence.MEDIUM,
                        snippet=args[:100] if len(args) > 100 else args,
                        fix_suggestion='Refactor using async/await or Promises'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass