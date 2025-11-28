"""GraphQL Injection Detection - Database-First Taint Analysis."""

import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="graphql_injection",
    category="security",
    target_extensions=[".graphql", ".gql", ".graphqls", ".py", ".js", ".ts"],
    execution_scope="database",
    requires_jsx_pass=False,
)


def check_graphql_injection(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect GraphQL injection via taint analysis."""
    if not context.db_path:
        return []

    findings = []
    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='graphql_resolver_mappings'
    """)
    if not cursor.fetchone():
        return findings

    cursor.execute("""
        SELECT
            fa.arg_name,
            fa.arg_type,
            f.field_name,
            t.type_name,
            rm.resolver_path,
            rm.resolver_line,
            fa.field_id
        FROM graphql_field_args fa
        JOIN graphql_fields f ON f.field_id = fa.field_id
        JOIN graphql_types t ON t.type_id = f.type_id
        LEFT JOIN graphql_resolver_mappings rm ON rm.field_id = fa.field_id
        WHERE rm.resolver_path IS NOT NULL
    """)

    for row in cursor.fetchall():
        arg_name = row["arg_name"]
        field_name = row["field_name"]
        type_name = row["type_name"]
        resolver_path = row["resolver_path"]
        resolver_line = row["resolver_line"]

        cursor.execute(
            """
            SELECT query_text, line, command
            FROM sql_queries
            WHERE file = ?
            AND line > ?
            AND line < ? + 50
        """,
            (resolver_path, resolver_line, resolver_line),
        )

        sql_queries = cursor.fetchall()

        for sql_row in sql_queries:
            query_text = sql_row["query_text"]
            query_line = sql_row["line"]
            command = sql_row["command"]

            if any(pattern in query_text for pattern in ["%s", ".format", 'f"', "f'"]):
                cursor.execute(
                    """
                    SELECT argument_expr
                    FROM function_call_args
                    WHERE file = ?
                    AND line BETWEEN ? AND ?
                """,
                    (resolver_path, resolver_line, query_line),
                )

                found_arg_in_context = any(
                    row["argument_expr"] and arg_name in row["argument_expr"]
                    for row in cursor.fetchall()
                )

                if found_arg_in_context:
                    finding = StandardFinding(
                        rule_name="graphql_injection",
                        message=f"GraphQL argument '{arg_name}' from {type_name}.{field_name} flows to SQL query without sanitization",
                        file_path=resolver_path,
                        line=query_line,
                        severity=Severity.CRITICAL,
                        category="security",
                        confidence=Confidence.HIGH,
                        snippet=query_text[:200] if query_text else "",
                        cwe_id="CWE-89",
                        additional_info={
                            "graphql_field": f"{type_name}.{field_name}",
                            "argument": arg_name,
                            "sql_command": command,
                            "query_snippet": query_text[:100] if query_text else "",
                            "recommendation": "Use parameterized queries instead of string formatting",
                        },
                    )
                    findings.append(finding)

    conn.close()
    return findings
