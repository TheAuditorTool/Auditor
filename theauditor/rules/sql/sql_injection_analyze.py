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

# =============================================================================
# METADATA
# =============================================================================

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

# =============================================================================
# DETECTION PATTERNS
# =============================================================================

# SQL keywords that indicate a SQL statement
SQL_KEYWORDS = frozenset([
    "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "TRUNCATE", "EXEC", "EXECUTE", "UNION", "MERGE", "REPLACE", "UPSERT",
])

# Patterns indicating string interpolation/concatenation (dangerous in SQL)
INTERPOLATION_PATTERNS = frozenset([
    "${",           # JS template literal interpolation
    ".format(",     # Python str.format()
    "% ",           # Python % formatting (with space to avoid %s params)
    "%(",           # Python % formatting with named params
    '+ "',          # String concatenation
    '" +',          # String concatenation
    "+ '",          # String concatenation (single quotes)
    "' +",          # String concatenation (single quotes)
    'f"',           # Python f-string (double quotes)
    "f'",           # Python f-string (single quotes)
    "`",            # JS template literal
    "String.format",  # Java String.format
    "sprintf",      # C-style sprintf
    "concat(",      # SQL CONCAT or string concat method
])

# ORM and database raw query methods that bypass parameterization
RAW_QUERY_METHODS = frozenset([
    # Node.js ORMs
    "sequelize.query",
    "knex.raw",
    "db.raw",
    "typeorm.query",
    "prisma.$queryRaw",
    "prisma.$executeRaw",
    "prisma.$queryRawUnsafe",
    "prisma.$executeRawUnsafe",
    "mongoose.aggregate",
    # Python ORMs
    "session.execute",
    "engine.execute",
    "connection.execute",
    "cursor.execute",
    "cursor.executemany",
    "cursor.executescript",
    "execute_sql",
    "raw_sql",
    # Java
    "createStatement",
    "prepareStatement",
    "executeQuery",
    "executeUpdate",
    # General
    "raw(",
    "executeSql",
    "exec(",
])

# User input sources that should never reach SQL sinks unsanitized
USER_INPUT_PATTERNS = frozenset([
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
])

# Stored procedure patterns
STORED_PROC_PATTERNS = frozenset([
    "CALL ",
    "EXEC ",
    "EXECUTE ",
    "sp_executesql",
    "xp_cmdshell",
    "sp_",
])

# Patterns that indicate safe parameterization (filter these out)
SAFE_PARAM_INDICATORS = frozenset([
    "?",            # Positional placeholder
    ":1", ":2",     # Oracle-style numbered params
    "$1", "$2",     # PostgreSQL-style numbered params
    "@",            # SQL Server named params
    ":param",       # Named parameter
])


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

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

        # Run all detection checks
        findings.extend(_check_interpolated_sql_queries(db))
        findings.extend(_check_dynamic_execute_calls(db))
        findings.extend(_check_orm_raw_queries(db))
        findings.extend(_check_user_input_to_sql(db))
        findings.extend(_check_template_literal_sql(db))
        findings.extend(_check_stored_procedure_injection(db))
        findings.extend(_check_dynamic_query_construction(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


# =============================================================================
# DETECTION FUNCTIONS
# =============================================================================

def _check_interpolated_sql_queries(db: RuleDB) -> list[StandardFinding]:
    """Check sql_queries table for queries with string interpolation.

    This catches SQL statements that were constructed with f-strings,
    .format(), or string concatenation.
    """
    findings = []

    # Build regex pattern for interpolation detection
    interpolation_tokens = [re.escape(p) for p in INTERPOLATION_PATTERNS]
    interpolation_regex = "|".join(interpolation_tokens)

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text")
        .where("has_interpolation = ?", 1)
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

        # Check if query matches interpolation patterns
        if not re.search(interpolation_regex, query_text, re.IGNORECASE):
            continue

        # Skip if query appears to use safe parameterization
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

        # Must be SQL-related function
        func_lower = func.lower()
        if not any(kw in func_lower for kw in ["execute", "query", "sql", "db", "cursor", "conn"]):
            continue

        # Check for string construction patterns
        if not _has_interpolation(args):
            continue

        # Skip if appears to have safe parameterization
        if _has_safe_params(args):
            continue

        # Deduplicate by location
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

    # Query for each raw query method pattern
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

            # Check for interpolation patterns
            if not _has_interpolation(args):
                continue

            # Skip if has safe params
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

    # Build user input pattern regex
    user_input_patterns = "|".join(re.escape(p) for p in USER_INPUT_PATTERNS)

    # CTE: Find assignments where source is user input and target looks like SQL variable
    tainted_vars = (
        Q("assignments")
        .select("file", "target_var", "source_expr")
        .where("source_expr REGEXP ?", user_input_patterns)
        .where("target_var REGEXP ?", r"(?i)(sql|query|stmt|command|qry)")
        .where("file NOT LIKE ?", "%test%")
        .where("file NOT LIKE ?", "%migration%")
    )

    # Main query: Find SQL execution calls using tainted variables
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
        .where("function_call_args.callee_function LIKE ? OR function_call_args.callee_function LIKE ?",
               "%execute%", "%query%")
    )

    for file, line, func, arg_expr, var, source in rows:
        # Verify tainted variable actually appears in function arguments
        if not arg_expr or var not in arg_expr:
            continue

        # Word boundary check to avoid "id" matching "width", "valid", etc.
        if not re.search(r'\b' + re.escape(var) + r'\b', arg_expr):
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
        Q("template_literals")
        .select("file", "line", "content")
        .where("file NOT LIKE ?", "%test%")
        .order_by("file, line")
    )

    for file, line, content in rows:
        if not content:
            continue

        # Check if content contains SQL keywords
        content_upper = content.upper()
        if not any(kw in content_upper for kw in SQL_KEYWORDS):
            continue

        # Check for interpolation in template literal
        if "${" not in content:
            continue

        # Skip if appears to be parameterized
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
            .where("callee_function LIKE ? OR argument_expr LIKE ?",
                   f"%{sp_pattern}%", f"%{sp_pattern}%")
            .where("file NOT LIKE ?", "%test%")
            .order_by("file, line")
        )

        for file, line, func, args in rows:
            if not args:
                continue

            # Check for dynamic construction
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

        # Check for interpolation patterns
        if not _has_interpolation(query_text):
            continue

        # Skip if has safe parameterization
        if _has_safe_params(query_text):
            continue

        # Deduplicate
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


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _has_interpolation(text: str) -> bool:
    """Check if text contains string interpolation/concatenation patterns."""
    return any(pattern in text for pattern in INTERPOLATION_PATTERNS)


def _has_safe_params(text: str) -> bool:
    """Check if text appears to use safe parameterization."""
    return any(param in text for param in SAFE_PARAM_INDICATORS)


# =============================================================================
# TAINT REGISTRY (Called by taint analysis engine)
# =============================================================================

def register_taint_patterns(taint_registry) -> None:
    """Register SQL injection sinks and sources for taint analysis.

    Called by the taint analysis engine during initialization.
    """
    # SQL execution sinks
    sql_sinks = [
        "execute", "query", "exec", "executemany", "executescript",
        "executeQuery", "executeUpdate", "cursor.execute", "conn.execute",
        "db.execute", "session.execute", "engine.execute", "db.query",
        "connection.query", "pool.query", "client.query", "knex.raw",
        "sequelize.query", "prepareStatement", "createStatement",
        "prepareCall", "prisma.$queryRaw", "prisma.$executeRaw",
    ]

    for pattern in sql_sinks:
        for lang in ["python", "javascript", "java", "typescript", "go"]:
            taint_registry.register_sink(pattern, "sql", lang)

    # User input sources
    user_sources = [
        "request.query", "request.params", "request.body", "req.query",
        "req.params", "req.body", "req.headers", "request.headers",
        "args.get", "form.get", "request.args", "request.form",
        "request.values", "request.cookies", "getParameter",
    ]

    for pattern in user_sources:
        for lang in ["python", "javascript", "typescript"]:
            taint_registry.register_source(pattern, "user_input", lang)
