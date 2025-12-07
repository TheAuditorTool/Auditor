"""SQL Injection Detection - CWE-89.

Detects SQL injection vulnerabilities across multiple patterns:
1. String interpolation in SQL queries (f-strings, .format(), concatenation)
2. Dynamic SQL construction without parameterization
3. ORM raw query methods with user input
4. User input flowing to SQL execution sinks
5. Template literals with SQL and interpolation
6. Stored procedure calls with dynamic input
"""

import re

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q
from theauditor.rules.sql.utils import register_regexp, truncate

METADATA = RuleMetadata(
    name="sql_injection",
    category="security",
    target_extensions=[".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php"],
    exclude_patterns=[
        "node_modules/",
        ".venv/",
        "__pycache__/",
        "test/",
        "tests/",
        "spec/",
        "fixtures/",
        "mocks/",
        "migrations/",
    ],
    execution_scope="database",
    primary_table="sql_queries",
)


SQL_KEYWORDS = frozenset(
    [
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "EXEC",
        "EXECUTE",
        "UNION",
        "MERGE",
        "REPLACE",
        "UPSERT",
    ]
)


INTERPOLATION_PATTERNS = frozenset(
    [
        "${",
        ".format(",
        "% ",
        "%(",
        '+ "',
        '" +',
        "+ '",
        "' +",
        'f"',
        "f'",
        "`",
        "String.format",
        "sprintf",
        "concat(",
    ]
)


RAW_QUERY_METHODS = frozenset(
    [
        "sequelize.query",
        "knex.raw",
        "db.raw",
        "typeorm.query",
        "prisma.$queryRaw",
        "prisma.$executeRaw",
        "prisma.$queryRawUnsafe",
        "prisma.$executeRawUnsafe",
        "mongoose.aggregate",
        "session.execute",
        "engine.execute",
        "connection.execute",
        "cursor.execute",
        "cursor.executemany",
        "cursor.executescript",
        "execute_sql",
        "raw_sql",
        "createStatement",
        "prepareStatement",
        "executeQuery",
        "executeUpdate",
        "raw(",
        "executeSql",
        "exec(",
    ]
)


USER_INPUT_PATTERNS = frozenset(
    [
        "request.",
        "req.",
        "params.",
        "query.",
        "body.",
        "args.",
        "form.",
        "headers.",
        "cookies.",
        "input(",
        "argv",
        "stdin",
        "getParameter",
        "getQueryString",
    ]
)


STORED_PROC_PATTERNS = frozenset(
    [
        "CALL ",
        "EXEC ",
        "EXECUTE ",
        "sp_executesql",
        "xp_cmdshell",
        "sp_",
    ]
)


SAFE_PARAM_INDICATORS = frozenset(
    [
        "?",
        ":1",
        ":2",
        "$1",
        "$2",
        "@",
        ":param",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect SQL injection vulnerabilities in indexed codebase.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    findings: list[StandardFinding] = []

    with RuleDB(context.db_path, METADATA.name) as db:
        register_regexp(db.conn)

        findings.extend(_check_interpolated_sql_queries(db))
        findings.extend(_check_dynamic_execute_calls(db))
        findings.extend(_check_orm_raw_queries(db))
        findings.extend(_check_user_input_to_sql(db))
        findings.extend(_check_template_literal_sql(db))
        findings.extend(_check_stored_procedure_injection(db))
        findings.extend(_check_dynamic_query_construction(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_interpolated_sql_queries(db: RuleDB) -> list[StandardFinding]:
    """Check sql_queries table for queries with string interpolation.

    This catches SQL statements that were constructed with f-strings,
    .format(), or string concatenation.
    """
    findings = []

    interpolation_tokens = [re.escape(p) for p in INTERPOLATION_PATTERNS]
    interpolation_regex = "|".join(interpolation_tokens)

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text")
        .where("file_path NOT LIKE ?", "%test%")
        .where("file_path NOT LIKE ?", "%migration%")
        .where("file_path NOT LIKE ?", "%fixture%")
        .where("file_path NOT LIKE ?", "%mock%")
        .where("file_path NOT LIKE ?", "%spec%")
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text in rows:
        if not query_text:
            continue

        if not re.search(interpolation_regex, query_text, re.IGNORECASE):
            continue

        if _has_safe_params(query_text):
            continue

        findings.append(
            StandardFinding(
                rule_name="sql-injection-interpolation",
                message="SQL query with string interpolation detected - high injection risk",
                file_path=file_path,
                line=line_number,
                severity=Severity.CRITICAL,
                category=METADATA.category,
                snippet=truncate(query_text, 100),
                cwe_id="CWE-89",
            )
        )

    return findings


def _check_dynamic_execute_calls(db: RuleDB) -> list[StandardFinding]:
    """Check function calls to execute/query methods with dynamic arguments."""
    findings = []
    seen = set()

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ? OR callee_function LIKE ?", "%execute%", "%query%")
        .where("file NOT LIKE ?", "%test%")
        .where("file NOT LIKE ?", "%migration%")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not args:
            continue

        func_lower = func.lower()
        if not any(kw in func_lower for kw in ["execute", "query", "sql", "db", "cursor", "conn"]):
            continue

        if not _has_interpolation(args):
            continue

        if _has_safe_params(args):
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-injection-dynamic-args",
                message=f"SQL function {func}() called with dynamic string construction",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category=METADATA.category,
                snippet=truncate(args, 80),
                cwe_id="CWE-89",
            )
        )

    return findings


def _check_orm_raw_queries(db: RuleDB) -> list[StandardFinding]:
    """Check for ORM raw query methods with dynamic SQL."""
    findings = []

    for method in RAW_QUERY_METHODS:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function LIKE ?", f"%{method}%")
            .where("file NOT LIKE ?", "%test%")
            .order_by("file, line")
        )

        for file, line, func, args in rows:
            if not args:
                continue

            if not _has_interpolation(args):
                continue

            if _has_safe_params(args):
                continue

            findings.append(
                StandardFinding(
                    rule_name="sql-injection-orm-raw",
                    message=f"ORM raw query method {func}() with dynamic SQL construction",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    snippet=truncate(args, 80),
                    cwe_id="CWE-89",
                )
            )

    return findings


def _check_user_input_to_sql(db: RuleDB) -> list[StandardFinding]:
    """Check for user input flowing to SQL execution sinks.

    Uses CTE to find tainted variables then checks if they reach SQL functions.
    """
    findings = []

    user_input_patterns = "|".join(re.escape(p) for p in USER_INPUT_PATTERNS)

    tainted_vars = (
        Q("assignments")
        .select("file", "target_var", "source_expr")
        .where("source_expr REGEXP ?", user_input_patterns)
        .where("target_var REGEXP ?", r"(?i)(sql|query|stmt|command|qry)")
        .where("file NOT LIKE ?", "%test%")
        .where("file NOT LIKE ?", "%migration%")
    )

    rows = db.query(
        Q("function_call_args")
        .with_cte("tainted_vars", tainted_vars)
        .select(
            "function_call_args.file",
            "function_call_args.line",
            "function_call_args.callee_function",
            "function_call_args.argument_expr",
            "tainted_vars.target_var",
            "tainted_vars.source_expr",
        )
        .join("tainted_vars", on=[("file", "file")])
        .where(
            "function_call_args.callee_function LIKE ? OR function_call_args.callee_function LIKE ?",
            "%execute%",
            "%query%",
        )
    )

    for file, line, func, arg_expr, var, source in rows:
        if not arg_expr or var not in arg_expr:
            continue

        if not re.search(r"\b" + re.escape(var) + r"\b", arg_expr):
            continue

        findings.append(
            StandardFinding(
                rule_name="sql-injection-user-input",
                message=f"User input from '{truncate(source, 30)}' flows to SQL function {func}()",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category=METADATA.category,
                snippet=f"Tainted variable '{var}' used in {func}()",
                cwe_id="CWE-89",
            )
        )

    return findings


def _check_template_literal_sql(db: RuleDB) -> list[StandardFinding]:
    """Check for template literals containing SQL with interpolation."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr LIKE ?", "%${%")
        .where("file NOT LIKE ?", "%test%")
        .order_by("file, line")
    )

    for file, line, content in rows:
        if not content:
            continue

        content_upper = content.upper()
        if not any(kw in content_upper for kw in SQL_KEYWORDS):
            continue

        if "${" not in content:
            continue

        if _has_safe_params(content):
            continue

        findings.append(
            StandardFinding(
                rule_name="sql-injection-template-literal",
                message="Template literal contains SQL query with interpolation",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category=METADATA.category,
                snippet=truncate(content, 100),
                cwe_id="CWE-89",
            )
        )

    return findings


def _check_stored_procedure_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for stored procedure calls with dynamic input."""
    findings = []

    for sp_pattern in STORED_PROC_PATTERNS:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where(
                "callee_function LIKE ? OR argument_expr LIKE ?",
                f"%{sp_pattern}%",
                f"%{sp_pattern}%",
            )
            .where("file NOT LIKE ?", "%test%")
            .order_by("file, line")
        )

        for file, line, _func, args in rows:
            if not args:
                continue

            if not _has_interpolation(args):
                continue

            findings.append(
                StandardFinding(
                    rule_name="sql-injection-stored-proc",
                    message="Stored procedure call with dynamic input construction",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    snippet=truncate(args, 80),
                    cwe_id="CWE-89",
                )
            )

    return findings


def _check_dynamic_query_construction(db: RuleDB) -> list[StandardFinding]:
    """Check sql_queries table for dynamic construction without parameterization."""
    findings = []
    seen = set()

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text", "command")
        .where("file_path NOT LIKE ?", "%test%")
        .where("file_path NOT LIKE ?", "%migration%")
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text, command in rows:
        if not query_text:
            continue

        if not _has_interpolation(query_text):
            continue

        if _has_safe_params(query_text):
            continue

        key = f"{file_path}:{line_number}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-injection-dynamic-query",
                message=f"{command or 'SQL'} query with dynamic construction without parameterization",
                file_path=file_path,
                line=line_number,
                severity=Severity.HIGH,
                category=METADATA.category,
                snippet=truncate(query_text, 80),
                cwe_id="CWE-89",
            )
        )

    return findings


def _has_interpolation(text: str) -> bool:
    """Check if text contains string interpolation/concatenation patterns."""
    return any(pattern in text for pattern in INTERPOLATION_PATTERNS)


def _has_safe_params(text: str) -> bool:
    """Check if text appears to use safe parameterization."""
    return any(param in text for param in SAFE_PARAM_INDICATORS)


def register_taint_patterns(taint_registry) -> None:
    """Register SQL injection sinks and sources for taint analysis.

    Called by the taint analysis engine during initialization.
    """

    sql_sinks = [
        "execute",
        "query",
        "exec",
        "executemany",
        "executescript",
        "executeQuery",
        "executeUpdate",
        "cursor.execute",
        "conn.execute",
        "db.execute",
        "session.execute",
        "engine.execute",
        "db.query",
        "connection.query",
        "pool.query",
        "client.query",
        "knex.raw",
        "sequelize.query",
        "prepareStatement",
        "createStatement",
        "prepareCall",
        "prisma.$queryRaw",
        "prisma.$executeRaw",
    ]

    for pattern in sql_sinks:
        for lang in ["python", "javascript", "java", "typescript", "go"]:
            taint_registry.register_sink(pattern, "sql", lang)

    user_sources = [
        "request.query",
        "request.params",
        "request.body",
        "req.query",
        "req.params",
        "req.body",
        "req.headers",
        "request.headers",
        "args.get",
        "form.get",
        "request.args",
        "request.form",
        "request.values",
        "request.cookies",
        "getParameter",
    ]

    for pattern in user_sources:
        for lang in ["python", "javascript", "typescript"]:
            taint_registry.register_source(pattern, "user_input", lang)
