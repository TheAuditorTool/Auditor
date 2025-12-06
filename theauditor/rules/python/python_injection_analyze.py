"""Python Injection Vulnerability Analyzer - Detects SQL, command, code, template, LDAP, NoSQL, and XPath injection."""

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
    name="python_injection",
    category="injection",
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


SQL_METHODS = frozenset(
    [
        "execute",
        "executemany",
        "executescript",
        "raw",
        "connection.execute",
        "cursor.execute",
        "db.execute",
        "query",
        "run_query",
        "session.execute",
        "db.session.execute",
        "select",
        "insert",
        "update",
        "delete",
        "create_table",
    ]
)


STRING_FORMAT_PATTERNS = frozenset(
    [
        ".format(",
        "% (",
        'f"',
        "f'",
        "%%",
        "+ request.",
        "+ params.",
        "+ args.",
        "+ user_input",
        "+ data[",
        "+ input(",
    ]
)


COMMAND_METHODS = frozenset(
    [
        "os.system",
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.check_output",
        "subprocess.check_call",
        "subprocess.getoutput",
        "subprocess.getstatusoutput",
        "os.popen",
        "os.popen2",
        "os.popen3",
        "os.popen4",
        "popen",
        "commands.getstatusoutput",
        "commands.getoutput",
        "os.execl",
        "os.execle",
        "os.execlp",
        "os.execlpe",
        "os.execv",
        "os.execve",
        "os.execvp",
        "os.execvpe",
        "os.spawnl",
        "os.spawnle",
        "os.spawnlp",
        "os.spawnlpe",
        "os.spawnv",
        "os.spawnve",
        "os.spawnvp",
        "os.spawnvpe",
        "os.startfile",
    ]
)


SHELL_TRUE_PATTERNS = frozenset(
    [
        "shell=True",
        "shell = True",
        "shell= True",
        "shell =True",
    ]
)


CODE_INJECTION = frozenset(
    [
        "eval",
        "exec",
        "compile",
        "__import__",
        "execfile",
        "input",
        "raw_input",
    ]
)


TEMPLATE_PATTERNS = frozenset(
    [
        "render_template_string",
        "Environment",
        "Template",
        "jinja2.Template",
        "django.template.Template",
        "mako.template.Template",
        "tornado.template.Template",
    ]
)


LDAP_METHODS = frozenset(
    [
        "search",
        "search_s",
        "search_ext",
        "search_ext_s",
        "ldap.search",
        "ldap3.search",
        "ldap_search",
        "modify",
        "modify_s",
        "add",
        "add_s",
        "delete",
        "delete_s",
    ]
)


NOSQL_METHODS = frozenset(
    [
        "find",
        "find_one",
        "find_and_modify",
        "update_one",
        "update_many",
        "delete_one",
        "delete_many",
        "aggregate",
        "collection.find",
        "collection.update",
        "collection.delete",
        "db.find",
        "db.update",
        "db.delete",
    ]
)


XPATH_METHODS = frozenset(
    [
        "xpath",
        "findall",
        "find",
        "XPath",
        "evaluate",
        "selectNodes",
        "selectSingleNode",
        "query",
    ]
)


USER_INPUTS = frozenset(
    [
        "request.args",
        "request.form",
        "request.values",
        "request.data",
        "request.json",
        "request.files",
        "request.GET",
        "request.POST",
        "request.REQUEST",
        "input()",
        "raw_input()",
        "sys.argv",
        "os.environ",
        "flask.request",
        "django.request",
        "bottle.request",
    ]
)


SAFE_PATTERNS = frozenset(
    [
        "paramstyle",
        "params=",
        "parameters=",
        "?",
        "%s",
        "%(",
        ":name",
        "prepared",
        "statement",
        "placeholder",
    ]
)


SQL_KEYWORDS = frozenset(
    [
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "UNION",
        "WHERE",
        "ORDER BY",
        "GROUP BY",
        "CREATE",
        "ALTER",
        "EXEC",
        "EXECUTE",
    ]
)


NOSQL_DANGEROUS_OPERATORS = frozenset(
    [
        "$where",
        "$regex",
        "$function",
        "function()",
        "eval(",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Python injection vulnerabilities.

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

        _check_sql_injection(db, add_finding)
        _check_command_injection(db, add_finding)
        _check_code_injection(db, add_finding)
        _check_template_injection(db, add_finding)
        _check_ldap_injection(db, add_finding)
        _check_nosql_injection(db, add_finding)
        _check_xpath_injection(db, add_finding)
        _check_raw_sql_construction(db, add_finding)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_assignment_expr(db: RuleDB, file: str, variable: str, call_line: int) -> str | None:
    """Get the latest assignment expression for a variable before a call line.

    This enables basic taint tracking: if a variable is passed to execute(),
    we look up what was assigned to that variable.

    Note: This is a simple line-based heuristic. It assumes linear execution
    and will not correctly handle assignments in branches or loops. For full
    dataflow analysis, use the taint module instead.
    """
    rows = db.query(
        Q("assignments")
        .select("source_expr")
        .where("file = ? AND target_var = ? AND line <= ?", file, variable, call_line)
        .order_by("line DESC")
        .limit(1)
    )
    return rows[0][0] if rows else None


def _check_sql_injection(db: RuleDB, add_finding) -> None:
    """Detect SQL injection vulnerabilities via string formatting in queries."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(SQL_METHODS))
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not args:
            continue

        args_str = str(args)

        assignment_expr = None
        if args_str.isidentifier():
            assignment_expr = _get_assignment_expr(db, file, args_str, line)

        expr_to_check = assignment_expr or args_str

        has_formatting = any(fmt in expr_to_check for fmt in STRING_FORMAT_PATTERNS)
        has_concatenation = "+" in expr_to_check and any(
            inp in expr_to_check for inp in ["request.", "params.", "args.", "user_"]
        )

        has_safe_params = any(safe in expr_to_check for safe in SAFE_PATTERNS)

        if (has_formatting or has_concatenation) and not has_safe_params:
            has_sql_keywords = any(kw.lower() in expr_to_check.lower() for kw in SQL_KEYWORDS)
            confidence = Confidence.HIGH if has_sql_keywords else Confidence.MEDIUM

            add_finding(
                file=file,
                line=line,
                rule_name="python-sql-injection",
                message=f"SQL injection in {method} with string formatting",
                severity=Severity.CRITICAL,
                confidence=confidence,
                cwe_id="CWE-89",
            )

        is_fstring = 'f"' in expr_to_check or "f'" in expr_to_check
        if args_str.isidentifier() and assignment_expr:
            is_fstring = is_fstring or 'f"' in assignment_expr or "f'" in assignment_expr

        if is_fstring:
            add_finding(
                file=file,
                line=line,
                rule_name="python-sql-fstring",
                message="F-string used in SQL query - high injection risk",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-89",
            )


def _check_command_injection(db: RuleDB, add_finding) -> None:
    """Detect command injection vulnerabilities."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(COMMAND_METHODS))
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not args:
            continue

        args_str = str(args)

        has_shell_true = any(shell in args_str for shell in SHELL_TRUE_PATTERNS)

        has_user_input = any(inp in args_str for inp in USER_INPUTS)
        has_concatenation = (
            "+" in args_str or ".format(" in args_str or 'f"' in args_str or "f'" in args_str
        )

        if has_shell_true:
            add_finding(
                file=file,
                line=line,
                rule_name="python-shell-true",
                message="Command execution with shell=True is dangerous",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-78",
            )
        elif has_user_input or has_concatenation:
            confidence = Confidence.HIGH if has_user_input else Confidence.MEDIUM
            add_finding(
                file=file,
                line=line,
                rule_name="python-command-injection",
                message=f"Command injection risk in {method}",
                severity=Severity.CRITICAL,
                confidence=confidence,
                cwe_id="CWE-78",
            )


def _check_code_injection(db: RuleDB, add_finding) -> None:
    """Detect code injection (eval/exec) vulnerabilities."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(CODE_INJECTION))
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        severity = Severity.CRITICAL
        confidence = Confidence.HIGH

        if args:
            args_str = str(args)
            is_literal = args_str.startswith('"') or args_str.startswith("'")
            has_user_input = any(inp in args_str for inp in USER_INPUTS)

            if is_literal and not has_user_input:
                confidence = Confidence.MEDIUM
                severity = Severity.HIGH

        add_finding(
            file=file,
            line=line,
            rule_name="python-code-injection",
            message=f"Code injection risk: {method}() with dynamic input",
            severity=severity,
            confidence=confidence,
            cwe_id="CWE-94",
        )


def _check_template_injection(db: RuleDB, add_finding) -> None:
    """Detect Server-Side Template Injection (SSTI) vulnerabilities."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(TEMPLATE_PATTERNS))
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        args_str = str(args) if args else ""
        has_user_input = any(inp in args_str for inp in USER_INPUTS)

        if "render_template_string" in method:
            add_finding(
                file=file,
                line=line,
                rule_name="python-template-injection",
                message="render_template_string() is vulnerable to template injection",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-1336",
            )
        elif has_user_input:
            add_finding(
                file=file,
                line=line,
                rule_name="python-template-user-input",
                message=f"User input passed to template {method}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-1336",
            )


def _check_ldap_injection(db: RuleDB, add_finding) -> None:
    """Detect LDAP injection vulnerabilities."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(LDAP_METHODS))
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        args_str = str(args) if args else ""
        has_formatting = any(fmt in args_str for fmt in STRING_FORMAT_PATTERNS)
        has_user_input = any(inp in args_str for inp in USER_INPUTS)

        if has_formatting or has_user_input:
            add_finding(
                file=file,
                line=line,
                rule_name="python-ldap-injection",
                message=f"LDAP injection risk in {method}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-90",
            )


def _check_nosql_injection(db: RuleDB, add_finding) -> None:
    """Detect NoSQL (MongoDB) injection vulnerabilities."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(NOSQL_METHODS))
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        args_str = str(args) if args else ""

        has_dangerous = any(op in args_str for op in NOSQL_DANGEROUS_OPERATORS)
        has_user_input = any(inp in args_str for inp in USER_INPUTS)

        if has_dangerous:
            add_finding(
                file=file,
                line=line,
                rule_name="python-nosql-dangerous-operator",
                message=f"Dangerous NoSQL operator in {method}",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-943",
            )
        elif has_user_input:
            add_finding(
                file=file,
                line=line,
                rule_name="python-nosql-injection",
                message=f"NoSQL injection risk in {method}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-943",
            )


def _check_xpath_injection(db: RuleDB, add_finding) -> None:
    """Detect XPath injection vulnerabilities."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(XPATH_METHODS))
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        args_str = str(args) if args else ""
        has_formatting = any(fmt in args_str for fmt in STRING_FORMAT_PATTERNS)

        if has_formatting:
            add_finding(
                file=file,
                line=line,
                rule_name="python-xpath-injection",
                message=f"XPath injection risk in {method}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-91",
            )


def _check_raw_sql_construction(db: RuleDB, add_finding) -> None:
    """Check for SQL queries constructed via string operations in assignments.

    To reduce false positives (e.g., log messages mentioning SQL keywords),
    we require either:
    1. Variable name indicates SQL purpose (query, sql, stmt, etc.)
    2. Expression starts with SQL keyword (actually constructing SQL)
    """

    sql_var_patterns = {"query", "sql", "stmt", "statement", "cmd", "command", "script"}

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for row in rows:
        file, line, var, expr = row[0], row[1], row[2], row[3]
        if not expr or not var:
            continue

        expr_str = str(expr)
        expr_upper = expr_str.upper()
        var_lower = var.lower()

        has_sql_keyword = any(kw in expr_upper for kw in ["SELECT", "INSERT", "UPDATE", "DELETE"])
        if not has_sql_keyword:
            continue

        has_formatting = any(pattern in expr_str for pattern in ["+", ".format(", 'f"', "f'"])
        if not has_formatting:
            continue

        is_sql_var = any(p in var_lower for p in sql_var_patterns)
        starts_with_sql = any(
            expr_upper.lstrip(" \"'f").startswith(kw)
            for kw in ["SELECT", "INSERT", "UPDATE", "DELETE"]
        )

        if not is_sql_var and not starts_with_sql:
            continue

        add_finding(
            file=file,
            line=line,
            rule_name="python-sql-string-building",
            message=f"SQL query built with string concatenation in {var}",
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-89",
        )
