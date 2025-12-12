"""JavaScript/TypeScript async and concurrency analyzer.

Detects:
- Async/await misuse (missing await, unhandled promises)
- Race conditions (TOCTOU, unprotected shared state)
- Resource leaks (unclosed streams, workers, event listeners)
- Performance anti-patterns (callback hell, sleep in loops)

CWE-362: Concurrent Execution using Shared Resource with Improper Synchronization
CWE-367: Time-of-check Time-of-use (TOCTOU) Race Condition
CWE-772: Missing Release of Resource after Effective Lifetime
"""

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
    name="async_concurrency_issues",
    category="node",
    target_extensions=[".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "spec/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        ".pf/",
        ".auditor_venv/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)


ASYNC_FUNCTIONS: frozenset[str] = frozenset(
    [
        "async",
        "await",
        "Promise",
        "then",
        "catch",
        "finally",
        "fetch",
        "axios",
        "ajax",
        "request",
        "http.get",
        "https.get",
    ]
)


PROMISE_METHODS: frozenset[str] = frozenset(
    [
        "Promise.all",
        "Promise.race",
        "Promise.allSettled",
        "Promise.any",
        "Promise.resolve",
        "Promise.reject",
    ]
)


TIMER_FUNCTIONS: frozenset[str] = frozenset(
    [
        "setTimeout",
        "setInterval",
        "setImmediate",
        "process.nextTick",
        "queueMicrotask",
    ]
)


WORKER_FUNCTIONS: frozenset[str] = frozenset(
    [
        "Worker",
        "SharedWorker",
        "ServiceWorker",
        "fork",
        "spawn",
        "exec",
        "execFile",
        "cluster.fork",
        "child_process",
    ]
)


# Synchronous process functions that block until completion - no worker to terminate
SYNC_PROCESS_FUNCTIONS: frozenset[str] = frozenset(
    [
        "execSync",
        "execFileSync",
        "spawnSync",
    ]
)


STREAM_FUNCTIONS: frozenset[str] = frozenset(
    [
        "createReadStream",
        "createWriteStream",
        "pipe",
        "pipeline",
        "stream.Readable",
        "stream.Writable",
        "fs.watch",
        "fs.watchFile",
    ]
)


SHARED_STATE: frozenset[str] = frozenset(
    [
        "global",
        "window",
        "globalThis",
        "process.env",
        "process",
        "module.exports",
        "exports",
        "self",
        "localStorage",
        "sessionStorage",
        "SharedArrayBuffer",
        "Atomics",
    ]
)


WRITE_OPERATIONS: frozenset[str] = frozenset(
    [
        "save",
        "update",
        "insert",
        "delete",
        "write",
        "create",
        "put",
        "post",
        "patch",
        "remove",
        "set",
        "add",
        "push",
    ]
)


CHECK_OPERATIONS: frozenset[str] = frozenset(
    [
        "exists",
        "has",
        "includes",
        "contains",
        "indexOf",
        "hasOwnProperty",
        "in",
        "get",
        "find",
        "some",
        "every",
    ]
)


COUNTER_PATTERNS: frozenset[str] = frozenset(
    [
        "count",
        "counter",
        "total",
        "sum",
        "index",
        "idx",
        "num",
        "amount",
        "size",
        "length",
    ]
)


SINGLETON_PATTERNS: frozenset[str] = frozenset(
    [
        "instance",
        "singleton",
        "_instance",
        "_singleton",
        "sharedInstance",
        "defaultInstance",
        "globalInstance",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect async and concurrency issues in JavaScript/TypeScript.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_async_without_await(db))
        findings.extend(_check_promise_no_catch(db))
        findings.extend(_check_promise_all_no_catch(db))
        findings.extend(_check_parallel_writes(db))
        findings.extend(_check_shared_state_modifications(db))
        findings.extend(_check_unprotected_counters(db))
        findings.extend(_check_sleep_in_loops(db))
        findings.extend(_check_workers_not_terminated(db))
        findings.extend(_check_streams_without_cleanup(db))
        findings.extend(_check_toctou_race_conditions(db))
        findings.extend(_check_event_listener_leaks(db))
        findings.extend(_check_callback_hell(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_async_without_await(db: RuleDB) -> list[StandardFinding]:
    """Check for async operations called without await.

    Fixed: Expands search window to line +/- 2 for multiline formatting.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for missing await
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function")
        .order_by("file, line")
    )

    for file, line, callee, caller in rows:
        if not callee:
            continue

        is_async_call = any(pattern in callee.lower() for pattern in ASYNC_FUNCTIONS)
        if not is_async_call:
            continue

        symbol_rows = db.query(
            Q("symbols")
            .select("name")
            .where("path = ?", file)
            .where("line BETWEEN ? AND ?", line - 1, line + 2)
        )

        has_await = any(
            name == "await" or ".then" in name or ".catch" in name for (name,) in symbol_rows
        )

        if not has_await and caller and "async" not in caller.lower():
            findings.append(
                StandardFinding(
                    rule_name="async-without-await",
                    message=f"Async operation {callee} called without await",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="async",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{callee}(...)",
                    cwe_id="CWE-362",
                )
            )

    return findings


def _check_promise_no_catch(db: RuleDB) -> list[StandardFinding]:
    """Check for promise chains without error handling.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for unhandled promises
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    then_calls = [(file, line, callee) for file, line, callee in rows if ".then" in callee]

    for file, line, method in then_calls:
        error_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", line, line + 5)
        )

        has_error_handling = any(
            ".catch" in error_func or ".finally" in error_func for (error_func,) in error_rows
        )

        if has_error_handling:
            continue

        findings.append(
            StandardFinding(
                rule_name="promise-no-catch",
                message="Promise chain without error handling",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="error-handling",
                confidence=Confidence.HIGH,
                snippet=method,
                cwe_id="CWE-755",
            )
        )

    return findings


def _check_promise_all_no_catch(db: RuleDB) -> list[StandardFinding]:
    """Check for Promise.all without error handling.

    Fixed: Also checks for surrounding try/catch blocks (async/await pattern).

    Args:
        db: RuleDB instance

    Returns:
        List of findings for unhandled Promise.all
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("callee_function IN (?, ?, ?)", "Promise.all", "Promise.allSettled", "Promise.race")
        .order_by("file, line")
    )

    for file, line, callee in rows:
        error_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", line, line + 5)
        )

        has_chained_catch = any(".catch" in error_func for (error_func,) in error_rows)
        if has_chained_catch:
            continue

        try_catch_rows = db.query(
            Q("symbols")
            .select("name")
            .where("path = ?", file)
            .where("line BETWEEN ? AND ?", line - 5, line + 10)
            .where("name = ?", "catch")
            .limit(1)
        )

        has_try_catch = len(try_catch_rows) > 0
        if has_try_catch:
            continue

        findings.append(
            StandardFinding(
                rule_name="promise-all-no-catch",
                message=f"{callee} without error handling (no .catch() or try/catch)",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="error-handling",
                confidence=Confidence.HIGH,
                snippet=f"{callee}(...)",
                cwe_id="CWE-755",
            )
        )

    return findings


def _check_parallel_writes(db: RuleDB) -> list[StandardFinding]:
    """Check for Promise.all with write operations (race condition risk).

    Args:
        db: RuleDB instance

    Returns:
        List of findings for parallel writes
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?)", "Promise.all", "Promise.allSettled")
        .order_by("file, line")
    )

    for file, line, _callee, args in rows:
        if not args:
            continue

        has_writes = any(write_op in args.lower() for write_op in WRITE_OPERATIONS)

        if has_writes:
            findings.append(
                StandardFinding(
                    rule_name="parallel-writes-race",
                    message="Parallel write operations in Promise.all may cause race conditions",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="concurrency",
                    confidence=Confidence.HIGH,
                    snippet=args[:100] if len(args) > 100 else args,
                    cwe_id="CWE-362",
                )
            )

    return findings


def _check_shared_state_modifications(db: RuleDB) -> list[StandardFinding]:
    """Check for shared/global state modifications without synchronization.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for unsafe shared state access
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target, _source in rows:
        if not target:
            continue

        is_shared = any(pattern in target for pattern in SHARED_STATE)

        if is_shared:
            findings.append(
                StandardFinding(
                    rule_name="shared-state-unsafe",
                    message=f'Shared state "{target}" modified without synchronization',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="concurrency",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{target} = ...",
                    cwe_id="CWE-362",
                )
            )

    return findings


def _check_unprotected_counters(db: RuleDB) -> list[StandardFinding]:
    """Check for counter increments in async context without atomic operations.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for unprotected counters
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target, expr in rows:
        if not expr:
            continue

        if not ("++" in expr or "--" in expr or "+= 1" in expr or "-= 1" in expr):
            continue

        is_counter = any(pattern in target.lower() for pattern in COUNTER_PATTERNS)
        if not is_counter:
            continue

        async_rows = db.query(
            Q("symbols")
            .select("name")
            .where("path = ?", file)
            .where("line BETWEEN ? AND ?", line - 10, line + 10)
        )

        in_async = any(name in ("async", "Promise", "await") for (name,) in async_rows)

        if in_async:
            findings.append(
                StandardFinding(
                    rule_name="unprotected-counter",
                    message=f'Counter "{target}" incremented in async context without atomic operations',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="concurrency",
                    confidence=Confidence.MEDIUM,
                    snippet=expr,
                    cwe_id="CWE-362",
                )
            )

    return findings


def _check_sleep_in_loops(db: RuleDB) -> list[StandardFinding]:
    """Check for setTimeout/setInterval in loops.

    Fixed: Filters out test directories and intentional polling (delay > 1000ms).

    Args:
        db: RuleDB instance

    Returns:
        List of findings for sleep in loop anti-pattern
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function", "argument_expr")
        .where("callee_function IN (?, ?, ?, ?)", "setTimeout", "setInterval", "sleep", "delay")
        .order_by("file, line")
    )

    for file, line, callee, caller, args in rows:
        if any(
            test_dir in file for test_dir in ["/test", "/__tests__/", "/spec/", ".test.", ".spec."]
        ):
            continue

        is_in_loop = caller and any(
            loop_kw in caller.lower()
            for loop_kw in ["loop", "for", "while", "each", "map", "reduce"]
        )

        if not is_in_loop:
            loop_rows = db.query(
                Q("symbols")
                .select("name")
                .where("path = ?", file)
                .where("line BETWEEN ? AND ?", line - 5, line)
                .where("name IN (?, ?, ?)", "for", "while", "do")
                .limit(1)
            )
            is_in_loop = len(loop_rows) > 0

        if not is_in_loop:
            continue

        if args:
            import re

            delay_match = re.search(r"(\d{4,})", args)
            if delay_match:
                continue

        findings.append(
            StandardFinding(
                rule_name="sleep-in-loop",
                message=f"{callee} in loop causes performance issues",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="performance",
                confidence=Confidence.MEDIUM,
                snippet=callee,
                cwe_id="CWE-400",
            )
        )

    return findings


def _check_workers_not_terminated(db: RuleDB) -> list[StandardFinding]:
    """Check for workers/processes not properly terminated.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for unterminated workers
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    for file, line, func in rows:
        # Skip synchronous functions - they block until completion, no worker to terminate
        is_sync = any(sync_func in func for sync_func in SYNC_PROCESS_FUNCTIONS)
        if is_sync:
            continue

        is_worker = any(pattern in func for pattern in WORKER_FUNCTIONS)
        if not is_worker:
            continue

        cleanup_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("line > ?", line)
            .where("line < ?", line + 100)
        )

        has_cleanup = any(
            cleanup_func in ("terminate", "kill", "disconnect", "close")
            for (cleanup_func,) in cleanup_rows
        )

        if not has_cleanup:
            findings.append(
                StandardFinding(
                    rule_name="worker-not-terminated",
                    message=f"Worker created with {func} but not terminated",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="resource-management",
                    confidence=Confidence.MEDIUM,
                    snippet=func,
                    cwe_id="CWE-772",
                )
            )

    return findings


def _check_streams_without_cleanup(db: RuleDB) -> list[StandardFinding]:
    """Check for streams without cleanup handlers.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for unclosed streams
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    for file, line, func in rows:
        is_stream = any(pattern in func for pattern in STREAM_FUNCTIONS)
        if not is_stream:
            continue

        cleanup_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("line > ?", line)
            .where("line < ?", line + 50)
        )

        has_cleanup = any(
            ".close" in cleanup_func
            or ".destroy" in cleanup_func
            or ".end" in cleanup_func
            or (".on" in cleanup_func and "error" in cleanup_func)
            for (cleanup_func,) in cleanup_rows
        )

        if not has_cleanup:
            findings.append(
                StandardFinding(
                    rule_name="stream-not-closed",
                    message=f"Stream created with {func} without cleanup handlers",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="resource-management",
                    confidence=Confidence.MEDIUM,
                    snippet=func,
                    cwe_id="CWE-772",
                )
            )

    return findings


def _check_toctou_race_conditions(db: RuleDB) -> list[StandardFinding]:
    """Check for Time-of-check Time-of-use (TOCTOU) race conditions.

    Detects patterns like: exists(file) then read(file) without locking.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for TOCTOU vulnerabilities
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    all_calls = list(rows)

    calls_by_file: dict[str, list[tuple[int, str, str]]] = {}
    for file, line, func, args in all_calls:
        if file not in calls_by_file:
            calls_by_file[file] = []
        calls_by_file[file].append((line, func, args or ""))

    for file, calls in calls_by_file.items():
        check_ops: dict[str, list[tuple[int, str]]] = {}
        write_ops: dict[str, list[tuple[int, str]]] = {}

        for line, func, args in calls:
            target = _extract_operation_target(func, args)
            if not target:
                continue

            is_check = any(pattern in func for pattern in CHECK_OPERATIONS)
            if is_check:
                if target not in check_ops:
                    check_ops[target] = []
                check_ops[target].append((line, func))

            is_write = any(pattern in func for pattern in WRITE_OPERATIONS)
            if is_write:
                if target not in write_ops:
                    write_ops[target] = []
                write_ops[target].append((line, func))

        for target, checks in check_ops.items():
            if target not in write_ops:
                continue

            writes = write_ops[target]

            for check_line, check_func in checks:
                for write_line, write_func in writes:
                    if 1 <= write_line - check_line <= 10:
                        confidence = _calculate_toctou_confidence(check_func, write_func, target)

                        if confidence >= 0.7:
                            severity = Severity.HIGH
                        elif confidence >= 0.5:
                            severity = Severity.MEDIUM
                        else:
                            severity = Severity.LOW

                        findings.append(
                            StandardFinding(
                                rule_name="toctou-race",
                                message=f"TOCTOU: {check_func} at line {check_line}, then {write_func} at line {write_line}",
                                file_path=file,
                                line=check_line,
                                severity=severity,
                                category="race-condition",
                                confidence=confidence,
                                snippet=f"{check_func} -> {write_func} (target: {target})",
                                cwe_id="CWE-367",
                            )
                        )

    return findings


def _extract_operation_target(callee: str, args: str) -> str:
    """Extract operation target from function call for TOCTOU matching.

    Args:
        callee: Function being called
        args: Arguments to the function

    Returns:
        Target identifier for matching check/write operations
    """

    base_obj = callee.split(".")[0] if "." in callee else ""

    first_arg = ""
    if args:
        cleaned = args.strip("()")
        first_arg = cleaned.split(",")[0].strip() if "," in cleaned else cleaned.strip()

    if base_obj and first_arg:
        return f"{base_obj}:{first_arg}"
    elif base_obj:
        return base_obj
    elif first_arg:
        return first_arg
    return ""


def _calculate_toctou_confidence(check_func: str, write_func: str, target: str) -> float:
    """Calculate confidence that this is a real TOCTOU vulnerability.

    Args:
        check_func: The check function name
        write_func: The write function name
        target: The operation target

    Returns:
        Confidence score between 0.0 and 1.0
    """
    confidence = 0.5

    if "fs." in check_func or "fs." in write_func:
        confidence += 0.2

    if ":" in target:
        confidence += 0.15

    known_patterns = [
        ("exists", "read"),
        ("exists", "write"),
        ("exists", "delete"),
        ("has", "get"),
        ("includes", "remove"),
    ]

    for check_pattern, write_pattern in known_patterns:
        if check_pattern in check_func.lower() and write_pattern in write_func.lower():
            confidence += 0.15
            break

    generic_ops = ["save", "update", "create"]
    if any(op in write_func.lower() for op in generic_ops):
        confidence -= 0.1

    return max(0.0, min(1.0, confidence))


def _check_event_listener_leaks(db: RuleDB) -> list[StandardFinding]:
    """Check for event listeners that are never removed.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for potential memory leaks
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    listener_additions = [
        (file, line, callee)
        for file, line, callee in rows
        if ".on" in callee or ".addEventListener" in callee or ".addListener" in callee
    ]

    for file, line, func in listener_additions[:20]:
        removal_rows = db.query(
            Q("function_call_args").select("callee_function").where("file = ?", file)
        )

        has_removal = any(
            ".off" in removal_func
            or ".removeEventListener" in removal_func
            or ".removeListener" in removal_func
            or ".removeAllListeners" in removal_func
            for (removal_func,) in removal_rows
        )

        if has_removal:
            continue

        findings.append(
            StandardFinding(
                rule_name="event-listener-leak",
                message=f"Event listener {func} may never be removed",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="memory-leak",
                confidence=Confidence.LOW,
                snippet=func,
                cwe_id="CWE-772",
            )
        )

    return findings


def _check_callback_hell(db: RuleDB) -> list[StandardFinding]:
    """Check for deeply nested callbacks (callback hell).

    Args:
        db: RuleDB instance

    Returns:
        List of findings for callback hell anti-pattern
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, _func, args in rows:
        if not args:
            continue

        function_count = args.lower().count("function")
        arrow_count = args.count("=>")
        nesting = max(function_count, arrow_count)

        if nesting >= 2:
            findings.append(
                StandardFinding(
                    rule_name="callback-hell",
                    message=f"Deeply nested callbacks detected (depth: {nesting})",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM if nesting == 2 else Severity.HIGH,
                    category="code-quality",
                    confidence=Confidence.MEDIUM,
                    snippet=args[:100] if len(args) > 100 else args,
                )
            )

    return findings
