"""General Logic Analyzer - Database-First Approach.

Detects common logic and resource management issues including:
- Float/double arithmetic for money calculations (CWE-682)
- Timezone-naive datetime usage (CWE-20)
- Email validation via regex (CWE-20)
- Division without zero check (CWE-369)
- Resource leaks: files, connections, sockets, streams (CWE-404)
- Unclosed transactions (CWE-404)
- Percentage calculation errors (CWE-682)
- Async operations without error handling (CWE-248)
- Locks acquired but not released (CWE-667)
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
    name="general_logic_issues",
    category="logic",
    target_extensions=[".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "migrations/",
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        ".venv/",
        "venv/",
        "dist/",
        "build/",
        ".pf/",
        ".auditor_venv/",
    ],
    execution_scope="database",
    primary_table="assignments",
)


MONEY_TERMS = frozenset(
    [
        "price",
        "cost",
        "amount",
        "total",
        "balance",
        "payment",
        "fee",
        "money",
        "charge",
        "refund",
        "salary",
        "wage",
        "tax",
        "discount",
        "revenue",
    ]
)


FLOAT_FUNCTIONS = frozenset(
    ["parseFloat", "float", "Number.parseFloat", "toFixed", "toPrecision", "parseDouble"]
)


DATETIME_FUNCTIONS = frozenset(
    [
        "datetime.now",
        "datetime.today",
        "datetime.utcnow",
        "Date.now",
        "new Date",
        "Date",
        "Date.parse",
        "moment",
        "new moment",
        "dayjs",
    ]
)


REGEX_FUNCTIONS = frozenset(
    ["re.match", "re.search", "re.compile", "RegExp", "test", "match", "exec"]
)


FILE_OPERATIONS = frozenset(
    [
        "open",
        "fopen",
        "fs.open",
        "fs.createReadStream",
        "fs.createWriteStream",
        "createReadStream",
        "createWriteStream",
    ]
)


FILE_CLEANUP = frozenset(["close", "fclose", "end", "destroy", "finish"])


CONNECTION_CLEANUP = frozenset(["close", "disconnect", "end", "release", "destroy"])


TRANSACTION_FUNCTIONS = frozenset(
    [
        "begin",
        "beginTransaction",
        "begin_transaction",
        "startTransaction",
        "start_transaction",
        "START TRANSACTION",
    ]
)


TRANSACTION_END = frozenset(["commit", "rollback", "end", "abort", "COMMIT", "ROLLBACK"])


STREAM_FUNCTIONS = frozenset(
    [
        "createReadStream",
        "createWriteStream",
        "stream",
        "fs.createReadStream",
        "fs.createWriteStream",
        "Readable",
        "Writable",
        "Transform",
    ]
)


DATETIME_SOURCES = frozenset(
    [
        "datetime.now",
        "datetime.today",
        "datetime.utcnow",
        "Date.now",
        "new Date",
        "Date.parse",
        "time.time",
        "time.localtime",
        "time.gmtime",
    ]
)


RESOURCE_SINKS = frozenset(
    [
        "open",
        "createReadStream",
        "createWriteStream",
        "socket",
        "createSocket",
        "connect",
        "createConnection",
        "begin_transaction",
        "start_transaction",
        "beginTransaction",
        "acquire",
        "lock",
        "getLock",
    ]
)


MONEY_SINKS = frozenset(
    [
        "parseFloat",
        "float",
        "toFixed",
        "toPrecision",
        "price",
        "cost",
        "amount",
        "total",
        "balance",
        "payment",
        "fee",
        "money",
        "charge",
        "refund",
    ]
)


DIVISION_SINKS = frozenset(["divide", "div", "quotient", "average", "mean"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect common logic and resource management issues using indexed data."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_money_float_arithmetic(db))
        findings.extend(_check_money_float_conversion(db))
        findings.extend(_check_timezone_naive_datetime(db))
        findings.extend(_check_email_regex_validation(db))
        findings.extend(_check_divide_by_zero(db))
        findings.extend(_check_file_no_close(db))
        findings.extend(_check_connection_no_close(db))
        findings.extend(_check_transaction_no_end(db))
        findings.extend(_check_socket_no_close(db))
        findings.extend(_check_percentage_calc_error(db))
        findings.extend(_check_stream_no_cleanup(db))
        findings.extend(_check_async_no_error_handling(db))
        findings.extend(_check_lock_no_release(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_money_float_arithmetic(db: RuleDB) -> list[StandardFinding]:
    """Detect float/double arithmetic used for money calculations."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var_name, expr in rows:
        if not var_name or not expr:
            continue
        var_lower = var_name.lower()
        if not any(term in var_lower for term in MONEY_TERMS):
            continue

        if not (
            "/" in expr
            or "*" in expr
            or "parseFloat" in expr
            or "float(" in expr
            or ".toFixed" in expr
        ):
            continue

        findings.append(
            StandardFinding(
                rule_name="money-float-arithmetic",
                message=f"Using float/double for money calculations in {var_name} - precision loss risk",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="business-logic",
                confidence=Confidence.HIGH,
                snippet=expr[:100] if len(expr) > 100 else expr,
                cwe_id="CWE-682",
            )
        )

    return findings


def _check_money_float_conversion(db: RuleDB) -> list[StandardFinding]:
    """Detect float conversion functions used with money values."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, arg in rows:
        if not func or func not in FLOAT_FUNCTIONS:
            continue
        if not arg:
            continue
        arg_lower = arg.lower()
        if not any(money_term in arg_lower for money_term in MONEY_TERMS):
            continue

        findings.append(
            StandardFinding(
                rule_name="money-float-conversion",
                message=f"Converting money value to float using {func} - precision loss risk",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="business-logic",
                confidence=Confidence.HIGH,
                snippet=f"{func}({arg[:50]}...)" if len(arg) > 50 else f"{func}({arg})",
                cwe_id="CWE-682",
            )
        )

    return findings


def _check_timezone_naive_datetime(db: RuleDB) -> list[StandardFinding]:
    """Detect datetime usage without timezone awareness."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, datetime_func, args in rows:
        if not datetime_func or datetime_func not in DATETIME_FUNCTIONS:
            continue
        if not args:
            continue
        if "tz" in args or "timezone" in args or "UTC" in args:
            continue

        findings.append(
            StandardFinding(
                rule_name="timezone-naive-datetime",
                message=f"Using {datetime_func} without timezone awareness",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="datetime",
                confidence=Confidence.MEDIUM,
                snippet=f"{datetime_func}({args[:30]}...)"
                if len(args) > 30
                else f"{datetime_func}({args})",
                cwe_id="CWE-20",
            )
        )

    return findings


def _check_email_regex_validation(db: RuleDB) -> list[StandardFinding]:
    """Detect email validation using regex instead of proper libraries."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            "callee_function IN ('re.match', 're.search', 're.compile', 'RegExp', 'test', 'match')"
        )
        .order_by("file, line")
    )

    for file, line, _regex_func, pattern in rows:
        if not pattern or "@" not in pattern:
            continue

        pattern_lower = pattern.lower()
        if not ("email" in pattern_lower or "mail" in pattern_lower or "\\@" in pattern):
            continue

        findings.append(
            StandardFinding(
                rule_name="email-regex-validation",
                message="Using regex for email validation - use proper email validation library",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category="validation",
                confidence=Confidence.HIGH,
                snippet=pattern[:100] if len(pattern) > 100 else pattern,
                cwe_id="CWE-20",
            )
        )

    return findings


def _check_divide_by_zero(db: RuleDB) -> list[StandardFinding]:
    """Detect division operations without zero checks."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    division_operations = []
    for file, line, _target, expr in rows:
        if not expr or "/" not in expr:
            continue

        expr_lower = expr.lower()
        if not (
            "count" in expr_lower
            or "length" in expr_lower
            or "size" in expr_lower
            or ".length" in expr
            or ".size" in expr
            or ".count" in expr
        ):
            continue

        division_operations.append((file, line, expr))

    for file, line, expr in division_operations:
        check_rows = db.query(
            Q("assignments")
            .select("source_expr")
            .where("file = ? AND line BETWEEN ? AND ?", file, line - 5, line)
        )

        has_check = False
        for (check_expr,) in check_rows:
            if (
                "!= 0" in check_expr
                or "> 0" in check_expr
                or ("if" in check_expr and "!= 0" in check_expr)
                or ("if" in check_expr and "> 0" in check_expr)
            ):
                has_check = True
                break

        if not has_check:
            findings.append(
                StandardFinding(
                    rule_name="divide-by-zero-risk",
                    message="Division without zero check - potential divide by zero",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="error-handling",
                    confidence=Confidence.MEDIUM,
                    snippet=expr[:100] if len(expr) > 100 else expr,
                    cwe_id="CWE-369",
                )
            )

    return findings


def _check_file_no_close(db: RuleDB) -> list[StandardFinding]:
    """Detect file operations without proper close/cleanup."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function")
        .order_by("file, line")
    )

    file_opens = []
    for file, line, callee, caller in rows:
        if not callee:
            continue
        if callee in FILE_OPERATIONS:
            file_opens.append((file, line, callee, caller))

    for file, line, open_func, in_function in file_opens:
        cleanup_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND caller_function = ? AND line > ?", file, in_function, line)
        )

        has_cleanup = False
        for (cleanup_func,) in cleanup_rows:
            if cleanup_func in FILE_CLEANUP:
                has_cleanup = True
                break

        if has_cleanup:
            continue

        cfg_rows = db.query(
            Q("cfg_blocks")
            .select("id")
            .where(
                "file = ? AND block_type IN ('try', 'finally', 'with') AND ? BETWEEN start_line AND end_line",
                file,
                line,
            )
            .limit(1)
        )
        has_context_manager = len(cfg_rows) > 0

        if not has_context_manager:
            findings.append(
                StandardFinding(
                    rule_name="file-no-close",
                    message=f"File opened with {open_func} but not closed - resource leak",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="resource-management",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{open_func}(...) in {in_function}",
                    cwe_id="CWE-404",
                )
            )

    return findings


def _check_connection_no_close(db: RuleDB) -> list[StandardFinding]:
    """Detect database connections without explicit cleanup."""
    findings = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    connection_calls = []
    for file, line, callee in rows:
        if not callee:
            continue
        callee_lower = callee.lower()
        if (
            "connect" in callee_lower
            or "createconnection" in callee_lower
            or "getconnection" in callee_lower
        ) and "disconnect" not in callee_lower:
            connection_calls.append((file, line, callee))

    for file, line, connect_func in connection_calls:
        cleanup_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND line > ? AND line < ?", file, line, line + 50)
        )

        has_cleanup = False
        for (cleanup_func,) in cleanup_rows:
            cleanup_lower = cleanup_func.lower()
            if any(kw in cleanup_lower for kw in CONNECTION_CLEANUP):
                has_cleanup = True
                break

        if not has_cleanup:
            findings.append(
                StandardFinding(
                    rule_name="connection-no-close",
                    message=f"Database connection from {connect_func} without explicit cleanup",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="resource-management",
                    confidence=Confidence.MEDIUM,
                    snippet=connect_func,
                    cwe_id="CWE-404",
                )
            )

    return findings


def _check_transaction_no_end(db: RuleDB) -> list[StandardFinding]:
    """Detect transactions started without commit/rollback."""
    findings = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    transaction_starts = []
    for file, line, callee in rows:
        if not callee:
            continue
        if callee in TRANSACTION_FUNCTIONS:
            transaction_starts.append((file, line, callee))

    for file, line, trans_func in transaction_starts:
        end_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND line > ? AND line < ?", file, line, line + 100)
        )

        has_end = False
        for (end_func,) in end_rows:
            if end_func in TRANSACTION_END:
                has_end = True
                break

        if not has_end:
            findings.append(
                StandardFinding(
                    rule_name="transaction-no-end",
                    message=f"Transaction started with {trans_func} but no commit/rollback found",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="database",
                    confidence=Confidence.MEDIUM,
                    snippet=trans_func,
                    cwe_id="CWE-404",
                )
            )

    return findings


def _check_socket_no_close(db: RuleDB) -> list[StandardFinding]:
    """Detect sockets created without proper close."""
    findings = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    socket_calls = []
    for file, line, callee in rows:
        if not callee:
            continue
        callee_lower = callee.lower()
        if ("socket" in callee_lower or callee == "createSocket") and "close" not in callee_lower:
            socket_calls.append((file, line, callee))

    for file, line, socket_func in socket_calls:
        cleanup_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND line > ? AND line < ?", file, line, line + 50)
        )

        has_cleanup = False
        for (cleanup_func,) in cleanup_rows:
            cleanup_lower = cleanup_func.lower()
            if "close" in cleanup_lower or "destroy" in cleanup_lower or "end" in cleanup_lower:
                has_cleanup = True
                break

        if not has_cleanup:
            findings.append(
                StandardFinding(
                    rule_name="socket-no-close",
                    message=f"Socket created with {socket_func} but not properly closed",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="resource-management",
                    confidence=Confidence.MEDIUM,
                    snippet=socket_func,
                    cwe_id="CWE-404",
                )
            )

    return findings


def _check_percentage_calc_error(db: RuleDB) -> list[StandardFinding]:
    """Detect percentage calculation errors from missing parentheses."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, _target, expr in rows:
        if not expr:
            continue
        if not ("/ 100 *" in expr or "/100*" in expr or "/ 100.0 *" in expr):
            continue

        if "(/ 100)" in expr or "( / 100 )" in expr:
            continue

        findings.append(
            StandardFinding(
                rule_name="percentage-calc-error",
                message="Potential percentage calculation error - missing parentheses around division",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="calculation",
                confidence=Confidence.HIGH,
                snippet=expr[:100] if len(expr) > 100 else expr,
                cwe_id="CWE-682",
            )
        )

    return findings


def _check_stream_no_cleanup(db: RuleDB) -> list[StandardFinding]:
    """Detect streams created without proper cleanup handlers."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where(
            "callee_function IN ('createReadStream', 'createWriteStream', 'stream', 'fs.createReadStream', 'fs.createWriteStream')"
        )
        .order_by("file, line")
    )

    stream_calls = list(rows)

    for file, line, stream_func in stream_calls:
        cleanup_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND line > ? AND line < ?", file, line, line + 30)
        )

        has_cleanup = False
        for (cleanup_func,) in cleanup_rows:
            if cleanup_func in ("end", "destroy", "close", "finish") or (
                ".on" in cleanup_func and ("error" in cleanup_func or "close" in cleanup_func)
            ):
                has_cleanup = True
                break

        if not has_cleanup:
            findings.append(
                StandardFinding(
                    rule_name="stream-no-cleanup",
                    message=f"Stream created with {stream_func} without proper cleanup handlers",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="resource-management",
                    confidence=Confidence.MEDIUM,
                    snippet=stream_func,
                    cwe_id="CWE-404",
                )
            )

    return findings


def _check_async_no_error_handling(db: RuleDB) -> list[StandardFinding]:
    """Detect async operations without error handling."""
    findings = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    async_calls = []
    for file, line, callee in rows:
        if not callee:
            continue
        if ".then" in callee or callee == "await" or "Promise" in callee:
            async_calls.append((file, line, callee))

    for file, line, async_func in async_calls[:10]:
        error_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND line BETWEEN ? AND ?", file, line, line + 5)
        )

        has_error_handling = False
        for (error_func,) in error_rows:
            if ".catch" in error_func or error_func == "try":
                has_error_handling = True
                break

        if not has_error_handling:
            findings.append(
                StandardFinding(
                    rule_name="async-no-error-handling",
                    message="Async operation without error handling",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="error-handling",
                    confidence=Confidence.LOW,
                    snippet=async_func,
                    cwe_id="CWE-248",
                )
            )

    return findings


def _check_lock_no_release(db: RuleDB) -> list[StandardFinding]:
    """Detect locks acquired but not released."""
    findings = []

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    lock_calls = []
    for file, line, callee in rows:
        if not callee:
            continue
        callee_lower = callee.lower()
        if (
            ("lock" in callee_lower or "acquire" in callee_lower or "mutex" in callee_lower)
            and "unlock" not in callee_lower
            and "release" not in callee_lower
        ):
            lock_calls.append((file, line, callee))

    for file, line, lock_func in lock_calls:
        release_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND line > ? AND line < ?", file, line, line + 50)
        )

        has_release = False
        for (release_func,) in release_rows:
            release_lower = release_func.lower()
            if "unlock" in release_lower or "release" in release_lower:
                has_release = True
                break

        if not has_release:
            findings.append(
                StandardFinding(
                    rule_name="lock-no-release",
                    message=f"Lock acquired with {lock_func} but not released",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="concurrency",
                    confidence=Confidence.MEDIUM,
                    snippet=lock_func,
                    cwe_id="CWE-667",
                )
            )

    return findings


def register_taint_patterns(taint_registry):
    """Register logic-related patterns with the taint analysis registry."""
    for pattern in DATETIME_SOURCES:
        taint_registry.register_source(pattern, "datetime", "any")

    for pattern in RESOURCE_SINKS:
        taint_registry.register_sink(pattern, "resource", "any")

    for pattern in MONEY_SINKS:
        taint_registry.register_sink(pattern, "financial", "any")

    for pattern in DIVISION_SINKS:
        taint_registry.register_sink(pattern, "division", "any")
