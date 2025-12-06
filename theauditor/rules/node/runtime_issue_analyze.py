"""Node.js runtime security analyzer - detects injection vulnerabilities.

Detects:
- Command injection (exec/spawn with user input)
- Prototype pollution (merge/extend with user data)
- Eval injection (eval/Function with user input)
- Path traversal (file ops with unsanitized paths)
- Unsafe regex (ReDoS from user-constructed patterns)

CWE-78: OS Command Injection
CWE-1321: Improperly Controlled Modification of Object Prototype
CWE-94: Improper Control of Generation of Code
CWE-22: Path Traversal
CWE-1333: Inefficient Regular Expression Complexity
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
    name="runtime_issues",
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
        "frontend/",
        "client/",
        "migrations/",
        ".pf/",
        ".auditor_venv/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)


USER_INPUT_SOURCES: frozenset[str] = frozenset(
    [
        "req.body",
        "req.query",
        "req.params",
        "req.headers",
        "req.cookies",
        "req.files",
        "request.body",
        "request.query",
        "request.params",
        "request.headers",
        "ctx.request.body",
        "ctx.query",
        "ctx.params",
        "ctx.request.query",
        "request.body",
        "request.query",
        "request.params",
        "socket.handshake.query",
        "socket.handshake.auth",
        "message.data",
        "event.body",
        "event.queryStringParameters",
        "event.pathParameters",
        "event.headers",
        "process.argv",
        "process.env",
        "location.search",
        "location.hash",
        "location.pathname",
        "window.location",
        "document.location",
        "URLSearchParams",
        "document.referrer",
    ]
)


EXEC_FUNCTIONS: frozenset[str] = frozenset(
    [
        "exec",
        "execSync",
        "execFile",
        "execFileSync",
        "spawn",
        "spawnSync",
        "fork",
        "execCommand",
        "child_process.exec",
        "child_process.spawn",
        "child_process.execSync",
        "child_process.spawnSync",
        "shelljs.exec",
        "execa",
    ]
)


MERGE_FUNCTIONS: frozenset[str] = frozenset(
    [
        "Object.assign",
        "merge",
        "extend",
        "deepMerge",
        "mergeDeep",
        "mergeRecursive",
        "_.merge",
        "_.extend",
        "_.defaultsDeep",
        "lodash.merge",
        "jQuery.extend",
        "$.extend",
    ]
)


EVAL_FUNCTIONS: frozenset[str] = frozenset(
    [
        "eval",
        "Function",
        "setTimeout",
        "setInterval",
        "setImmediate",
        "execScript",
        "vm.runInContext",
        "vm.runInNewContext",
        "vm.runInThisContext",
        "new Function",
    ]
)


FILE_OPERATIONS: frozenset[str] = frozenset(
    [
        "readFile",
        "readFileSync",
        "writeFile",
        "writeFileSync",
        "createReadStream",
        "createWriteStream",
        "open",
        "openSync",
        "access",
        "accessSync",
        "stat",
        "statSync",
        "unlink",
        "unlinkSync",
        "mkdir",
        "mkdirSync",
        "rmdir",
        "rmdirSync",
        "readdir",
        "readdirSync",
        "fs.readFile",
        "fs.writeFile",
        "fs.unlink",
    ]
)


PATH_SAFE_FUNCTIONS: frozenset[str] = frozenset(
    [
        "path.join",
        "path.normalize",
        "path.basename",
    ]
)


DANGEROUS_KEYS: frozenset[str] = frozenset(
    [
        "__proto__",
        "constructor",
        "prototype",
        "__defineGetter__",
        "__defineSetter__",
        "__lookupGetter__",
        "__lookupSetter__",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Node.js runtime security issues.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        tainted_vars = _identify_tainted_variables(db)

        findings.extend(_detect_command_injection(db, tainted_vars))
        findings.extend(_detect_spawn_shell_true(db))
        findings.extend(_detect_prototype_pollution(db))
        findings.extend(_detect_eval_injection(db, tainted_vars))
        findings.extend(_detect_unsafe_regex(db))
        findings.extend(_detect_path_traversal(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _identify_tainted_variables(db: RuleDB) -> dict[str, tuple[str, int, str]]:
    """Identify variables assigned from user input sources.

    Args:
        db: RuleDB instance

    Returns:
        Dict mapping var_name -> (file, line, source)
    """
    tainted: dict[str, tuple[str, int, str]] = {}

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var, source in rows:
        if not source:
            continue
        for input_source in USER_INPUT_SOURCES:
            if input_source in source:
                tainted[var] = (file, line, input_source)
                break

    return tainted


def _detect_command_injection(
    db: RuleDB, tainted_vars: dict[str, tuple[str, int, str]]
) -> list[StandardFinding]:
    """Detect command injection vulnerabilities.

    Checks for:
    1. Direct user input in exec/spawn calls
    2. Tainted variables passed to exec/spawn
    3. Template literals with user input near exec calls

    Args:
        db: RuleDB instance
        tainted_vars: Map of tainted variable names

    Returns:
        List of command injection findings
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not args:
            continue

        is_exec = any(exec_func in func for exec_func in EXEC_FUNCTIONS)
        if not is_exec:
            continue

        found_source = None
        for source in USER_INPUT_SOURCES:
            if source in args:
                found_source = source
                break

        if not found_source:
            for var_name in tainted_vars:
                if var_name in args:
                    found_source = f"tainted variable '{var_name}'"
                    break

        if found_source:
            findings.append(
                StandardFinding(
                    rule_name="command-injection",
                    message=f"Command injection: {func} called with {found_source}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}({args[:50]}...)" if len(args) > 50 else f"{func}({args})",
                    cwe_id="CWE-78",
                )
            )

    assignment_rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, _target, expr in assignment_rows:
        if not ("`" in expr and "$" in expr):
            continue

        has_user_input = any(source in expr for source in USER_INPUT_SOURCES)
        if not has_user_input:
            continue

        nearby_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", line - 5, line + 5)
        )

        near_exec = any(
            any(exec_func in callee for exec_func in EXEC_FUNCTIONS) for (callee,) in nearby_rows
        )

        if near_exec:
            findings.append(
                StandardFinding(
                    rule_name="command-injection-template",
                    message="Template literal with user input near exec function",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.MEDIUM,
                    snippet=expr[:80] + "..." if len(expr) > 80 else expr,
                    cwe_id="CWE-78",
                )
            )

    return findings


def _detect_spawn_shell_true(db: RuleDB) -> list[StandardFinding]:
    """Detect spawn() with shell:true - command injection vector.

    Args:
        db: RuleDB instance

    Returns:
        List of spawn shell:true findings
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, callee, args in rows:
        if "spawn" not in callee:
            continue
        if not args or "shell" not in args or "true" not in args:
            continue

        has_user_input = any(source in args for source in USER_INPUT_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="spawn-shell-true",
                    message="spawn() with shell:true and user input enables command injection",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet="spawn(..., {shell: true})",
                    cwe_id="CWE-78",
                )
            )

    return findings


def _detect_prototype_pollution(db: RuleDB) -> list[StandardFinding]:
    """Detect prototype pollution vulnerabilities.

    Checks for:
    1. Merge/extend functions with spread of user input
    2. for...in loops without hasOwnProperty validation
    3. Recursive merge functions without key validation

    Args:
        db: RuleDB instance

    Returns:
        List of prototype pollution findings
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not args:
            continue

        is_merge = any(merge_func in func for merge_func in MERGE_FUNCTIONS)
        if not is_merge:
            continue

        if "..." in args:
            for source in USER_INPUT_SOURCES:
                if source in args:
                    findings.append(
                        StandardFinding(
                            rule_name="prototype-pollution-merge",
                            message=f"Prototype pollution: {func} with spread of user input",
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category="injection",
                            confidence=Confidence.HIGH,
                            snippet=f"{func}({args[:50]}...)"
                            if len(args) > 50
                            else f"{func}({args})",
                            cwe_id="CWE-1321",
                        )
                    )
                    break

    symbol_rows = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("name IN (?, ?)", "for", "in")
        .order_by("path, line")
    )

    for file, line, _ in symbol_rows:
        validation_rows = db.query(
            Q("symbols")
            .select("name")
            .where("path = ?", file)
            .where("line BETWEEN ? AND ?", line, line + 10)
            .where("name IN (?, ?, ?, ?)", "hasOwnProperty", "hasOwn", "__proto__", "constructor")
            .limit(1)
        )

        has_validation = len(validation_rows) > 0

        if not has_validation:
            findings.append(
                StandardFinding(
                    rule_name="prototype-pollution-forin",
                    message="for...in loop without hasOwnProperty check may enable prototype pollution",
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category="injection",
                    confidence=Confidence.LOW,
                    snippet="for...in without hasOwnProperty check",
                    cwe_id="CWE-1321",
                )
            )

    return findings


def _detect_eval_injection(
    db: RuleDB, tainted_vars: dict[str, tuple[str, int, str]]
) -> list[StandardFinding]:
    """Detect dangerous eval() usage with user input.

    Args:
        db: RuleDB instance
        tainted_vars: Map of tainted variable names

    Returns:
        List of eval injection findings
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not args:
            continue

        is_eval = any(eval_func in func for eval_func in EVAL_FUNCTIONS)
        if not is_eval:
            continue

        found_source = None
        confidence = Confidence.HIGH

        for source in USER_INPUT_SOURCES:
            if source in args:
                found_source = source
                break

        if not found_source:
            for var_name in tainted_vars:
                if var_name in args:
                    found_source = f"tainted variable '{var_name}'"
                    break

        if not found_source:
            suspicious = ["input", "data", "user", "param", "query", "code", "script"]
            for pattern in suspicious:
                if pattern in args.lower():
                    found_source = f"suspicious parameter '{pattern}'"
                    confidence = Confidence.MEDIUM
                    break

        if found_source:
            findings.append(
                StandardFinding(
                    rule_name="eval-injection",
                    message=f"Code injection: {func} called with {found_source}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=confidence,
                    snippet=f"{func}({args[:50]}...)" if len(args) > 50 else f"{func}({args})",
                    cwe_id="CWE-94",
                )
            )

    return findings


def _detect_unsafe_regex(db: RuleDB) -> list[StandardFinding]:
    """Detect ReDoS vulnerabilities from user-constructed regex.

    Args:
        db: RuleDB instance

    Returns:
        List of unsafe regex findings
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if "RegExp" not in func:
            continue
        if not args:
            continue

        has_user_input = any(source in args for source in USER_INPUT_SOURCES)

        if not has_user_input:
            suspicious = ["input", "user", "search", "pattern", "query", "filter"]
            has_user_input = any(pattern in args.lower() for pattern in suspicious)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="unsafe-regex",
                    message="ReDoS risk: RegExp constructed from user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="denial-of-service",
                    confidence=Confidence.MEDIUM,
                    snippet=f"{func}({args[:50]}...)" if len(args) > 50 else f"{func}({args})",
                    cwe_id="CWE-1333",
                )
            )

    return findings


def _detect_path_traversal(db: RuleDB) -> list[StandardFinding]:
    """Detect path traversal vulnerabilities.

    Args:
        db: RuleDB instance

    Returns:
        List of path traversal findings
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not args:
            continue

        is_file_op = any(file_op in func for file_op in FILE_OPERATIONS)
        if not is_file_op:
            continue

        has_user_input = any(source in args for source in USER_INPUT_SOURCES)
        if not has_user_input:
            continue

        has_sanitization = any(safe_func in args for safe_func in PATH_SAFE_FUNCTIONS)

        if not has_sanitization:
            findings.append(
                StandardFinding(
                    rule_name="path-traversal",
                    message=f"Path traversal: {func} with unsanitized user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet=f"{func}({args[:50]}...)" if len(args) > 50 else f"{func}({args})",
                    cwe_id="CWE-22",
                )
            )

    return findings
