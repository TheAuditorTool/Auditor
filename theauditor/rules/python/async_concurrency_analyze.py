"""Python Async and Concurrency Analyzer - Detects race conditions and concurrency issues."""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="python_async_concurrency",
    category="concurrency",
    target_extensions=[".py"],
    exclude_patterns=[
        "node_modules/",
        "vendor/",
        ".venv/",
        "__pycache__/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)


COUNTER_OPS = frozenset(["+= 1", "-= 1", "+= ", "-= "])


TASK_CREATORS = frozenset(
    [
        "asyncio.create_task",
        "asyncio.ensure_future",
        "create_task",
        "ensure_future",
        "loop.create_task",
    ]
)


EXECUTOR_PATTERNS = ("ThreadPoolExecutor", "ProcessPoolExecutor", "map", "submit")


TOCTOU_CHECKS = frozenset(
    [
        "exists",
        "isfile",
        "isdir",
        "path.exists",
        "os.path.exists",
        "os.path.isfile",
        "os.path.isdir",
        "Path.exists",
        "has_key",
        "hasattr",
        "__contains__",
    ]
)


TOCTOU_ACTIONS = frozenset(
    [
        "open",
        "mkdir",
        "makedirs",
        "create",
        "write",
        "unlink",
        "remove",
        "rmdir",
        "rename",
        "move",
        "copy",
        "shutil.copy",
        "shutil.move",
        "Path.mkdir",
        "Path.write_text",
        "Path.write_bytes",
    ]
)


CONCURRENCY_IMPORTS = frozenset(
    [
        "threading",
        "multiprocessing",
        "asyncio",
        "concurrent",
        "queue",
        "Queue",
        "gevent",
        "eventlet",
        "twisted",
        "trio",
        "anyio",
        "curio",
    ]
)


LOCK_METHODS = frozenset(
    [
        "acquire",
        "release",
        "Lock",
        "RLock",
        "Semaphore",
        "BoundedSemaphore",
        "Event",
        "Condition",
        "__enter__",
        "__exit__",
        "lock",
        "unlock",
        "wait",
        "notify",
    ]
)


ASYNC_METHODS = frozenset(
    [
        "gather",
        "asyncio.gather",
        "wait",
        "as_completed",
        "create_task",
        "ensure_future",
        "run_coroutine_threadsafe",
        "asyncio.create_task",
        "asyncio.ensure_future",
        "loop.create_task",
    ]
)


THREAD_START = frozenset(
    [
        "start",
        "Thread.start",
        "Process.start",
        "run",
        "submit",
        "apply_async",
        "map_async",
    ]
)


THREAD_CLEANUP = frozenset(
    [
        "join",
        "Thread.join",
        "Process.join",
        "terminate",
        "kill",
        "close",
        "shutdown",
        "wait",
        "cancel",
    ]
)


WORKER_CREATION = frozenset(
    [
        "Process",
        "Thread",
        "Worker",
        "Pool",
        "ThreadPoolExecutor",
        "ProcessPoolExecutor",
        "ThreadPool",
        "ProcessPool",
        "fork",
        "spawn",
        "Popen",
    ]
)


WRITE_OPERATIONS = frozenset(
    [
        "save",
        "update",
        "insert",
        "write",
        "delete",
        "remove",
        "create",
        "put",
        "post",
        "patch",
        "upsert",
        "bulk_create",
        "bulk_update",
        "execute",
        "executemany",
        "commit",
    ]
)


SLEEP_METHODS = frozenset(
    [
        "sleep",
        "time.sleep",
        "delay",
        "wait",
        "pause",
        "asyncio.sleep",
        "gevent.sleep",
        "eventlet.sleep",
    ]
)


RETRY_VARIABLES = frozenset(
    [
        "retry",
        "retries",
        "attempt",
        "attempts",
        "tries",
        "max_retries",
        "retry_count",
        "num_retries",
    ]
)


BACKOFF_PATTERNS = frozenset(
    [
        "**",
        "exponential",
        "backoff",
        "*= 2",
        "* 2",
        "<< 1",
        "math.pow",
        "pow(2",
    ]
)


SINGLETON_VARS = frozenset(
    [
        "instance",
        "_instance",
        "__instance",
        "singleton",
        "_singleton",
        "__singleton",
        "INSTANCE",
        "_INSTANCE",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Python async and concurrency issues.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []
        seen: set[str] = set()

        def add_finding(
            file: str,
            line: int,
            rule_name: str,
            message: str,
            severity: Severity,
            confidence: Confidence = Confidence.HIGH,
            cwe_id: str | None = None,
        ) -> None:
            """Add a finding if not already seen."""
            key = f"{file}:{line}:{rule_name}"
            if key in seen:
                return
            seen.add(key)

            findings.append(
                StandardFinding(
                    rule_name=rule_name,
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category=METADATA.category,
                    confidence=confidence,
                    cwe_id=cwe_id,
                )
            )

        has_concurrency = _detect_concurrency_usage(db)

        _check_race_conditions(db, add_finding)
        _check_async_without_await(db, add_finding)
        _check_parallel_writes(db, add_finding)
        _check_threading_issues(db, add_finding)
        _check_lock_issues(db, add_finding)
        _check_shared_state_no_lock(db, add_finding, has_concurrency)
        _check_sleep_in_loops(db, add_finding)
        _check_retry_without_backoff(db, add_finding)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _detect_concurrency_usage(db: RuleDB) -> bool:
    """Check if project uses threading/async/multiprocessing."""
    rows = db.query(Q("refs").select("COUNT(*)").where_in("value", list(CONCURRENCY_IMPORTS)))
    count = rows[0][0] if rows else 0
    return count > 0


def _check_race_conditions(db: RuleDB, add_finding) -> None:
    """Detect TOCTOU (time-of-check-time-of-use) race conditions.

    Pattern: check(path) followed by action(path) without atomic operation.
    Example: if os.path.exists(f): open(f) -- race between check and open.
    """
    check_placeholders = ", ".join("?" for _ in TOCTOU_CHECKS)
    action_placeholders = ", ".join("?" for _ in TOCTOU_ACTIONS)

    sql, params = Q.raw(
        f"""
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
        """,
        list(TOCTOU_CHECKS) + list(TOCTOU_ACTIONS),
    )

    for row in db.execute(sql, params):
        file, line, check_func = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-toctou-race",
            message=f"Time-of-check-time-of-use race: {check_func} followed by action",
            severity=Severity.CRITICAL,
            confidence=Confidence.HIGH,
            cwe_id="CWE-367",
        )


def _check_async_without_await(db: RuleDB, add_finding) -> None:
    """Find async function calls not awaited.

    Missing await causes coroutine to never execute, silently dropping work.
    """

    rows = db.query(
        Q("function_call_args").select("caller_function", "argument_expr", "callee_function")
    )

    async_functions = set()
    for row in rows:
        caller, arg_expr, callee = row[0], row[1], row[2]
        if caller and (
            (arg_expr and "await" in str(arg_expr)) or (callee and "await" in str(callee))
        ):
            async_functions.add(caller)

    if not async_functions:
        return

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, func, caller, arg_expr = row[0], row[1], row[2], row[3], row[4]

        if func not in async_functions:
            continue

        if arg_expr and "await" in str(arg_expr):
            continue

        if func in TASK_CREATORS:
            continue

        if caller in async_functions:
            add_finding(
                file=file,
                line=line,
                rule_name="python-async-no-await",
                message=f'Async function "{func}" called without await',
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-667",
            )


def _check_parallel_writes(db: RuleDB, add_finding) -> None:
    """Find parallel operations with write operations - data corruption risk."""

    async_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where_in("callee_function", list(ASYNC_METHODS))
        .order_by("file, line")
    )

    for row in async_rows:
        file, line, args = row[0], row[1], row[2]
        if not args:
            continue

        args_lower = str(args).lower()
        has_writes = any(op in args_lower for op in WRITE_OPERATIONS)

        if has_writes:
            add_finding(
                file=file,
                line=line,
                rule_name="python-parallel-writes",
                message="Parallel write operations without synchronization",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-362",
            )

    executor_placeholders = ", ".join("?" for _ in EXECUTOR_PATTERNS)
    write_placeholders = ", ".join("?" for _ in WRITE_OPERATIONS)

    sql, params = Q.raw(
        f"""
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
        """,
        list(EXECUTOR_PATTERNS) + list(WRITE_OPERATIONS),
    )

    for row in db.execute(sql, params):
        file, line, executor = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-executor-writes",
            message=f'Parallel executor "{executor}" with write operations',
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-362",
        )


def _check_threading_issues(db: RuleDB, add_finding) -> None:
    """Find thread lifecycle issues - threads started but not joined."""
    start_placeholders = ", ".join("?" for _ in THREAD_START)
    cleanup_placeholders = ", ".join("?" for _ in THREAD_CLEANUP)

    sql, params = Q.raw(
        f"""
        SELECT DISTINCT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.callee_function IN ({start_placeholders})
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.callee_function IN ({cleanup_placeholders})
                AND f2.line > f1.line
          )
        """,
        list(THREAD_START) + list(THREAD_CLEANUP),
    )

    for row in db.execute(sql, params):
        file, line, method = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-thread-no-join",
            message=f'Thread/Process "{method}" started but never joined',
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-404",
        )

    worker_placeholders = ", ".join("?" for _ in WORKER_CREATION)

    sql, params = Q.raw(
        f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE callee_function IN ({worker_placeholders})
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = file
                AND f2.callee_function IN ({cleanup_placeholders})
                AND f2.line > line
          )
        """,
        list(WORKER_CREATION) + list(THREAD_CLEANUP),
    )

    for row in db.execute(sql, params):
        file, line, worker_type = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-worker-no-cleanup",
            message=f"{worker_type} created but may not be properly cleaned up",
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            cwe_id="CWE-404",
        )


def _check_lock_issues(db: RuleDB, add_finding) -> None:
    """Find lock-related issues: missing timeouts, nested locks, unprotected singletons."""
    lock_placeholders = ", ".join("?" for _ in LOCK_METHODS)

    sql, params = Q.raw(
        f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ({lock_placeholders})
        ORDER BY file, line
        """,
        list(LOCK_METHODS),
    )

    for row in db.execute(sql, params):
        file, line, lock_func, args = row[0], row[1], row[2], row[3]
        if args:
            args_lower = str(args).lower()
            if "timeout" in args_lower or "blocking" in args_lower:
                continue
        if lock_func in ("acquire", "Lock", "RLock", "Semaphore"):
            add_finding(
                file=file,
                line=line,
                rule_name="python-lock-no-timeout",
                message=f'Lock "{lock_func}" without timeout - infinite wait risk',
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-667",
            )

    sql, params = Q.raw(
        f"""
        SELECT file, caller_function, COUNT(*) as lock_count
        FROM function_call_args
        WHERE callee_function IN ({lock_placeholders})
          AND caller_function IS NOT NULL
        GROUP BY file, caller_function
        HAVING COUNT(*) > 1
        """,
        list(LOCK_METHODS),
    )

    for row in db.execute(sql, params):
        file, function, count = row[0], row[1], row[2]
        if count > 1 and function:
            add_finding(
                file=file,
                line=1,
                rule_name="python-nested-locks",
                message=f'Multiple locks ({count}) in function "{function}" - deadlock risk',
                severity=Severity.CRITICAL,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-833",
            )

    singleton_placeholders = ", ".join("?" for _ in SINGLETON_VARS)

    sql, params = Q.raw(
        f"""
        SELECT a.file, a.line, a.target_var
        FROM assignments a
        WHERE a.target_var IN ({singleton_placeholders})
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f
              WHERE f.file = a.file
                AND f.callee_function IN ({lock_placeholders})
                AND ABS(f.line - a.line) <= 5
          )
        """,
        list(SINGLETON_VARS) + list(LOCK_METHODS),
    )

    for row in db.execute(sql, params):
        file, line, var = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-singleton-race",
            message=f'Singleton "{var}" without synchronization',
            severity=Severity.CRITICAL,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-362",
        )


def _check_shared_state_no_lock(db: RuleDB, add_finding, has_concurrency: bool) -> None:
    """Find shared state modifications without locks."""
    if not has_concurrency:
        return

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "in_function", "source_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, var, function, source_expr = row[0], row[1], row[2], row[3], row[4]

        if not var:
            continue
        if not (var.startswith("self.") or var.startswith("cls.") or var.startswith("__class__.")):
            continue

        has_lock = _check_lock_nearby(db, file, line, function)

        if not has_lock:
            confidence = (
                Confidence.HIGH if any(op in str(var) for op in COUNTER_OPS) else Confidence.MEDIUM
            )

            add_finding(
                file=file,
                line=line,
                rule_name="python-shared-state-no-lock",
                message=f'Shared state "{var}" modified without synchronization',
                severity=Severity.HIGH,
                confidence=confidence,
                cwe_id="CWE-362",
            )

        if source_expr and any(op in str(source_expr) for op in COUNTER_OPS):
            add_finding(
                file=file,
                line=line,
                rule_name="python-unprotected-increment",
                message=f'Unprotected counter operation on "{var}"',
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-362",
            )


def _check_lock_nearby(db: RuleDB, file: str, line: int, function: str | None) -> bool:
    """Check if there's lock protection nearby."""
    lock_placeholders = ", ".join("?" for _ in LOCK_METHODS)
    params = list(LOCK_METHODS) + [file, line, line]

    if function:
        sql, params = Q.raw(
            f"""
            SELECT COUNT(*) FROM function_call_args f
            WHERE f.callee_function IN ({lock_placeholders})
              AND f.file = ?
              AND f.line >= ? - 5
              AND f.line <= ? + 5
              AND f.caller_function = ?
            LIMIT 1
            """,
            list(LOCK_METHODS) + [file, line, line, function],
        )
    else:
        sql, params = Q.raw(
            f"""
            SELECT COUNT(*) FROM function_call_args f
            WHERE f.callee_function IN ({lock_placeholders})
              AND f.file = ?
              AND f.line >= ? - 5
              AND f.line <= ? + 5
            LIMIT 1
            """,
            list(LOCK_METHODS) + [file, line, line],
        )

    rows = db.execute(sql, params)
    return rows[0][0] > 0 if rows else False


def _check_sleep_in_loops(db: RuleDB, add_finding) -> None:
    """Find sleep operations in loops - performance antipattern."""
    sleep_placeholders = ", ".join("?" for _ in SLEEP_METHODS)

    sql, params = Q.raw(
        f"""
        SELECT DISTINCT cb.file, f.line, f.callee_function
        FROM cfg_blocks cb
        JOIN function_call_args f ON f.file = cb.file
        WHERE cb.block_type IN ('loop', 'for_loop', 'while_loop')
          AND f.line >= cb.start_line
          AND f.line <= cb.end_line
          AND f.callee_function IN ({sleep_placeholders})
        ORDER BY cb.file, f.line
        """,
        list(SLEEP_METHODS),
    )

    for row in db.execute(sql, params):
        file, line, sleep_func = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-sleep-in-loop",
            message=f'Sleep "{sleep_func}" in loop causes performance issues',
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            cwe_id="CWE-1050",
        )


def _check_retry_without_backoff(db: RuleDB, add_finding) -> None:
    """Find retry loops without exponential backoff - thundering herd risk."""

    loop_rows = db.query(
        Q("cfg_blocks")
        .select("file", "start_line", "end_line")
        .where("block_type IN (?, ?, ?)", "loop", "while_loop", "for_loop")
    )

    assignment_rows = db.query(Q("assignments").select("file", "line", "target_var", "source_expr"))

    assignments_by_file: dict[str, list] = {}
    for row in assignment_rows:
        file = row[0]
        if file not in assignments_by_file:
            assignments_by_file[file] = []
        assignments_by_file[file].append(row)

    retry_loops = []
    for loop_row in loop_rows:
        file, start_line, end_line = loop_row[0], loop_row[1], loop_row[2]

        has_retry = False
        for assign in assignments_by_file.get(file, []):
            assign_line, target_var, source_expr = assign[1], assign[2], assign[3]
            if not (start_line <= assign_line <= end_line):
                continue

            if target_var and target_var in RETRY_VARIABLES:
                has_retry = True
                break
            if source_expr and (
                "retry" in str(source_expr).lower() or "attempt" in str(source_expr).lower()
            ):
                has_retry = True
                break

        if has_retry:
            retry_loops.append((file, start_line, end_line))

    for file, start_line, end_line in retry_loops:
        has_backoff = _check_backoff_pattern(db, file, start_line, end_line)

        if not has_backoff:
            has_sleep = _check_sleep_in_range(db, file, start_line, end_line)

            if has_sleep:
                add_finding(
                    file=file,
                    line=start_line,
                    rule_name="python-retry-no-backoff",
                    message="Retry logic without exponential backoff",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-1050",
                )


def _check_backoff_pattern(db: RuleDB, file: str, start: int, end: int) -> bool:
    """Check if there's exponential backoff in range."""
    rows = db.query(
        Q("assignments")
        .select("source_expr")
        .where("file = ? AND line >= ? AND line <= ?", file, start, end)
    )

    for row in rows:
        source_expr = row[0]
        if not source_expr:
            continue
        source_lower = str(source_expr).lower()
        for pattern in BACKOFF_PATTERNS:
            if pattern.lower() in source_lower:
                return True

    return False


def _check_sleep_in_range(db: RuleDB, file: str, start: int, end: int) -> bool:
    """Check if there's sleep in line range."""
    rows = db.query(
        Q("function_call_args")
        .select("COUNT(*)")
        .where("file = ? AND line >= ? AND line <= ?", file, start, end)
        .where_in("callee_function", list(SLEEP_METHODS))
        .limit(1)
    )
    return rows[0][0] > 0 if rows else False
