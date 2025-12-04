"""Golden Standard JavaScript/TypeScript Async and Concurrency Analyzer."""

import sqlite3
from dataclasses import dataclass

from theauditor.indexer.schema import build_query
from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="async_concurrency_issues",
    category="node",
    target_extensions=[".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        ".pf/",
        ".auditor_venv/",
    ])


@dataclass(frozen=True)
class AsyncPatterns:
    """Configuration for JavaScript async/concurrency patterns."""

    ASYNC_FUNCTIONS = frozenset(
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

    PROMISE_METHODS = frozenset(
        [
            "Promise.all",
            "Promise.race",
            "Promise.allSettled",
            "Promise.any",
            "Promise.resolve",
            "Promise.reject",
            "then",
            "catch",
            "finally",
        ]
    )

    TIMER_FUNCTIONS = frozenset(
        [
            "setTimeout",
            "setInterval",
            "setImmediate",
            "clearTimeout",
            "clearInterval",
            "process.nextTick",
            "queueMicrotask",
        ]
    )

    WORKER_FUNCTIONS = frozenset(
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

    STREAM_FUNCTIONS = frozenset(
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

    SHARED_STATE = frozenset(
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
            "document",
            "SharedArrayBuffer",
            "Atomics",
        ]
    )

    WRITE_OPERATIONS = frozenset(
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

    CHECK_OPERATIONS = frozenset(
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

    COUNTER_PATTERNS = frozenset(
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
            "qty",
            "quantity",
        ]
    )

    SINGLETON_PATTERNS = frozenset(
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

    LOOP_KEYWORDS = frozenset(
        [
            "for",
            "while",
            "do",
            "forEach",
            "map",
            "reduce",
            "filter",
            "find",
            "some",
            "every",
            "loop",
        ]
    )

    CLEANUP_FUNCTIONS = frozenset(
        [
            "close",
            "destroy",
            "end",
            "terminate",
            "kill",
            "disconnect",
            "abort",
            "cancel",
            "unsubscribe",
            "removeListener",
            "removeAllListeners",
            "off",
            "removeEventListener",
            "clearInterval",
            "clearTimeout",
        ]
    )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect async and concurrency issues in JavaScript/TypeScript."""
    analyzer = AsyncConcurrencyAnalyzer(context)
    return analyzer.analyze()


class AsyncConcurrencyAnalyzer:
    """Main analyzer for JavaScript async and concurrency issues."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with context."""
        self.context = context
        self.patterns = AsyncPatterns()
        self.findings: list[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

    def analyze(self) -> list[StandardFinding]:
        """Run complete async/concurrency analysis."""
        if not self._is_javascript_project():
            return self.findings

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

            query = build_query(
                "files", ["path"], where="ext IN ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')"
            )
            cursor.execute(query)

            count = len(cursor.fetchall())
            conn.close()
            return count > 0

        except (sqlite3.Error, Exception):
            return False

    def _check_async_without_await(self) -> None:
        """Check for async operations called without await."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args",
                ["file", "line", "callee_function", "caller_function"],
                order_by="file, line",
            )
            cursor.execute(query)

            for file, line, callee, caller in cursor.fetchall():
                is_async_call = False
                for pattern in self.patterns.ASYNC_FUNCTIONS:
                    if pattern in callee.lower():
                        is_async_call = True
                        break

                if is_async_call:
                    symbol_query = build_query("symbols", ["name"], where="path = ? AND line = ?")
                    cursor.execute(symbol_query, (file, line))

                    has_await = False
                    for (name,) in cursor.fetchall():
                        if name == "await" or ".then" in name or ".catch" in name:
                            has_await = True
                            break

                    if not has_await and caller and "async" not in caller:
                        self.findings.append(
                            StandardFinding(
                                rule_name="async-without-await",
                                message=f"Async operation {callee} called without await",
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category="async",
                                confidence=Confidence.MEDIUM,
                                snippet=f"{callee}(...)",
                            )
                        )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_promise_no_catch(self) -> None:
        """Check for promise chains without error handling."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
            )
            cursor.execute(query)

            then_calls = []
            for file, line, callee in cursor.fetchall():
                if ".then" in callee:
                    then_calls.append((file, line, callee))

            for file, line, method in then_calls:
                error_query = build_query(
                    "function_call_args",
                    ["callee_function"],
                    where="file = ? AND line BETWEEN ? AND ?",
                )
                cursor.execute(error_query, (file, line, line + 5))

                has_error_handling = False
                for (error_func,) in cursor.fetchall():
                    if ".catch" in error_func or ".finally" in error_func:
                        has_error_handling = True
                        break

                if has_error_handling:
                    continue
                self.findings.append(
                    StandardFinding(
                        rule_name="promise-no-catch",
                        message="Promise chain without error handling",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="error-handling",
                        confidence=Confidence.HIGH,
                        snippet=method,
                    )
                )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_promise_all_no_catch(self) -> None:
        """Check for Promise.all without error handling."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args",
                ["file", "line", "callee_function"],
                where="callee_function IN ('Promise.all', 'Promise.allSettled', 'Promise.race')",
                order_by="file, line",
            )
            cursor.execute(query)

            promise_all_calls = list(cursor.fetchall())

            for file, line, _callee in promise_all_calls:
                error_query = build_query(
                    "function_call_args",
                    ["callee_function"],
                    where="file = ? AND line BETWEEN ? AND ?",
                )
                cursor.execute(error_query, (file, line, line + 5))

                has_catch = False
                for (error_func,) in cursor.fetchall():
                    if ".catch" in error_func:
                        has_catch = True
                        break

                if has_catch:
                    continue
                self.findings.append(
                    StandardFinding(
                        rule_name="promise-all-no-catch",
                        message="Promise.all without error handling",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="error-handling",
                        confidence=Confidence.HIGH,
                        snippet="Promise.all(...)",
                    )
                )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_parallel_writes(self) -> None:
        """Check for Promise.all with write operations."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args",
                ["file", "line", "callee_function", "argument_expr"],
                where="callee_function IN ('Promise.all', 'Promise.allSettled')",
                order_by="file, line",
            )
            cursor.execute(query)

            for file, line, _callee_function, args in cursor.fetchall():
                has_writes = False
                for write_op in self.patterns.WRITE_OPERATIONS:
                    if write_op in args.lower():
                        has_writes = True
                        break

                if has_writes:
                    self.findings.append(
                        StandardFinding(
                            rule_name="parallel-writes-no-sync",
                            message="Parallel write operations in Promise.all",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="concurrency",
                            confidence=Confidence.HIGH,
                            snippet=args[:100] if len(args) > 100 else args,
                        )
                    )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_shared_state_modifications(self) -> None:
        """Check for shared/global state modifications."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
            )
            cursor.execute(query)

            for file, line, target, _source in cursor.fetchall():
                is_shared = False
                for pattern in self.patterns.SHARED_STATE:
                    if pattern in target:
                        is_shared = True
                        break

                if is_shared:
                    self.findings.append(
                        StandardFinding(
                            rule_name="shared-state-no-lock",
                            message=f'Shared state "{target}" modified without synchronization',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category="concurrency",
                            confidence=Confidence.MEDIUM,
                            snippet=f"{target} = ...",
                        )
                    )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unprotected_counters(self) -> None:
        """Check for unprotected counter increments."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
            )
            cursor.execute(query)

            for file, line, target, expr in cursor.fetchall():
                if not ("++" in expr or "--" in expr or "+= 1" in expr or "-= 1" in expr):
                    continue

                is_counter = False
                for pattern in self.patterns.COUNTER_PATTERNS:
                    if pattern in target.lower():
                        is_counter = True
                        break

                if is_counter:
                    async_query = build_query(
                        "symbols", ["name"], where="path = ? AND line BETWEEN ? AND ?"
                    )
                    cursor.execute(async_query, (file, line - 10, line + 10))

                    in_async = False
                    for (name,) in cursor.fetchall():
                        if name in ("async", "Promise", "await"):
                            in_async = True
                            break

                    if in_async:
                        self.findings.append(
                            StandardFinding(
                                rule_name="unprotected-global-increment",
                                message=f'Counter "{target}" incremented without atomic operations',
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category="concurrency",
                                confidence=Confidence.MEDIUM,
                                snippet=expr,
                            )
                        )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_sleep_in_loops(self) -> None:
        """Check for setTimeout/setInterval in loops."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args",
                ["file", "line", "callee_function", "caller_function"],
                where="callee_function IN ('setTimeout', 'setInterval', 'sleep', 'delay')",
                order_by="file, line",
            )
            cursor.execute(query)

            for file, line, callee_function, caller_function in cursor.fetchall():
                if "loop" not in caller_function.lower():
                    continue
                self.findings.append(
                    StandardFinding(
                        rule_name="sleep-in-loop",
                        message=f"{callee_function} in loop causes performance issues",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="performance",
                        confidence=Confidence.MEDIUM,
                        snippet=callee_function,
                    )
                )

            query = build_query(
                "function_call_args",
                ["file", "line", "callee_function"],
                where="""callee_function IN ('setTimeout', 'setInterval')
                  AND EXISTS (
                      SELECT 1 FROM symbols s
                      WHERE s.path = file
                        AND s.line BETWEEN line - 5 AND line
                        AND s.name IN ('for', 'while', 'do')
                  )""",
                order_by="file, line",
            )
            cursor.execute(query)

            for file, line, func in cursor.fetchall():
                self.findings.append(
                    StandardFinding(
                        rule_name="sleep-in-loop",
                        message=f"{func} inside loop - performance anti-pattern",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="performance",
                        confidence=Confidence.HIGH,
                        snippet=func,
                    )
                )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_workers_not_terminated(self) -> None:
        """Check for workers/processes not properly terminated."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
            )
            cursor.execute(query)

            for file, line, func in cursor.fetchall():
                is_worker = False
                for pattern in self.patterns.WORKER_FUNCTIONS:
                    if pattern in func:
                        is_worker = True
                        break

                if is_worker:
                    cleanup_query = build_query(
                        "function_call_args",
                        ["callee_function"],
                        where="file = ? AND line > ? AND line < ?",
                    )
                    cursor.execute(cleanup_query, (file, line, line + 100))

                    has_cleanup = False
                    for (cleanup_func,) in cursor.fetchall():
                        if cleanup_func in ("terminate", "kill", "disconnect", "close"):
                            has_cleanup = True
                            break

                    if not has_cleanup:
                        self.findings.append(
                            StandardFinding(
                                rule_name="worker-no-terminate",
                                message=f"Worker created with {func} but not terminated",
                                file_path=file,
                                line=line,
                                severity=Severity.MEDIUM,
                                category="resource-management",
                                confidence=Confidence.MEDIUM,
                                snippet=func,
                            )
                        )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_streams_without_cleanup(self) -> None:
        """Check for streams without cleanup handlers."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
            )
            cursor.execute(query)

            for file, line, func in cursor.fetchall():
                is_stream = False
                for pattern in self.patterns.STREAM_FUNCTIONS:
                    if pattern in func:
                        is_stream = True
                        break

                if is_stream:
                    cleanup_query = build_query(
                        "function_call_args",
                        ["callee_function"],
                        where="file = ? AND line > ? AND line < ?",
                    )
                    cursor.execute(cleanup_query, (file, line, line + 50))

                    has_cleanup = False
                    for (cleanup_func,) in cursor.fetchall():
                        if (
                            ".close" in cleanup_func
                            or ".destroy" in cleanup_func
                            or ".end" in cleanup_func
                            or (".on" in cleanup_func and "error" in cleanup_func)
                        ):
                            has_cleanup = True
                            break

                    if not has_cleanup:
                        self.findings.append(
                            StandardFinding(
                                rule_name="stream-no-close",
                                message=f"Stream created with {func} without cleanup",
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category="resource-management",
                                confidence=Confidence.MEDIUM,
                                snippet=func,
                            )
                        )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _extract_base_object(self, callee_function: str) -> str:
        """Extract base object from function call."""
        if "." in callee_function:
            return callee_function.split(".")[0]
        return ""

    def _extract_operation_target(self, callee_function: str, argument_expr: str) -> str:
        """Extract operation target (object + first argument)."""
        base_obj = self._extract_base_object(callee_function)

        first_arg = ""
        if argument_expr:
            cleaned = argument_expr.strip("()")
            first_arg = cleaned.split(",")[0].strip() if "," in cleaned else cleaned.strip()

        if base_obj and first_arg:
            return f"{base_obj}:{first_arg}"
        elif base_obj:
            return base_obj
        elif first_arg:
            return first_arg
        return ""

    def _calculate_toctou_confidence(self, check_func: str, write_func: str, target: str) -> float:
        """Calculate confidence that this is a real TOCTOU vulnerability."""
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

    def _check_toctou_race_conditions(self) -> None:
        """Check for TOCTOU race conditions with object tracking."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args",
                ["file", "line", "callee_function", "argument_expr"],
                order_by="file, line",
            )
            cursor.execute(query)

            all_calls = cursor.fetchall()

            calls_by_file = {}
            for file, line, func, args in all_calls:
                if file not in calls_by_file:
                    calls_by_file[file] = []
                calls_by_file[file].append((line, func, args))

            for file, calls in calls_by_file.items():
                check_ops = {}
                write_ops = {}

                for line, func, args in calls:
                    target = self._extract_operation_target(func, args)
                    if not target:
                        continue

                    is_check = any(pattern in func for pattern in self.patterns.CHECK_OPERATIONS)
                    if is_check:
                        if target not in check_ops:
                            check_ops[target] = []
                        check_ops[target].append((line, func))

                    is_write = any(pattern in func for pattern in self.patterns.WRITE_OPERATIONS)
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
                                confidence = self._calculate_toctou_confidence(
                                    check_func, write_func, target
                                )

                                if confidence >= 0.7:
                                    severity = Severity.HIGH
                                elif confidence >= 0.5:
                                    severity = Severity.MEDIUM
                                else:
                                    severity = Severity.LOW

                                self.findings.append(
                                    StandardFinding(
                                        rule_name="check-then-act",
                                        message=f"Potential TOCTOU: {check_func} at line {check_line}, then {write_func} at line {write_line} (target: {target})",
                                        file_path=file,
                                        line=check_line,
                                        severity=severity,
                                        category="race-condition",
                                        confidence=confidence,
                                        snippet=f"{check_func} → {write_func} (target: {target})",
                                    )
                                )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_retry_without_backoff(self) -> None:
        """Check for retry logic without exponential backoff."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
            )
            cursor.execute(query)

            for file, line, var, expr in cursor.fetchall():
                var_lower = var.lower()
                if not ("retry" in var_lower or "attempt" in var_lower or "tries" in var_lower):
                    continue

                if (
                    "Math.pow" in expr
                    or "**" in expr
                    or "exponential" in expr
                    or "backoff" in expr
                    or "*=" in expr
                ):
                    continue
                self.findings.append(
                    StandardFinding(
                        rule_name="retry-without-backoff",
                        message="Retry logic without exponential backoff",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="performance",
                        confidence=Confidence.LOW,
                        snippet=expr[:100] if len(expr) > 100 else expr,
                    )
                )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_singleton_race_conditions(self) -> None:
        """Check for singleton patterns without synchronization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
            )
            cursor.execute(query)

            for file, line, var, source_expr in cursor.fetchall():
                if "new " not in source_expr:
                    continue

                is_singleton = False
                for pattern in self.patterns.SINGLETON_PATTERNS:
                    if pattern in var.lower():
                        is_singleton = True
                        break

                if is_singleton:
                    sync_query = build_query(
                        "symbols", ["name"], where="path = ? AND line BETWEEN ? AND ?"
                    )
                    cursor.execute(sync_query, (file, line - 5, line + 5))

                    has_sync = False
                    for (name,) in cursor.fetchall():
                        name_lower = name.lower()
                        if (
                            "lock" in name_lower
                            or "mutex" in name_lower
                            or "synchronized" in name_lower
                        ):
                            has_sync = True
                            break

                    if not has_sync:
                        self.findings.append(
                            StandardFinding(
                                rule_name="singleton-race",
                                message=f'Singleton "{var}" without synchronization',
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category="concurrency",
                                confidence=Confidence.LOW,
                                snippet=var,
                            )
                        )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_event_listener_leaks(self) -> None:
        """Check for event listeners that are never removed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
            )
            cursor.execute(query)

            listener_additions = []
            for file, line, callee in cursor.fetchall():
                if ".on" in callee or ".addEventListener" in callee or ".addListener" in callee:
                    listener_additions.append((file, line, callee))

            for file, line, func in listener_additions[:20]:
                removal_query = build_query(
                    "function_call_args", ["callee_function"], where="file = ?"
                )
                cursor.execute(removal_query, (file,))

                has_removal = False
                for (removal_func,) in cursor.fetchall():
                    if (
                        ".off" in removal_func
                        or ".removeEventListener" in removal_func
                        or ".removeListener" in removal_func
                    ):
                        has_removal = True
                        break

                if has_removal:
                    continue
                self.findings.append(
                    StandardFinding(
                        rule_name="event-listener-leak",
                        message=f"Event listener {func} never removed",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="memory-leak",
                        confidence=Confidence.LOW,
                        snippet=func,
                    )
                )

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_callback_hell(self) -> None:
        """Check for deeply nested callbacks (callback hell)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query(
                "function_call_args",
                ["file", "line", "callee_function", "argument_expr"],
                order_by="file, line",
            )
            cursor.execute(query)

            nested_callbacks = []
            for file, line, func, args in cursor.fetchall():
                if (
                    ("function" in args and args.count("function") >= 2)
                    or ("=>" in args and args.count("=>") >= 2)
                    or ("callback" in args and args.count("callback") >= 2)
                ):
                    nested_callbacks.append((file, line, func, args))

            for file, line, _func, args in nested_callbacks[:50]:
                nesting = max(args.lower().count("function"), args.count("=>"))

                if nesting >= 2:
                    self.findings.append(
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

            conn.close()

        except (sqlite3.Error, Exception):
            pass
