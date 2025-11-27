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

from theauditor.indexer.schema import build_query
from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

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
    requires_jsx_pass=False,
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


DIVISION_RISK_TERMS = frozenset(
    ["count", "length", "size", "total", "sum", "num", "items", "records", "rows", "elements"]
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


CONNECTION_FUNCTIONS = frozenset(
    ["connect", "createConnection", "getConnection", "createPool", "getPool", "createClient"]
)


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


SOCKET_FUNCTIONS = frozenset(
    ["socket", "Socket", "createSocket", "createServer", "net.createConnection", "net.createServer"]
)


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


STREAM_HANDLERS = frozenset(
    ["end", "destroy", "close", "finish", "error", ".on", ".once", ".addListener"]
)


ASYNC_PATTERNS = frozenset([".then", "await", "Promise", "async", ".catch"])


LOCK_FUNCTIONS = frozenset(
    ["lock", "Lock", "acquire", "mutex", "Mutex", "semaphore", "Semaphore", "RLock"]
)


LOCK_RELEASE = frozenset(["unlock", "release", "free", "signal"])


# Taint analysis pattern constants - datetime sources
DATETIME_SOURCES = frozenset([
    "datetime.now",
    "datetime.today",
    "datetime.utcnow",
    "Date.now",
    "new Date",
    "Date.parse",
    "time.time",
    "time.localtime",
    "time.gmtime",
])


# Taint analysis pattern constants - resource sinks
RESOURCE_SINKS = frozenset([
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
])


# Taint analysis pattern constants - money/financial sinks
MONEY_SINKS = frozenset([
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
])


# Taint analysis pattern constants - division sinks
DIVISION_SINKS = frozenset(["divide", "div", "quotient", "average", "mean"])


def find_logic_issues(context: StandardRuleContext) -> list[StandardFinding]:
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
        money_terms_list = list(MONEY_TERMS)
        money_placeholders = ",".join(["?" for _ in MONEY_TERMS])

        query = build_query(
            "assignments",
            ["file", "line", "target_var", "source_expr"],
            where=f"target_var IN ({money_placeholders})",
            order_by="file, line",
        )
        cursor.execute(query, money_terms_list)

        for file, line, var_name, expr in cursor.fetchall():
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

        float_funcs_list = list(FLOAT_FUNCTIONS)
        float_placeholders = ",".join("?" * len(float_funcs_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where=f"callee_function IN ({float_placeholders})",
            order_by="file, line",
        )
        cursor.execute(query, float_funcs_list)

        for file, line, func, arg in cursor.fetchall():
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

        datetime_funcs_list = list(DATETIME_FUNCTIONS)
        datetime_placeholders = ",".join("?" * len(datetime_funcs_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where=f"callee_function IN ({datetime_placeholders})",
            order_by="file, line",
        )
        cursor.execute(query, datetime_funcs_list)

        for file, line, datetime_func, args in cursor.fetchall():
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

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where="callee_function IN ('re.match', 're.search', 're.compile', 'RegExp', 'test', 'match')",
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, _regex_func, pattern in cursor.fetchall():
            if "@" not in pattern:
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

        query = build_query(
            "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
        )
        cursor.execute(query)

        division_operations = []
        for file, line, _target, expr in cursor.fetchall():
            if "/" not in expr:
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
            assignments_query = build_query(
                "assignments", ["source_expr"], where="file = ? AND line BETWEEN ? AND ?"
            )
            cursor.execute(assignments_query, (file, line - 5, line))

            has_check = False
            for (check_expr,) in cursor.fetchall():
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

        file_ops_list = list(FILE_OPERATIONS)
        file_cleanup_list = list(FILE_CLEANUP)
        ops_placeholders = ",".join("?" * len(file_ops_list))
        cleanup_placeholders = ",".join("?" * len(file_cleanup_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "caller_function"],
            where=f"""callee_function IN ({ops_placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND fca2.caller_function = function_call_args.caller_function
                    AND fca2.callee_function IN ({cleanup_placeholders})
                    AND fca2.line > function_call_args.line
              )""",
            order_by="file, line",
        )
        cursor.execute(query, file_ops_list + file_cleanup_list)

        file_operations = cursor.fetchall()

        for file, line, open_func, in_function in file_operations:
            has_context_manager = False

            cfg_query = build_query(
                "cfg_blocks",
                ["id"],
                where="""file = ?
                  AND block_type IN ('try', 'finally', 'with')
                  AND ? BETWEEN start_line AND end_line""",
                limit=1,
            )
            cursor.execute(cfg_query, (file, line))
            has_context_manager = cursor.fetchone() is not None

            if not has_context_manager:
                symbols_query = build_query(
                    "symbols",
                    ["name"],
                    where="""path = ?
                      AND line BETWEEN ? AND ?
                      AND name = '__enter__'""",
                    limit=1,
                )
                cursor.execute(symbols_query, (file, line - 5, line + 5))
                has_context_manager = cursor.fetchone() is not None

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

        query = build_query(
            "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
        )
        cursor.execute(query)

        connection_calls = []
        for file, line, callee in cursor.fetchall():
            callee_lower = callee.lower()

            if (
                "connect" in callee_lower
                or "createconnection" in callee_lower
                or "getconnection" in callee_lower
            ) and "disconnect" not in callee_lower:
                connection_calls.append((file, line, callee))

        for file, line, connect_func in connection_calls:
            cleanup_query = build_query(
                "function_call_args",
                ["callee_function"],
                where="file = ? AND line > ? AND line < ?",
            )
            cursor.execute(cleanup_query, (file, line, line + 50))

            has_cleanup = False
            for (cleanup_func,) in cursor.fetchall():
                cleanup_lower = cleanup_func.lower()
                if (
                    "close" in cleanup_lower
                    or "disconnect" in cleanup_lower
                    or "end" in cleanup_lower
                    or "release" in cleanup_lower
                ):
                    has_cleanup = True
                    break

            if has_cleanup:
                continue
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

        trans_funcs_list = list(TRANSACTION_FUNCTIONS)
        trans_end_list = list(TRANSACTION_END)
        trans_placeholders = ",".join("?" * len(trans_funcs_list))
        end_placeholders = ",".join("?" * len(trans_end_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function"],
            where=f"""callee_function IN ({trans_placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args AS fca2
                  WHERE fca2.file = function_call_args.file
                    AND fca2.callee_function IN ({end_placeholders})
                    AND fca2.line > function_call_args.line
                    AND fca2.line < function_call_args.line + 100
              )""",
            order_by="file, line",
        )
        cursor.execute(query, trans_funcs_list + trans_end_list)

        for file, line, trans_func in cursor.fetchall():
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

        query = build_query(
            "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
        )
        cursor.execute(query)

        socket_calls = []
        for file, line, callee in cursor.fetchall():
            callee_lower = callee.lower()

            if (
                "socket" in callee_lower or callee == "createSocket"
            ) and "close" not in callee_lower:
                socket_calls.append((file, line, callee))

        for file, line, socket_func in socket_calls:
            cleanup_query = build_query(
                "function_call_args",
                ["callee_function"],
                where="file = ? AND line > ? AND line < ?",
            )
            cursor.execute(cleanup_query, (file, line, line + 50))

            has_cleanup = False
            for (cleanup_func,) in cursor.fetchall():
                cleanup_lower = cleanup_func.lower()
                if "close" in cleanup_lower or "destroy" in cleanup_lower or "end" in cleanup_lower:
                    has_cleanup = True
                    break

            if has_cleanup:
                continue
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

        query = build_query(
            "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
        )
        cursor.execute(query)

        for file, line, _target, expr in cursor.fetchall():
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

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function"],
            where="callee_function IN ('createReadStream', 'createWriteStream', 'stream', 'fs.createReadStream', 'fs.createWriteStream')",
            order_by="file, line",
        )
        cursor.execute(query)

        stream_calls = list(cursor.fetchall())

        for file, line, stream_func in stream_calls:
            cleanup_query = build_query(
                "function_call_args",
                ["callee_function"],
                where="file = ? AND line > ? AND line < ?",
            )
            cursor.execute(cleanup_query, (file, line, line + 30))

            has_cleanup = False
            for (cleanup_func,) in cursor.fetchall():
                if (
                    cleanup_func in ("end", "destroy", "close", "finish")
                    or ".on" in cleanup_func
                    and ("error" in cleanup_func or "close" in cleanup_func)
                ):
                    has_cleanup = True
                    break

            if has_cleanup:
                continue
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

        query = build_query(
            "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
        )
        cursor.execute(query)

        async_calls = []
        for file, line, callee in cursor.fetchall():
            if ".then" in callee or callee == "await" or "Promise" in callee:
                async_calls.append((file, line, callee))

        for file, line, async_func in async_calls[:10]:
            error_query = build_query(
                "function_call_args", ["callee_function"], where="file = ? AND line BETWEEN ? AND ?"
            )
            cursor.execute(error_query, (file, line, line + 5))

            has_error_handling = False
            for (error_func,) in cursor.fetchall():
                if ".catch" in error_func or error_func == "try":
                    has_error_handling = True
                    break

            if has_error_handling:
                continue
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

        query = build_query(
            "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
        )
        cursor.execute(query)

        lock_calls = []
        for file, line, callee in cursor.fetchall():
            callee_lower = callee.lower()

            if (
                ("lock" in callee_lower or "acquire" in callee_lower or "mutex" in callee_lower)
                and "unlock" not in callee_lower
                and "release" not in callee_lower
            ):
                lock_calls.append((file, line, callee))

        for file, line, lock_func in lock_calls:
            release_query = build_query(
                "function_call_args",
                ["callee_function"],
                where="file = ? AND line > ? AND line < ?",
            )
            cursor.execute(release_query, (file, line, line + 50))

            has_release = False
            for (release_func,) in cursor.fetchall():
                release_lower = release_func.lower()
                if "unlock" in release_lower or "release" in release_lower:
                    has_release = True
                    break

            if has_release:
                continue
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

    finally:
        conn.close()

    return findings


def register_taint_patterns(taint_registry):
    """Register logic-related patterns with the taint analysis registry.

    Args:
        taint_registry: TaintRegistry instance
    """
    for pattern in DATETIME_SOURCES:
        taint_registry.register_source(pattern, "datetime", "any")

    for pattern in RESOURCE_SINKS:
        taint_registry.register_sink(pattern, "resource", "any")

    for pattern in MONEY_SINKS:
        taint_registry.register_sink(pattern, "financial", "any")

    for pattern in DIVISION_SINKS:
        taint_registry.register_sink(pattern, "division", "any")
