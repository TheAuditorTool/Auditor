"""Performance Analyzer - Database-First Approach.

Detects performance anti-patterns and inefficiencies using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows golden standard patterns:
- Frozensets for O(1) pattern matching
- Direct database queries (fail-fast on missing tables)
- Schema contract compliance (v1.1+ - uses build_query())
- Proper confidence levels
"""

import sqlite3

from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    Confidence,
    RuleMetadata,
)
from theauditor.indexer.schema import build_query


METADATA = RuleMetadata(
    name="performance_issues",
    category="performance",
    target_extensions=[".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        ".venv/",
        "venv/",
        ".pf/",
        ".auditor_venv/",
    ],
    requires_jsx_pass=False,
)


DB_OPERATIONS = frozenset(
    [
        "query",
        "execute",
        "fetch",
        "fetchone",
        "fetchall",
        "fetchmany",
        "select",
        "insert",
        "update",
        "delete",
        "findAll",
        "findOne",
        "findByPk",
        "findOrCreate",
        "create",
        "bulkCreate",
        "bulkUpdate",
        "destroy",
        "findMany",
        "findFirst",
        "findUnique",
        "findUniqueOrThrow",
        "createMany",
        "updateMany",
        "deleteMany",
        "upsert",
        "find",
        "findOneBy",
        "findAndCount",
        "save",
        "remove",
        "find_one",
        "find_one_and_update",
        "insert_one",
        "update_one",
        "delete_one",
        "aggregate",
        "count_documents",
        "filter",
        "filter_by",
        "get",
        "all",
        "first",
        "one",
        "count",
        "exists",
        "scalar",
    ]
)


EXPENSIVE_OPS = frozenset(
    [
        "open",
        "read",
        "write",
        "readFile",
        "writeFile",
        "readFileSync",
        "writeFileSync",
        "createReadStream",
        "createWriteStream",
        "fetch",
        "axios",
        "request",
        "get",
        "post",
        "put",
        "delete",
        "http.get",
        "http.post",
        "https.get",
        "https.post",
        "compile",
        "re.compile",
        "RegExp",
        "new RegExp",
        "sleep",
        "time.sleep",
        "setTimeout",
        "setInterval",
        "hash",
        "encrypt",
        "decrypt",
        "bcrypt",
        "pbkdf2",
        "scrypt",
        "crypto.createHash",
        "crypto.createCipher",
        "crypto.pbkdf2",
    ]
)


SYNC_BLOCKERS = frozenset(
    [
        "readFileSync",
        "writeFileSync",
        "existsSync",
        "mkdirSync",
        "readdirSync",
        "statSync",
        "unlinkSync",
        "rmSync",
        "execSync",
        "spawnSync",
        "time.sleep",
        "requests.get",
        "requests.post",
    ]
)


STRING_CONCAT_OPS = frozenset(["+=", "+", "concat", "join", "append"])


MEMORY_OPS = frozenset(
    [
        "sort",
        "sorted",
        "reverse",
        "deepcopy",
        "clone",
        "JSON.parse",
        "JSON.stringify",
        "Buffer.from",
        "Buffer.alloc",
    ]
)


ARRAY_METHODS = frozenset(
    [
        "forEach",
        "map",
        "filter",
        "reduce",
        "some",
        "every",
        "find",
        "findIndex",
        "flatMap",
        "reduceRight",
    ]
)


ASYNC_INDICATORS = frozenset(
    [
        "async",
        "await",
        "promise",
        "then",
        "catch",
        "finally",
        "Promise.all",
        "Promise.race",
        "Promise.allSettled",
    ]
)


PROPERTY_CHAIN_PATTERNS = frozenset(
    [
        "req.body",
        "req.params",
        "req.query",
        "req.headers",
        "res.status",
        "res.send",
        "res.json",
        "res.render",
    ]
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect performance anti-patterns and inefficiencies.

    Detects:
    - Database queries in loops (N+1 problem)
    - Expensive operations in loops
    - Inefficient string concatenation
    - Synchronous I/O blocking event loop
    - Unbounded operations
    - Deep property access chains
    - Unoptimized taint flows

    Args:
        context: Standardized rule context with database path

    Returns:
        List of performance issues found
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        findings.extend(_find_queries_in_loops(cursor))

        findings.extend(_find_expensive_operations_in_loops(cursor))

        findings.extend(_find_inefficient_string_concat(cursor))

        findings.extend(_find_synchronous_io_patterns(cursor))

        findings.extend(_find_unbounded_operations(cursor))

        findings.extend(_find_deep_property_chains(cursor))

        findings.extend(_find_unoptimized_taint_flows(cursor))

        findings.extend(_find_repeated_expensive_calls(cursor))

        findings.extend(_find_large_object_operations(cursor))

    finally:
        conn.close()

    return findings


def _find_queries_in_loops(cursor) -> list[StandardFinding]:
    """Find database queries executed inside loops (N+1 problem)."""
    findings = []

    db_ops_list = list(DB_OPERATIONS)
    placeholders = ",".join("?" * len(db_ops_list))

    query = build_query(
        "cfg_blocks",
        ["file", "function_name", "start_line", "end_line", "block_type"],
        order_by="file, start_line",
    )
    cursor.execute(query)

    loops = []
    for file, function, start_line, end_line, block_type in cursor.fetchall():
        block_lower = block_type.lower()
        if block_type in ("loop", "for_loop", "while_loop", "do_while") or "loop" in block_lower:
            loops.append((file, function, start_line, end_line))

    for file, function, loop_start, loop_end in loops:
        cursor.execute(
            f"""
            SELECT line, callee_function, argument_expr
            FROM function_call_args
            WHERE file = ?
              AND line >= ?
              AND line <= ?
              AND callee_function IN ({placeholders})
            ORDER BY line
        """,
            [file, loop_start, loop_end] + db_ops_list,
        )

        for line, operation, args in cursor.fetchall():
            nested_query = build_query(
                "cfg_blocks", ["block_type"], where="file = ? AND start_line < ? AND end_line > ?"
            )
            cursor.execute(nested_query, (file, loop_start, loop_end))

            nested_count = 0
            for (block_type,) in cursor.fetchall():
                if "loop" in block_type.lower():
                    nested_count += 1
            severity = Severity.CRITICAL if nested_count > 0 else Severity.HIGH

            findings.append(
                StandardFinding(
                    rule_name="perf-query-in-loop",
                    message=f'Database query "{operation}" in {"nested " if nested_count else ""}loop - N+1 problem',
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1050",
                )
            )

    array_methods_list = list(ARRAY_METHODS)
    array_placeholders = ",".join("?" * len(array_methods_list))

    cursor.execute(
        f"""
        SELECT f1.file, f1.line, f1.callee_function, f1.caller_function
        FROM function_call_args f1
        WHERE f1.callee_function IN ({array_placeholders})
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.caller_function = f1.caller_function
                AND f2.callee_function IN ({placeholders})
                AND ABS(f2.line - f1.line) <= 10
          )
        ORDER BY f1.file, f1.line
    """,
        array_methods_list + db_ops_list,
    )

    for file, line, method, _ in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="perf-query-in-array-method",
                message=f"Database operations in array.{method}() creates implicit loop",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="performance",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-1050",
            )
        )

    return findings


def _find_expensive_operations_in_loops(cursor) -> list[StandardFinding]:
    """Find expensive operations that should be moved outside loops."""
    findings = []

    query = build_query("cfg_blocks", ["file", "start_line", "end_line", "block_type"])
    cursor.execute(query)

    loops = []
    for file, start_line, end_line, block_type in cursor.fetchall():
        if "loop" in block_type.lower():
            loops.append((file, start_line, end_line))

    for file, loop_start, loop_end in loops:
        expensive_ops_list = list(EXPENSIVE_OPS)
        placeholders = ",".join("?" * len(expensive_ops_list))

        query = build_query(
            "function_call_args",
            ["line", "callee_function", "argument_expr"],
            where=f"""file = ?
              AND line >= ?
              AND line <= ?
              AND callee_function IN ({placeholders})""",
            order_by="line",
        )
        cursor.execute(query, [file, loop_start, loop_end] + expensive_ops_list)

        for line, operation, args in cursor.fetchall():
            if operation in ["sleep", "time.sleep", "execSync", "spawnSync"]:
                severity = Severity.CRITICAL
                message = f'Blocking operation "{operation}" in loop severely degrades performance'
            elif operation in ["fetch", "axios", "request", "http.get", "https.get"]:
                severity = Severity.CRITICAL
                message = f'HTTP request "{operation}" in loop causes severe performance issues'
            elif operation in ["readFile", "writeFile", "open"]:
                severity = Severity.HIGH
                message = f'File I/O operation "{operation}" in loop is expensive'
            elif operation in ["bcrypt", "pbkdf2", "scrypt"]:
                severity = Severity.CRITICAL
                message = f'CPU-intensive crypto "{operation}" in loop blocks execution'
            else:
                severity = Severity.HIGH
                message = f'Expensive operation "{operation}" in loop'

            findings.append(
                StandardFinding(
                    rule_name="perf-expensive-in-loop",
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1050",
                )
            )

    return findings


def _find_inefficient_string_concat(cursor) -> list[StandardFinding]:
    """Find inefficient string concatenation in loops (O(n²) complexity)."""
    findings = []

    query = build_query(
        "cfg_blocks", ["file", "start_line", "end_line", "function_name", "block_type"]
    )
    cursor.execute(query)

    loops = []
    for file, start_line, end_line, function, block_type in cursor.fetchall():
        if "loop" in block_type.lower():
            loops.append((file, start_line, end_line, function))

    for file, loop_start, loop_end, function in loops:
        query = build_query(
            "assignments",
            ["line", "target_var", "source_expr"],
            where="file = ? AND line >= ? AND line <= ?",
            order_by="line",
        )
        cursor.execute(query, (file, loop_start, loop_end))

        string_var_patterns = frozenset(["str", "text", "result", "output", "html", "message"])

        for line, var_name, expr in cursor.fetchall():
            if not expr or not any(op in expr for op in ["+=", "+", "concat"]):
                continue

            var_lower = var_name.lower()

            is_string_var = any(pattern in var_lower for pattern in string_var_patterns)
            has_string_literal = any(quote in expr for quote in ['"', "'", "`"])

            if not (is_string_var or has_string_literal):
                continue

            if any(op in expr for op in ["+", "+=", "concat"]):
                findings.append(
                    StandardFinding(
                        rule_name="perf-string-concat-loop",
                        message=f'String concatenation "{var_name} += ..." in loop has O(n²) complexity',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="performance",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1050",
                    )
                )

    return findings


def _find_synchronous_io_patterns(cursor) -> list[StandardFinding]:
    """Find synchronous I/O operations that block the event loop."""
    findings = []

    sync_ops_list = list(SYNC_BLOCKERS)
    placeholders = ",".join("?" * len(sync_ops_list))

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "caller_function", "argument_expr"],
        where=f"callee_function IN ({placeholders})",
        order_by="file, line",
    )
    cursor.execute(query, sync_ops_list)

    for file, line, operation, caller, args in cursor.fetchall():
        is_async_context = False
        confidence = Confidence.MEDIUM

        if caller:
            caller_lower = caller.lower()
            if any(indicator in caller_lower for indicator in ["async", "await", "promise"]):
                is_async_context = True
                confidence = Confidence.HIGH

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM api_endpoints
            WHERE file = ? AND ? BETWEEN line - 50 AND line + 50
        """,
            (file, line),
        )

        if cursor.fetchone()[0] > 0:
            is_async_context = True
            confidence = Confidence.HIGH

        severity = Severity.CRITICAL if is_async_context else Severity.HIGH

        findings.append(
            StandardFinding(
                rule_name="perf-sync-io",
                message=f'Synchronous operation "{operation}" blocks event loop',
                file_path=file,
                line=line,
                severity=severity,
                category="performance",
                confidence=confidence,
                cwe_id="CWE-1050",
            )
        )

    return findings


def _find_unbounded_operations(cursor) -> list[StandardFinding]:
    """Find operations without proper limits that could cause memory issues."""
    findings = []

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        where="callee_function IN ('find', 'findMany', 'findAll', 'select', 'query', 'all')",
        order_by="file, line",
    )
    cursor.execute(query)

    pagination_keywords = frozenset(["limit", "take", "first", "pagesize", "max"])

    for file, line, operation, args in cursor.fetchall():
        if operation in ["findOne", "findUnique", "first", "get"]:
            continue

        if args:
            args_lower = args.lower()
            if any(keyword in args_lower for keyword in pagination_keywords):
                continue

        findings.append(
            StandardFinding(
                rule_name="perf-unbounded-query",
                message=f'Query "{operation}" without limit could return excessive data',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="performance",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-770",
            )
        )

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        where="callee_function IN ('readFile', 'readFileSync', 'read')",
    )
    cursor.execute(query)

    large_file_extensions = frozenset([".log", ".csv", ".json", ".xml", ".sql", ".txt"])

    for file, line, operation, file_arg in cursor.fetchall():
        if not file_arg:
            continue
        file_arg_lower = file_arg.lower()
        if not any(ext in file_arg_lower for ext in large_file_extensions):
            continue
        findings.append(
            StandardFinding(
                rule_name="perf-large-file-read",
                message=f"Reading potentially large file entirely into memory",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="performance",
                confidence=Confidence.LOW,
                cwe_id="CWE-770",
            )
        )

    memory_ops_list = list(MEMORY_OPS)
    placeholders = ",".join("?" * len(memory_ops_list))

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function"],
        where=f"""callee_function IN ({placeholders})
          AND line IN (
              SELECT line FROM function_call_args
              WHERE callee_function IN ('find', 'findMany', 'findAll', 'query')
                AND file = function_call_args.file
                AND ABS(line - function_call_args.line) <= 5
          )""",
        order_by="file, line",
    )
    cursor.execute(query, memory_ops_list)

    for file, line, operation in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="perf-memory-intensive",
                message=f'Memory-intensive operation "{operation}" on potentially large dataset',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="performance",
                confidence=Confidence.LOW,
                cwe_id="CWE-770",
            )
        )

    return findings


def _find_deep_property_chains(cursor) -> list[StandardFinding]:
    """Find deep property access chains that impact performance."""
    findings = []

    query = build_query(
        "symbols",
        ["path", "name", "line"],
        where="type = 'property' AND LENGTH(name) - LENGTH(REPLACE(name, '.', '')) >= 3",
        order_by="path, line",
    )
    cursor.execute(query)

    for file, prop_chain, line in cursor.fetchall():
        depth = prop_chain.count(".")

        if depth >= 4:
            severity = Severity.HIGH
            message = f'Very deep property chain "{prop_chain}" ({depth} levels)'
        elif depth == 3:
            severity = Severity.MEDIUM
            message = f'Deep property chain "{prop_chain}" impacts performance'
        else:
            continue

        findings.append(
            StandardFinding(
                rule_name="perf-deep-property-chain",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="performance",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-1050",
            )
        )

    cursor.execute("""
        SELECT path, name, COUNT(*) as count, MIN(line) as first_line
        FROM symbols
        WHERE type = 'property'
          AND LENGTH(name) - LENGTH(REPLACE(name, '.', '')) >= 2
        GROUP BY path, name
        HAVING count > 3
        ORDER BY count DESC
    """)

    for file, prop_chain, count, line in cursor.fetchall():
        if count > 5:
            findings.append(
                StandardFinding(
                    rule_name="perf-repeated-property-access",
                    message=f'Property "{prop_chain}" accessed {count} times - cache it',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1050",
                )
            )

    return findings


def _find_unoptimized_taint_flows(cursor) -> list[StandardFinding]:
    """Find unoptimized taint flows (e.g., req.body → res.send without validation)."""
    findings = []

    cursor.execute("""
        SELECT DISTINCT s1.path, s1.line, s1.name as source, s2.name as sink
        FROM symbols s1
        JOIN symbols s2 ON s1.path = s2.path
        WHERE ABS(s1.line - s2.line) <= 5
          AND s1.line < s2.line
        ORDER BY s1.path, s1.line
    """)

    taint_flows = []
    for file, line, source, sink in cursor.fetchall():
        if source.startswith("req.") and sink.startswith("res."):
            taint_flows.append((file, line, source, sink))

    for file, line, source, sink in taint_flows:
        if "req.body" in source and "res.send" in sink:
            severity = Severity.CRITICAL
            message = "Direct flow from req.body to res.send - potential XSS"
            cwe = "CWE-79"
        elif "req.query" in source and "res.render" in sink:
            severity = Severity.HIGH
            message = "Query parameter passed to render - potential template injection"
            cwe = "CWE-94"
        elif "req.params" in source and any(db in sink for db in ["query", "find", "execute"]):
            severity = Severity.CRITICAL
            message = "Request parameter in database query - potential SQL injection"
            cwe = "CWE-89"
        else:
            continue

        findings.append(
            StandardFinding(
                rule_name="perf-unoptimized-taint",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="performance-security",
                confidence=Confidence.MEDIUM,
                cwe_id=cwe,
            )
        )

    return findings


def _find_repeated_expensive_calls(cursor) -> list[StandardFinding]:
    """Find expensive functions called multiple times in same context."""
    findings = []

    expensive_ops_list = list(EXPENSIVE_OPS)
    placeholders = ",".join("?" * len(expensive_ops_list))

    cursor.execute(
        f"""
        SELECT file, caller_function, callee_function, COUNT(*) as count, MIN(line) as first_line
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
          AND caller_function IS NOT NULL
        GROUP BY file, caller_function, callee_function
        HAVING count > 2
        ORDER BY count DESC
    """,
        expensive_ops_list,
    )

    for file, caller, callee, count, line in cursor.fetchall():
        if count > 5:
            severity = Severity.HIGH
            message = f'Expensive operation "{callee}" called {count} times in {caller}'
        elif count > 3:
            severity = Severity.MEDIUM
            message = f'Operation "{callee}" repeated {count} times in {caller}'
        else:
            continue

        findings.append(
            StandardFinding(
                rule_name="perf-repeated-expensive-call",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="performance",
                confidence=Confidence.HIGH,
                cwe_id="CWE-1050",
            )
        )

    return findings


def _find_large_object_operations(cursor) -> list[StandardFinding]:
    """Find operations on large objects that could cause performance issues."""
    findings = []

    query = build_query(
        "assignments",
        ["file", "line", "target_var", "source_expr"],
        where="LENGTH(source_expr) > 500",
        order_by="file, line",
    )
    cursor.execute(query)

    for file, line, var_name, expr in cursor.fetchall():
        if not expr or not any(json_op in expr for json_op in ["JSON.parse", "JSON.stringify"]):
            continue
        expr_len = len(expr)

        if expr_len > 2000:
            severity = Severity.HIGH
            message = "Very large JSON operation detected"
        elif expr_len > 1000:
            severity = Severity.MEDIUM
            message = "Large JSON operation may impact performance"
        else:
            continue

        findings.append(
            StandardFinding(
                rule_name="perf-large-json-operation",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="performance",
                confidence=Confidence.LOW,
                cwe_id="CWE-770",
            )
        )

    query = build_query(
        "assignments",
        ["file", "line", "target_var", "source_expr"],
        where="LENGTH(source_expr) > 1000",
        order_by="LENGTH(source_expr) DESC",
        limit=10,
    )
    cursor.execute(query)

    for file, line, var_name, expr in cursor.fetchall():
        if not expr or not ("{" in expr or "[" in expr):
            continue
        findings.append(
            StandardFinding(
                rule_name="perf-large-object-copy",
                message=f"Large object assignment to {var_name} may impact memory",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category="performance",
                confidence=Confidence.LOW,
                cwe_id="CWE-770",
            )
        )

    return findings


def register_taint_patterns(taint_registry):
    """Register performance-related taint patterns.

    This function is called by the orchestrator to register
    performance-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """

    for pattern in DB_OPERATIONS:
        taint_registry.register_sink(pattern, "database", "all")

    for pattern in EXPENSIVE_OPS:
        taint_registry.register_sink(pattern, "expensive_op", "all")

    PERF_SOURCES = frozenset(
        [
            "req.body",
            "req.query",
            "req.params",
            "process.argv",
            "process.env",
            "fs.readFile",
            "fs.readdir",
        ]
    )

    for pattern in PERF_SOURCES:
        taint_registry.register_source(pattern, "user_input", "all")
