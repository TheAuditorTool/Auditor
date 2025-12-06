"""Performance Analyzer - Database-First Approach.

Detects performance anti-patterns:
- N+1 queries (database operations in loops)
- Synchronous I/O blocking event loop
- Unbounded queries without limits
- String concatenation in loops (O(n^2))
- Deep property chains
- Memory-intensive operations on large datasets

Schema Contract Compliance: v2.0 (Fidelity Layer - Q class + RuleDB)
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
    execution_scope="database",
    primary_table="function_call_args",
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


STRING_VAR_PATTERNS = frozenset(["str", "text", "result", "output", "html", "message"])


PAGINATION_KEYWORDS = frozenset(["limit", "take", "first", "pagesize", "max"])


LARGE_FILE_EXTENSIONS = frozenset([".log", ".csv", ".json", ".xml", ".sql", ".txt"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect performance anti-patterns and inefficiencies."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        findings.extend(_find_queries_in_loops(db))
        findings.extend(_find_expensive_operations_in_loops(db))
        findings.extend(_find_inefficient_string_concat(db))
        findings.extend(_find_synchronous_io_patterns(db))
        findings.extend(_find_unbounded_operations(db))
        findings.extend(_find_deep_property_chains(db))
        findings.extend(_find_repeated_expensive_calls(db))
        findings.extend(_find_large_object_operations(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _find_queries_in_loops(db: RuleDB) -> list[StandardFinding]:
    """Find database queries executed inside loops (N+1 problem)."""
    findings = []

    rows = db.query(
        Q("cfg_blocks")
        .select("file", "function_name", "start_line", "end_line", "block_type")
        .order_by("file, start_line")
    )

    loops = []
    for file, function, start_line, end_line, block_type in rows:
        block_lower = block_type.lower()
        if block_type in ("loop", "for_loop", "while_loop", "do_while") or "loop" in block_lower:
            loops.append((file, function, start_line, end_line))

    for file, _function, loop_start, loop_end in loops:
        call_rows = db.query(
            Q("function_call_args")
            .select("line", "callee_function", "argument_expr")
            .where("file = ?", file)
            .where("line >= ?", loop_start)
            .where("line <= ?", loop_end)
            .order_by("line")
        )

        for line, operation, _args in call_rows:
            if operation not in DB_OPERATIONS:
                continue

            nested_rows = db.query(
                Q("cfg_blocks")
                .select("block_type")
                .where("file = ?", file)
                .where("start_line < ?", loop_start)
                .where("end_line > ?", loop_end)
            )

            nested_count = sum(1 for (bt,) in nested_rows if "loop" in bt.lower())
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

    array_call_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function")
        .order_by("file, line")
    )

    array_method_calls = []
    db_op_calls = []
    for file, line, callee, caller in array_call_rows:
        if callee in ARRAY_METHODS:
            array_method_calls.append((file, line, callee, caller))
        if callee in DB_OPERATIONS:
            db_op_calls.append((file, line, callee, caller))

    for file, line, method, caller in array_method_calls:
        for db_file, db_line, _db_op, db_caller in db_op_calls:
            if file == db_file and caller == db_caller and abs(db_line - line) <= 10:
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
                break

    return findings


def _find_expensive_operations_in_loops(db: RuleDB) -> list[StandardFinding]:
    """Find expensive operations that should be moved outside loops."""
    findings = []

    rows = db.query(Q("cfg_blocks").select("file", "start_line", "end_line", "block_type"))

    loops = []
    for file, start_line, end_line, block_type in rows:
        if "loop" in block_type.lower():
            loops.append((file, start_line, end_line))

    for file, loop_start, loop_end in loops:
        call_rows = db.query(
            Q("function_call_args")
            .select("line", "callee_function", "argument_expr")
            .where("file = ?", file)
            .where("line >= ?", loop_start)
            .where("line <= ?", loop_end)
            .order_by("line")
        )

        for line, operation, _args in call_rows:
            if operation not in EXPENSIVE_OPS:
                continue

            if operation in ("sleep", "time.sleep", "execSync", "spawnSync"):
                severity = Severity.CRITICAL
                message = f'Blocking operation "{operation}" in loop severely degrades performance'
            elif operation in ("fetch", "axios", "request", "http.get", "https.get"):
                severity = Severity.CRITICAL
                message = f'HTTP request "{operation}" in loop causes severe performance issues'
            elif operation in ("readFile", "writeFile", "open"):
                severity = Severity.HIGH
                message = f'File I/O operation "{operation}" in loop is expensive'
            elif operation in ("bcrypt", "pbkdf2", "scrypt"):
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


def _find_inefficient_string_concat(db: RuleDB) -> list[StandardFinding]:
    """Find inefficient string concatenation in loops (O(n^2) complexity)."""
    findings = []

    rows = db.query(
        Q("cfg_blocks").select("file", "start_line", "end_line", "function_name", "block_type")
    )

    loops = []
    for file, start_line, end_line, function, block_type in rows:
        if "loop" in block_type.lower():
            loops.append((file, start_line, end_line, function))

    for file, loop_start, loop_end, _function in loops:
        assign_rows = db.query(
            Q("assignments")
            .select("line", "target_var", "source_expr")
            .where("file = ?", file)
            .where("line >= ?", loop_start)
            .where("line <= ?", loop_end)
            .order_by("line")
        )

        for line, var_name, expr in assign_rows:
            if not expr or not any(op in expr for op in ("+=", "+", "concat")):
                continue

            var_lower = var_name.lower()

            is_string_var = any(pattern in var_lower for pattern in STRING_VAR_PATTERNS)
            has_string_literal = any(quote in expr for quote in ('"', "'", "`"))

            if not (is_string_var or has_string_literal):
                continue

            if any(op in expr for op in ("+", "+=", "concat")):
                findings.append(
                    StandardFinding(
                        rule_name="perf-string-concat-loop",
                        message=f'String concatenation "{var_name} += ..." in loop has O(n^2) complexity',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="performance",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1050",
                    )
                )

    return findings


def _find_synchronous_io_patterns(db: RuleDB) -> list[StandardFinding]:
    """Find synchronous I/O operations that block the event loop."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function", "argument_expr")
        .order_by("file, line")
    )

    endpoint_rows = db.query(Q("api_endpoints").select("file", "line"))
    endpoint_locations = {(f, ln) for f, ln in endpoint_rows}

    for file, line, operation, caller, _args in rows:
        if operation not in SYNC_BLOCKERS:
            continue

        is_async_context = False
        confidence = Confidence.MEDIUM

        if caller:
            caller_lower = caller.lower()
            if any(indicator in caller_lower for indicator in ("async", "await", "promise")):
                is_async_context = True
                confidence = Confidence.HIGH

        for ep_file, ep_line in endpoint_locations:
            if file == ep_file and abs(line - ep_line) <= 50:
                is_async_context = True
                confidence = Confidence.HIGH
                break

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


def _find_unbounded_operations(db: RuleDB) -> list[StandardFinding]:
    """Find operations without proper limits that could cause memory issues."""
    findings = []

    unbounded_ops = ("find", "findMany", "findAll", "select", "query", "all")
    single_result_ops = ("findOne", "findUnique", "first", "get")

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, operation, args in rows:
        if operation not in unbounded_ops:
            continue
        if operation in single_result_ops:
            continue

        if args:
            args_lower = args.lower()
            if any(keyword in args_lower for keyword in PAGINATION_KEYWORDS):
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

    file_read_ops = ("readFile", "readFileSync", "read")
    for file, line, operation, file_arg in rows:
        if operation not in file_read_ops:
            continue
        if not file_arg:
            continue
        file_arg_lower = file_arg.lower()
        if not any(ext in file_arg_lower for ext in LARGE_FILE_EXTENSIONS):
            continue
        findings.append(
            StandardFinding(
                rule_name="perf-large-file-read",
                message="Reading potentially large file entirely into memory",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="performance",
                confidence=Confidence.LOW,
                cwe_id="CWE-770",
            )
        )

    memory_op_locs = []
    query_op_locs = []
    query_ops = ("find", "findMany", "findAll", "query")

    for file, line, operation, _args in rows:
        if operation in MEMORY_OPS:
            memory_op_locs.append((file, line, operation))
        if operation in query_ops:
            query_op_locs.append((file, line))

    for mem_file, mem_line, mem_op in memory_op_locs:
        for q_file, q_line in query_op_locs:
            if mem_file == q_file and abs(mem_line - q_line) <= 5:
                findings.append(
                    StandardFinding(
                        rule_name="perf-memory-intensive",
                        message=f'Memory-intensive operation "{mem_op}" on potentially large dataset',
                        file_path=mem_file,
                        line=mem_line,
                        severity=Severity.MEDIUM,
                        category="performance",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-770",
                    )
                )
                break

    return findings


def _find_deep_property_chains(db: RuleDB) -> list[StandardFinding]:
    """Find deep property access chains that impact performance."""
    findings = []

    rows = db.query(
        Q("symbols")
        .select("path", "name", "line")
        .where("type = ?", "property")
        .order_by("path, line")
    )

    for file, prop_chain, line in rows:
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

    property_counts: dict[tuple[str, str], tuple[int, int]] = {}
    for file, prop_chain, line in rows:
        depth = prop_chain.count(".")
        if depth < 2:
            continue
        key = (file, prop_chain)
        if key not in property_counts:
            property_counts[key] = (0, line)
        count, first_line = property_counts[key]
        property_counts[key] = (count + 1, first_line)

    for (file, prop_chain), (count, line) in property_counts.items():
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


def _find_repeated_expensive_calls(db: RuleDB) -> list[StandardFinding]:
    """Find expensive functions called multiple times in same context."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "caller_function", "callee_function", "line")
        .where("caller_function IS NOT NULL")
    )

    call_counts: dict[tuple[str, str, str], tuple[int, int]] = {}
    for file, caller, callee, line in rows:
        if callee not in EXPENSIVE_OPS:
            continue
        key = (file, caller, callee)
        if key not in call_counts:
            call_counts[key] = (0, line)
        count, first_line = call_counts[key]
        call_counts[key] = (count + 1, first_line)

    for (file, caller, callee), (count, line) in call_counts.items():
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


def _find_large_object_operations(db: RuleDB) -> list[StandardFinding]:
    """Find operations on large objects that could cause performance issues."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    large_expr_candidates = []
    for file, line, var_name, expr in rows:
        if not expr:
            continue
        expr_len = len(expr)

        if expr_len > 500 and any(json_op in expr for json_op in ("JSON.parse", "JSON.stringify")):
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

        if expr_len > 1000:
            large_expr_candidates.append((file, line, var_name, expr, expr_len))

    large_expr_candidates.sort(key=lambda x: x[4], reverse=True)
    for file, line, var_name, expr, _expr_len in large_expr_candidates[:10]:
        if "{" not in expr and "[" not in expr:
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
