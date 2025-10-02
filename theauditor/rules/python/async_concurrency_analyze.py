"""Python Async and Concurrency Analyzer - Database-First Approach.

Detects race conditions, async issues, and concurrency problems using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows golden standard patterns from compose_analyze.py:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
- Proper confidence levels
"""

import sqlite3
from typing import List, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA (Phase 3B Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="python_async_concurrency",
    category="concurrency",
    target_extensions=['.py'],
    exclude_patterns=['frontend/', 'client/', 'node_modules/', 'test/', '__tests__/', 'migrations/'],
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class ConcurrencyPatterns:
    """Immutable pattern definitions for concurrency detection."""

    # TOCTOU (Time-of-Check-Time-of-Use) patterns
    TOCTOU_CHECKS = frozenset([
        'exists', 'isfile', 'isdir', 'path.exists', 'os.path.exists',
        'os.path.isfile', 'os.path.isdir', 'Path.exists', 'has_key',
        'hasattr', '__contains__'
    ])

    TOCTOU_ACTIONS = frozenset([
        'open', 'mkdir', 'makedirs', 'create', 'write', 'unlink',
        'remove', 'rmdir', 'rename', 'move', 'copy', 'shutil.copy',
        'shutil.move', 'Path.mkdir', 'Path.write_text', 'Path.write_bytes'
    ])

    # Threading/async imports that indicate concurrency
    CONCURRENCY_IMPORTS = frozenset([
        'threading', 'multiprocessing', 'asyncio', 'concurrent',
        'queue', 'Queue', 'gevent', 'eventlet', 'twisted',
        'trio', 'anyio', 'curio'
    ])

    # Lock/synchronization methods
    LOCK_METHODS = frozenset([
        'acquire', 'release', 'Lock', 'RLock', 'Semaphore',
        'BoundedSemaphore', 'Event', 'Condition', '__enter__',
        '__exit__', 'lock', 'unlock', 'wait', 'notify'
    ])

    # Async/await patterns
    ASYNC_METHODS = frozenset([
        'gather', 'asyncio.gather', 'wait', 'as_completed',
        'create_task', 'ensure_future', 'run_coroutine_threadsafe',
        'asyncio.create_task', 'asyncio.ensure_future', 'loop.create_task'
    ])

    # Thread/process lifecycle methods
    THREAD_START = frozenset([
        'start', 'Thread.start', 'Process.start', 'run',
        'submit', 'apply_async', 'map_async'
    ])

    THREAD_CLEANUP = frozenset([
        'join', 'Thread.join', 'Process.join', 'terminate',
        'kill', 'close', 'shutdown', 'wait', 'cancel'
    ])

    # Worker/pool patterns
    WORKER_CREATION = frozenset([
        'Process', 'Thread', 'Worker', 'Pool', 'ThreadPoolExecutor',
        'ProcessPoolExecutor', 'ThreadPool', 'ProcessPool', 'fork',
        'spawn', 'Popen'
    ])

    # Write operations that need synchronization
    WRITE_OPERATIONS = frozenset([
        'save', 'update', 'insert', 'write', 'delete', 'remove',
        'create', 'put', 'post', 'patch', 'upsert', 'bulk_create',
        'bulk_update', 'execute', 'executemany', 'commit'
    ])

    # Sleep/delay patterns
    SLEEP_METHODS = frozenset([
        'sleep', 'time.sleep', 'delay', 'wait', 'pause',
        'asyncio.sleep', 'gevent.sleep', 'eventlet.sleep'
    ])

    # Retry-related variables
    RETRY_VARIABLES = frozenset([
        'retry', 'retries', 'attempt', 'attempts', 'tries',
        'max_retries', 'retry_count', 'num_retries'
    ])

    # Exponential backoff patterns
    BACKOFF_PATTERNS = frozenset([
        '**', 'exponential', 'backoff', '*= 2', '* 2',
        '<< 1', 'math.pow', 'pow(2'
    ])

    # Singleton-related patterns
    SINGLETON_VARS = frozenset([
        'instance', '_instance', '__instance', 'singleton',
        '_singleton', '__singleton', 'INSTANCE', '_INSTANCE'
    ])

    # Global/shared state patterns
    SHARED_STATE_PATTERNS = frozenset([
        'self.', 'cls.', 'global ', '__class__.',
        'classmethod', 'staticmethod'
    ])


# ============================================================================
# HELPER: Table Existence Check
# ============================================================================
def _check_tables(cursor) -> Set[str]:
    """Check which tables exist in database for graceful degradation."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name IN ('function_call_args', 'assignments', 'symbols')
    """)
    return {row[0] for row in cursor.fetchall()}


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class AsyncConcurrencyAnalyzer:
    """Analyzer for Python async and concurrency issues."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ConcurrencyPatterns()
        self.findings = []
        self.existing_tables = set()

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of concurrency issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Check which tables exist (graceful degradation)
            existing_tables = _check_tables(self.cursor)

            # Must have function_call_args for core analysis
            if 'function_call_args' not in existing_tables:
                return []

            # Store for use in other methods
            self.existing_tables = existing_tables

            # Detect if project uses concurrency
            has_concurrency = self._detect_concurrency_usage()

            # Run appropriate checks based on available data
            if 'function_call_args' in self.existing_tables:
                self._check_race_conditions()
                self._check_async_without_await()
                self._check_parallel_writes()
                self._check_threading_issues()
                self._check_lock_issues()

            if 'assignments' in self.existing_tables:
                self._check_shared_state_no_lock(has_concurrency)

            if 'cfg_blocks' in self.existing_tables:
                self._check_sleep_in_loops()
                self._check_retry_without_backoff()

        finally:
            conn.close()

        return self.findings

    def _detect_concurrency_usage(self) -> bool:
        """Check if project uses threading/async/multiprocessing."""
        if 'refs' not in self.existing_tables:
            return True  # Assume yes if we can't check

        placeholders = ','.join('?' * len(self.patterns.CONCURRENCY_IMPORTS))
        self.cursor.execute(f"""
            SELECT COUNT(*) FROM refs
            WHERE value IN ({placeholders})
        """, list(self.patterns.CONCURRENCY_IMPORTS))

        count = self.cursor.fetchone()[0]
        return count > 0

    def _check_race_conditions(self):
        """Detect TOCTOU race conditions."""
        # Build query for check functions
        check_placeholders = ','.join('?' * len(self.patterns.TOCTOU_CHECKS))
        action_placeholders = ','.join('?' * len(self.patterns.TOCTOU_ACTIONS))

        self.cursor.execute(f"""
            SELECT DISTINCT f1.file, f1.line, f1.callee_function
            FROM function_call_args f1
            WHERE f1.callee_function IN ({check_placeholders})
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.line > f1.line
                    AND f2.line <= f1.line + 10
                    AND f2.callee_function IN ({action_placeholders})
              )
            ORDER BY f1.file, f1.line
        """, list(self.patterns.TOCTOU_CHECKS) + list(self.patterns.TOCTOU_ACTIONS))

        for file, line, check_func in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-toctou-race',
                message=f'Time-of-check-time-of-use race: {check_func} followed by action',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='concurrency',
                confidence=Confidence.HIGH,
                cwe_id='CWE-367'
            ))

    def _check_shared_state_no_lock(self, has_concurrency: bool):
        """Find shared state modifications without locks."""
        if not has_concurrency:
            return

        # Find assignments to class/instance variables
        self.cursor.execute("""
            SELECT DISTINCT a.file, a.line, a.target_var, a.in_function
            FROM assignments a
            WHERE (a.target_var LIKE 'self.%'
                   OR a.target_var LIKE 'cls.%'
                   OR a.target_var LIKE '__class__.%')
            ORDER BY a.file, a.line
        """)

        for file, line, var, function in self.cursor.fetchall():
            # Check for lock protection
            has_lock = self._check_lock_nearby(file, line, function)

            if not has_lock:
                # Determine confidence based on variable type
                confidence = Confidence.HIGH if '+=' in var or '-=' in var else Confidence.MEDIUM

                self.findings.append(StandardFinding(
                    rule_name='python-shared-state-no-lock',
                    message=f'Shared state "{var}" modified without synchronization',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='concurrency',
                    confidence=confidence,
                    cwe_id='CWE-362'
                ))

        # Check for counter operations
        self.cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.source_expr LIKE '%+= 1%'
                   OR a.source_expr LIKE '%-= 1%'
                   OR a.source_expr LIKE '%+= %'
                   OR a.source_expr LIKE '%-= %')
              AND (a.target_var LIKE 'self.%'
                   OR a.target_var LIKE 'cls.%')
        """)

        for file, line, var, expr in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-unprotected-increment',
                message=f'Unprotected counter operation on "{var}"',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='concurrency',
                confidence=Confidence.HIGH,
                cwe_id='CWE-362'
            ))

    def _check_lock_nearby(self, file: str, line: int, function: str) -> bool:
        """Check if there's lock protection nearby."""
        if 'function_call_args' not in self.existing_tables:
            return False

        lock_placeholders = ','.join('?' * len(self.patterns.LOCK_METHODS))
        params = list(self.patterns.LOCK_METHODS) + [file, line, line]

        # Add function parameter if provided
        query = f"""
            SELECT COUNT(*) FROM function_call_args f
            WHERE f.callee_function IN ({lock_placeholders})
              AND f.file = ?
              AND f.line >= ? - 5
              AND f.line <= ? + 5
        """

        if function:
            query += " AND f.caller_function = ?"
            params.append(function)

        self.cursor.execute(query + " LIMIT 1", params)
        return self.cursor.fetchone()[0] > 0

    def _check_async_without_await(self):
        """Find async function calls not awaited."""
        # First find functions that use await (likely async functions)
        self.cursor.execute("""
            SELECT DISTINCT caller_function
            FROM function_call_args
            WHERE argument_expr LIKE '%await%'
               OR callee_function LIKE '%await%'
        """)
        async_functions = {row[0] for row in self.cursor.fetchall() if row[0]}

        if not async_functions:
            return

        # Check calls to async functions without await
        placeholders = ','.join('?' * len(async_functions))
        self.cursor.execute(f"""
            SELECT file, line, callee_function, caller_function
            FROM function_call_args
            WHERE callee_function IN ({placeholders})
              AND argument_expr NOT LIKE '%await%'
              AND callee_function NOT IN ('asyncio.create_task', 'asyncio.ensure_future',
                                          'create_task', 'ensure_future', 'loop.create_task')
            ORDER BY file, line
        """, list(async_functions))

        for file, line, func, caller in self.cursor.fetchall():
            # Only flag if caller is also async
            if caller in async_functions:
                self.findings.append(StandardFinding(
                    rule_name='python-async-no-await',
                    message=f'Async function "{func}" called without await',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='concurrency',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-667'
                ))

    def _check_parallel_writes(self):
        """Find parallel operations with write operations."""
        # Check asyncio.gather with writes
        gather_placeholders = ','.join('?' * len(self.patterns.ASYNC_METHODS))
        self.cursor.execute(f"""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({gather_placeholders})
            ORDER BY file, line
        """, list(self.patterns.ASYNC_METHODS))

        for file, line, args in self.cursor.fetchall():
            if not args:
                continue

            # Check if arguments contain write operations
            has_writes = any(op in args.lower() for op in self.patterns.WRITE_OPERATIONS)

            if has_writes:
                self.findings.append(StandardFinding(
                    rule_name='python-parallel-writes',
                    message='Parallel write operations without synchronization',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='concurrency',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-362'
                ))

        # Check ThreadPoolExecutor/ProcessPoolExecutor with writes
        executor_patterns = ['ThreadPoolExecutor', 'ProcessPoolExecutor', 'map', 'submit']
        executor_placeholders = ','.join('?' * len(executor_patterns))
        write_placeholders = ','.join('?' * len(self.patterns.WRITE_OPERATIONS))

        self.cursor.execute(f"""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function IN ({executor_placeholders})
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND f2.line >= f.line - 10
                    AND f2.line <= f.line + 10
                    AND f2.callee_function IN ({write_placeholders})
              )
        """, executor_patterns + list(self.patterns.WRITE_OPERATIONS))

        for file, line, executor in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-executor-writes',
                message=f'Parallel executor "{executor}" with write operations',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='concurrency',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-362'
            ))

    def _check_threading_issues(self):
        """Find thread lifecycle issues."""
        # Find Thread.start() without join()
        start_placeholders = ','.join('?' * len(self.patterns.THREAD_START))
        cleanup_placeholders = ','.join('?' * len(self.patterns.THREAD_CLEANUP))

        self.cursor.execute(f"""
            SELECT DISTINCT f1.file, f1.line, f1.callee_function
            FROM function_call_args f1
            WHERE f1.callee_function IN ({start_placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.callee_function IN ({cleanup_placeholders})
                    AND f2.line > f1.line
              )
        """, list(self.patterns.THREAD_START) + list(self.patterns.THREAD_CLEANUP))

        for file, line, method in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-thread-no-join',
                message=f'Thread/Process "{method}" started but never joined',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='concurrency',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-404'
            ))

        # Find worker creation without cleanup
        worker_placeholders = ','.join('?' * len(self.patterns.WORKER_CREATION))

        self.cursor.execute(f"""
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IN ({worker_placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = file
                    AND f2.callee_function IN ({cleanup_placeholders})
                    AND f2.line > line
              )
        """, list(self.patterns.WORKER_CREATION) + list(self.patterns.THREAD_CLEANUP))

        for file, line, worker_type in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-worker-no-cleanup',
                message=f'{worker_type} created but may not be properly cleaned up',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='concurrency',
                confidence=Confidence.LOW,
                cwe_id='CWE-404'
            ))

    def _check_sleep_in_loops(self):
        """Find sleep operations in loops."""
        if 'cfg_blocks' not in self.existing_tables:
            return

        sleep_placeholders = ','.join('?' * len(self.patterns.SLEEP_METHODS))

        self.cursor.execute(f"""
            SELECT DISTINCT cb.file, f.line, f.callee_function
            FROM cfg_blocks cb
            JOIN function_call_args f ON f.file = cb.file
            WHERE cb.block_type IN ('loop', 'for_loop', 'while_loop')
              AND f.line >= cb.start_line
              AND f.line <= cb.end_line
              AND f.callee_function IN ({sleep_placeholders})
            ORDER BY cb.file, f.line
        """, list(self.patterns.SLEEP_METHODS))

        for file, line, sleep_func in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-sleep-in-loop',
                message=f'Sleep "{sleep_func}" in loop causes performance issues',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='performance',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))

    def _check_retry_without_backoff(self):
        """Find retry loops without exponential backoff."""
        if 'cfg_blocks' not in self.existing_tables or 'assignments' not in self.existing_tables:
            return

        # Find loops with retry variables
        retry_placeholders = ','.join('?' * len(self.patterns.RETRY_VARIABLES))

        self.cursor.execute(f"""
            SELECT DISTINCT cb.file, cb.start_line, cb.end_line
            FROM cfg_blocks cb
            WHERE cb.block_type IN ('loop', 'while_loop', 'for_loop')
              AND EXISTS (
                  SELECT 1 FROM assignments a
                  WHERE a.file = cb.file
                    AND a.line >= cb.start_line
                    AND a.line <= cb.end_line
                    AND (
                        a.target_var IN ({retry_placeholders})
                        OR a.source_expr LIKE '%retry%'
                        OR a.source_expr LIKE '%attempt%'
                    )
              )
        """, list(self.patterns.RETRY_VARIABLES))

        for file, start_line, end_line in self.cursor.fetchall():
            # Check for backoff patterns
            has_backoff = self._check_backoff_pattern(file, start_line, end_line)

            if not has_backoff:
                # Check if at least has sleep
                has_sleep = self._check_sleep_in_range(file, start_line, end_line)

                if has_sleep:
                    self.findings.append(StandardFinding(
                        rule_name='python-retry-no-backoff',
                        message='Retry logic without exponential backoff',
                        file_path=file,
                        line=start_line,
                        severity=Severity.MEDIUM,
                        category='performance',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-1050'
                    ))

    def _check_backoff_pattern(self, file: str, start: int, end: int) -> bool:
        """Check if there's exponential backoff in range."""
        if 'assignments' not in self.existing_tables:
            return False

        # Check for backoff patterns in assignments
        for pattern in self.patterns.BACKOFF_PATTERNS:
            self.cursor.execute("""
                SELECT COUNT(*) FROM assignments
                WHERE file = ?
                  AND line >= ?
                  AND line <= ?
                  AND source_expr LIKE ?
                LIMIT 1
            """, [file, start, end, f'%{pattern}%'])

            if self.cursor.fetchone()[0] > 0:
                return True

        return False

    def _check_sleep_in_range(self, file: str, start: int, end: int) -> bool:
        """Check if there's sleep in line range."""
        if 'function_call_args' not in self.existing_tables:
            return False

        sleep_placeholders = ','.join('?' * len(self.patterns.SLEEP_METHODS))

        self.cursor.execute(f"""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND line >= ?
              AND line <= ?
              AND callee_function IN ({sleep_placeholders})
            LIMIT 1
        """, [file, start, end] + list(self.patterns.SLEEP_METHODS))

        return self.cursor.fetchone()[0] > 0

    def _check_lock_issues(self):
        """Find lock-related issues."""
        # Check lock without timeout
        lock_placeholders = ','.join('?' * len(self.patterns.LOCK_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({lock_placeholders})
              AND (argument_expr IS NULL
                   OR (argument_expr NOT LIKE '%timeout%'
                       AND argument_expr NOT LIKE '%blocking%'))
            ORDER BY file, line
        """, list(self.patterns.LOCK_METHODS))

        for file, line, lock_func, args in self.cursor.fetchall():
            if lock_func in ['acquire', 'Lock', 'RLock', 'Semaphore']:
                self.findings.append(StandardFinding(
                    rule_name='python-lock-no-timeout',
                    message=f'Lock "{lock_func}" without timeout - infinite wait risk',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='concurrency',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-667'
                ))

        # Check for nested locks
        self.cursor.execute(f"""
            SELECT file, caller_function, COUNT(*) as lock_count
            FROM function_call_args
            WHERE callee_function IN ({lock_placeholders})
            GROUP BY file, caller_function
            HAVING COUNT(*) > 1
        """, list(self.patterns.LOCK_METHODS))

        for file, function, count in self.cursor.fetchall():
            if count > 1:
                self.findings.append(StandardFinding(
                    rule_name='python-nested-locks',
                    message=f'Multiple locks ({count}) in function "{function}" - deadlock risk',
                    file_path=file,
                    line=1,  # Can't determine exact line from aggregate
                    severity=Severity.CRITICAL,
                    category='concurrency',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-833'
                ))

        # Check singleton without synchronization
        if 'assignments' in self.existing_tables:
            singleton_placeholders = ','.join('?' * len(self.patterns.SINGLETON_VARS))

            self.cursor.execute(f"""
                SELECT a.file, a.line, a.target_var
                FROM assignments a
                WHERE a.target_var IN ({singleton_placeholders})
                  AND NOT EXISTS (
                      SELECT 1 FROM function_call_args f
                      WHERE f.file = a.file
                        AND f.callee_function IN ({lock_placeholders})
                        AND ABS(f.line - a.line) <= 5
                  )
            """, list(self.patterns.SINGLETON_VARS) + list(self.patterns.LOCK_METHODS))

            for file, line, var in self.cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='python-singleton-race',
                    message=f'Singleton "{var}" without synchronization',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='concurrency',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-362'
                ))


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_async_concurrency_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Python async and concurrency issues.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of concurrency issues found
    """
    analyzer = AsyncConcurrencyAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register concurrency-specific taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = ConcurrencyPatterns()

    # Register shared state sources
    SHARED_STATE_SOURCES = [
        "global", "self.", "cls.", "__class__.",
        "threading.local", "asyncio.Queue", "multiprocessing.Queue",
        "shared_memory", "mmap", "memoryview"
    ]

    for pattern in SHARED_STATE_SOURCES:
        taint_registry.register_source(pattern, "shared_state", "python")

    # Register synchronization sinks
    for pattern in patterns.LOCK_METHODS:
        taint_registry.register_sink(pattern, "synchronization", "python")

    # Register async operation sinks
    for pattern in patterns.ASYNC_METHODS:
        taint_registry.register_sink(pattern, "async_operation", "python")

    # Register thread/process sinks
    for pattern in patterns.THREAD_START:
        taint_registry.register_sink(pattern, "thread_process", "python")