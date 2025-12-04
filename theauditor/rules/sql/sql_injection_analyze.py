"""SQL Injection Detection."""

import re
import sqlite3
from dataclasses import dataclass

from theauditor.indexer.schema import build_query
from theauditor.rules.base import Severity, StandardFinding, StandardRuleContext


def _regexp_adapter(expr: str, item: str) -> bool:
    """Adapter to let SQLite use Python's regex engine."""
    if item is None:
        return False
    return re.search(expr, item, re.IGNORECASE) is not None


@dataclass(frozen=True)
class SQLInjectionPatterns:
    """SQL injection patterns."""

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
        ]
    )

    INTERPOLATION_PATTERNS = frozenset(
        ["${", "%s", "%(", "{0}", "{1}", ".format(", '+ "', '" +', "+ '", "' +", 'f"', "f'", "`"]
    )

    SAFE_PARAMS = frozenset(["?", ":1", ":2", "$1", "$2", "%s", "@param", ":param", "${param}"])


def find_sql_injection_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Analyze codebase for SQL injection vulnerabilities.

    Named find_* for orchestrator discovery - enables register_taint_patterns loading.
    """
    findings = []
    patterns = SQLInjectionPatterns()

    conn = sqlite3.connect(context.db_path)

    conn.create_function("REGEXP", 2, _regexp_adapter)

    cursor = conn.cursor()

    interpolation_tokens = []
    for pattern in patterns.INTERPOLATION_PATTERNS:
        interpolation_tokens.append(re.escape(pattern))

    interpolation_regex = "|".join(interpolation_tokens)

    cursor.execute(
        """
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE has_interpolation = 1
          AND file_path NOT LIKE '%test%'
          AND file_path NOT LIKE '%migration%'
          AND query_text REGEXP ?
        ORDER BY file_path, line_number
    """,
        (interpolation_regex,),
    )

    for file, line, query_text in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="sql-injection-interpolation",
                message="SQL query with string interpolation - high injection risk",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="security",
                snippet=query_text[:100] + "..." if len(query_text) > 100 else query_text,
                cwe_id="CWE-89",
            )
        )

    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        where="callee_function LIKE '%execute%' OR callee_function LIKE '%query%'",
        order_by="file, line",
    )
    cursor.execute(query)

    seen_dynamic = set()
    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        if not any(kw in func.lower() for kw in ["execute", "query", "sql", "db"]):
            continue

        has_concat = any(pattern in args for pattern in ["+", "${", 'f"', ".format(", "%"])

        if has_concat:
            key = f"{file}:{line}"
            if key not in seen_dynamic:
                seen_dynamic.add(key)
                findings.append(
                    StandardFinding(
                        rule_name="sql-injection-dynamic-args",
                        message=f"{func} called with dynamic SQL construction",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=args[:80] + "..." if len(args) > 80 else args,
                        cwe_id="CWE-89",
                    )
                )

    raw_query_patterns = [
        "sequelize.query",
        "knex.raw",
        "db.raw",
        "raw(",
        "execute_sql",
        "executeSql",
        "session.execute",
    ]

    placeholders = ",".join(["?" for _ in raw_query_patterns])
    query = build_query(
        "function_call_args",
        ["file", "line", "callee_function", "argument_expr"],
        where=f"callee_function IN ({placeholders})",
        order_by="file, line",
    )
    cursor.execute(query, raw_query_patterns)

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        if any(pattern in args for pattern in patterns.INTERPOLATION_PATTERNS):
            findings.append(
                StandardFinding(
                    rule_name="sql-injection-orm-raw",
                    message=f"ORM raw query {func} with dynamic SQL",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    snippet=args[:80] + "..." if len(args) > 80 else args,
                    cwe_id="CWE-89",
                )
            )

    cursor.execute("""
        WITH tainted_vars AS (
            SELECT file, target_var, source_expr
            FROM assignments
            WHERE (source_expr LIKE '%request.%' OR source_expr LIKE '%req.%')
              AND target_var REGEXP '(?i)(sql|query|stmt|command)'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
        )
        SELECT f.file, f.line, f.callee_function, t.target_var, t.source_expr
        FROM function_call_args f
        INNER JOIN tainted_vars t
            ON f.file = t.file
            AND (f.callee_function LIKE '%execute%' OR f.callee_function LIKE '%query%')
            AND f.argument_expr LIKE '%' || t.target_var || '%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, var, expr in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="sql-injection-user-input",
                message=f"User input from {expr[:30]} used in SQL {func}",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="security",
                snippet=f"{var} used in {func}",
                cwe_id="CWE-89",
            )
        )

    query = build_query("template_literals", ["file", "line", "content"], order_by="file, line")
    cursor.execute(query)

    for file, line, content in cursor.fetchall():
        if not content:
            continue

        content_upper = content.upper()
        has_sql = any(kw in content_upper for kw in patterns.SQL_KEYWORDS)

        if has_sql and "${" in content:
            findings.append(
                StandardFinding(
                    rule_name="sql-injection-template-literal",
                    message="Template literal contains SQL with interpolation",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    snippet=content[:100] + "..." if len(content) > 100 else content,
                    cwe_id="CWE-89",
                )
            )

    sp_patterns = ["CALL", "EXEC", "EXECUTE", "sp_executesql"]

    for sp in sp_patterns:
        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where="callee_function LIKE ? OR argument_expr LIKE ?",
            order_by="file, line",
        )
        cursor.execute(query, [f"%{sp}%", f"%{sp}%"])

        for file, line, _func, args in cursor.fetchall():
            if not args:
                continue

            if any(pattern in args for pattern in ["+", "${", ".format"]):
                findings.append(
                    StandardFinding(
                        rule_name="sql-injection-stored-proc",
                        message="Stored procedure call with dynamic input",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=args[:80] + "..." if len(args) > 80 else args,
                        cwe_id="CWE-89",
                    )
                )

    conn.close()
    return findings


def check_dynamic_query_construction(context: StandardRuleContext) -> list[StandardFinding]:
    """Check for dynamic SQL query construction patterns."""
    findings = []
    patterns = SQLInjectionPatterns()

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    query = build_query(
        "sql_queries", ["file", "line", "query_text", "command"], order_by="file, line"
    )
    cursor.execute(query)

    seen = set()
    for file, line, query, command in cursor.fetchall():
        if not query:
            continue

        has_interpolation = any(pattern in query for pattern in patterns.INTERPOLATION_PATTERNS)

        if not has_interpolation:
            continue

        has_params = any(param in query for param in patterns.SAFE_PARAMS)

        if has_params:
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-injection-dynamic-query",
                message=f"{command} query with dynamic construction - potential injection risk",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="security",
                snippet=query[:80] + "..." if len(query) > 80 else query,
                cwe_id="CWE-89",
            )
        )

    return findings


def register_taint_patterns(taint_registry):
    """Register SQL injection sinks and sources for taint analysis."""

    sql_sinks = [
        "execute",
        "query",
        "exec",
        "executemany",
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
        "executeQuery",
        "executeUpdate",
        "prepareStatement",
        "createStatement",
        "prepareCall",
    ]

    for pattern in sql_sinks:
        for lang in ["python", "javascript", "java", "typescript"]:
            taint_registry.register_sink(pattern, "sql", lang)

    sql_sources = [
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
    ]

    for pattern in sql_sources:
        for lang in ["python", "javascript", "typescript"]:
            taint_registry.register_source(pattern, "user_input", lang)
