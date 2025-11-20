"""Python Async and Concurrency Analyzer - Database-First Approach.

Detects race conditions, async issues, and concurrency problems using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""
from __future__ import annotations


import sqlite3
from typing import List, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query, get_table_schema


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

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of concurrency issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Schema validation - crash if tables missing (schema contract)
            self._validate_required_tables()

            # Detect if project uses concurrency
            has_concurrency = self._detect_concurrency_usage()

            # Run all checks
            self._check_race_conditions()
            self._check_async_without_await()
            self._check_parallel_writes()
            self._check_threading_issues()
            self._check_lock_issues()
            self._check_shared_state_no_lock(has_concurrency)
            self._check_sleep_in_loops()
            self._check_retry_without_backoff()

        finally:
            conn.close()

        return self.findings

    def _validate_required_tables(self):
        """Validate all required tables exist - crash if missing (schema contract)."""
        required_tables = [
            'refs', 'function_call_args', 'assignments',
            'cfg_blocks', 'cfg_edges', 'cfg_block_statements'
        ]
        for table_name in required_tables:
            # This will raise ValueError if table doesn't exist
            get_table_schema(table_name)

    def _validate_columns(self, table_name: str, columns: list[str]):
        """Validate columns exist in table schema.

        Args:
            table_name: Table to check
            columns: List of column names to validate

        Raises:
            ValueError: If table or column doesn't exist
        """
        schema = get_table_schema(table_name)
        valid_cols = set(schema.column_names())
        for col in columns:
            if col not in valid_cols:
                raise ValueError(
                    f"Column '{col}' not in table '{table_name}'. "
                    f"Valid columns: {', '.join(sorted(valid_cols))}"
                )

    def _detect_concurrency_usage(self) -> bool:
        """Check if project uses threading/async/multiprocessing.

        Schema: refs(src, kind, value, line)
        """
        # Validate columns used in query
        self._validate_columns('refs', ['value'])

        placeholders = ','.join('?' * len(self.patterns.CONCURRENCY_IMPORTS))
        self.cursor.execute(f"""
            SELECT COUNT(*) FROM refs
            WHERE value IN ({placeholders})
        """, list(self.patterns.CONCURRENCY_IMPORTS))

        count = self.cursor.fetchone()[0]
        return count > 0

    def _check_race_conditions(self):
        """Detect TOCTOU race conditions.

        Schema: function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
        """
        # Validate columns used in query
        self._validate_columns('function_call_args', ['file', 'line', 'callee_function'])

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
        """Find shared state modifications without locks.

        Schema: assignments(file, line, target_var, source_expr, source_vars, in_function)
        """
        if not has_concurrency:
            return

        # Validate columns used in query
        self._validate_columns('assignments', ['file', 'line', 'target_var', 'in_function', 'source_expr'])

        # Find assignments to class/instance variables - fetch all, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'in_function'],
                           order_by="file, line")
        self.cursor.execute(query)

        # Filter for class/instance variables in Python
        shared_state_assignments = []
        for file, line, var, function in self.cursor.fetchall():
            if var.startswith('self.') or var.startswith('cls.') or var.startswith('__class__.'):
                shared_state_assignments.append((file, line, var, function))

        for file, line, var, function in shared_state_assignments:
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

        # Check for counter operations - fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'])
        self.cursor.execute(query)

        # Counter operation patterns
        counter_ops = frozenset(['+= 1', '-= 1', '+= ', '-= '])

        for file, line, var, expr in self.cursor.fetchall():
            # Check for counter operations in Python
            if not expr or not any(op in expr for op in counter_ops):
                continue
            # Check for shared state variables
            if not (var.startswith('self.') or var.startswith('cls.')):
                continue
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
        """Check if there's lock protection nearby.

        Schema: function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
        """
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

        query += " LIMIT 1"
        self.cursor.execute(query, params)
        return self.cursor.fetchone()[0] > 0

    def _check_async_without_await(self):
        """Find async function calls not awaited.

        Schema: function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
        """
        # Validate columns used in query
        self._validate_columns('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_expr'])

        # Find functions that use await (likely async functions) - fetch all, filter in Python
        query = build_query('function_call_args', ['caller_function', 'argument_expr', 'callee_function'])
        self.cursor.execute(query)

        # Filter for await patterns in Python
        async_functions = set()
        for caller, arg_expr, callee in self.cursor.fetchall():
            if caller and ((arg_expr and 'await' in arg_expr) or 'await' in callee):
                async_functions.add(caller)

        if not async_functions:
            return

        # Check calls to async functions without await - fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'caller_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        # Async task creation functions (don't need await)
        task_creators = frozenset(['asyncio.create_task', 'asyncio.ensure_future', 'create_task', 'ensure_future', 'loop.create_task'])

        for file, line, func, caller, arg_expr in self.cursor.fetchall():
            # Check if calling an async function
            if func not in async_functions:
                continue
            # Check if missing await
            if arg_expr and 'await' in arg_expr:
                continue  # Has await, skip
            # Skip task creators
            if func in task_creators:
                continue
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
        """Find parallel operations with write operations.

        Schema: function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
        """
        # Validate columns used in query
        self._validate_columns('function_call_args', ['file', 'line', 'argument_expr', 'callee_function'])

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
        """Find thread lifecycle issues.

        Schema: function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
        """
        # Validate columns used in query
        self._validate_columns('function_call_args', ['file', 'line', 'callee_function'])

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
        """Find sleep operations in loops.

        Schema: cfg_blocks(id, file, function_name, block_type, start_line, end_line, condition_expr)
                function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
        """
        # Validate columns used in query
        self._validate_columns('cfg_blocks', ['file', 'block_type', 'start_line', 'end_line'])
        self._validate_columns('function_call_args', ['file', 'line', 'callee_function'])

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
        """Find retry loops without exponential backoff.

        Schema: cfg_blocks(id, file, function_name, block_type, start_line, end_line, condition_expr)
                assignments(file, line, target_var, source_expr, source_vars, in_function)
        """
        # Validate columns used in query
        self._validate_columns('cfg_blocks', ['file', 'block_type', 'start_line', 'end_line'])
        self._validate_columns('assignments', ['file', 'line', 'target_var', 'source_expr'])

        # Find loops with retry variables - fetch loops and assignments separately, join in Python
        # Get all loops
        query = build_query('cfg_blocks', ['file', 'start_line', 'end_line'],
                           where="block_type IN ('loop', 'while_loop', 'for_loop')")
        self.cursor.execute(query)
        all_loops = self.cursor.fetchall()

        # Get all assignments
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'])
        self.cursor.execute(query)
        all_assignments = self.cursor.fetchall()

        # Find loops with retry patterns in Python
        retry_loops = []
        for file, start_line, end_line in all_loops:
            has_retry = False
            for assign_file, assign_line, target_var, source_expr in all_assignments:
                if assign_file != file or not (start_line <= assign_line <= end_line):
                    continue

                # Check for retry patterns
                if target_var in self.patterns.RETRY_VARIABLES:
                    has_retry = True
                    break
                if source_expr and ('retry' in source_expr.lower() or 'attempt' in source_expr.lower()):
                    has_retry = True
                    break

            if has_retry:
                retry_loops.append((file, start_line, end_line))

        for file, start_line, end_line in retry_loops:
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
        """Check if there's exponential backoff in range.

        Schema: assignments(file, line, target_var, source_expr, source_vars, in_function)
        """
        # Fetch assignments in range, filter in Python
        query = build_query('assignments', ['source_expr'],
                           where="file = ? AND line >= ? AND line <= ?")
        self.cursor.execute(query, (file, start, end))

        # Check for backoff patterns in Python
        for (source_expr,) in self.cursor.fetchall():
            if not source_expr:
                continue
            source_lower = source_expr.lower()
            for pattern in self.patterns.BACKOFF_PATTERNS:
                if pattern.lower() in source_lower:
                    return True

        return False

    def _check_sleep_in_range(self, file: str, start: int, end: int) -> bool:
        """Check if there's sleep in line range.

        Schema: function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
        """
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
        """Find lock-related issues.

        Schema: function_call_args(file, line, caller_function, callee_function,
                                   argument_index, argument_expr, param_name)
                assignments(file, line, target_var, source_expr, source_vars, in_function)
        """
        # Validate columns used in query
        self._validate_columns('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_expr'])
        self._validate_columns('assignments', ['file', 'line', 'target_var'])

        # Check lock without timeout - fetch lock method calls, filter in Python
        lock_methods_list = list(self.patterns.LOCK_METHODS)
        lock_placeholders = ','.join('?' * len(lock_methods_list))

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"callee_function IN ({lock_placeholders})",
                           order_by="file, line")
        self.cursor.execute(query, lock_methods_list)

        for file, line, lock_func, args in self.cursor.fetchall():
            # Check for timeout/blocking keywords in Python
            if args:
                args_lower = args.lower()
                if 'timeout' in args_lower or 'blocking' in args_lower:
                    continue  # Has timeout config, skip
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

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
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