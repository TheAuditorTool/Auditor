"""GraphQL Query Depth Check - Prevent DoS via nested queries."""

import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="graphql_query_depth",
    category="security",
    execution_scope="database",
    requires_jsx_pass=False,
)


def check_query_depth(context: StandardRuleContext) -> list[StandardFinding]:
    """Check for unrestricted query depth (DoS risk).

    Detects:
    - List fields returning complex types (potential nested queries)
    - Lack of depth limiting configuration
    """
    if not context.db_path:
        return []

    findings = []
    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT f.field_id, f.field_name, f.return_type, t.type_name, t.schema_path, f.line
        FROM graphql_fields f
        JOIN graphql_types t ON t.type_id = f.type_id
        WHERE f.is_list = 1
          AND f.return_type NOT IN ('String', 'Int', 'Float', 'Boolean', 'ID')
    """)

    for row in cursor.fetchall():
        return_type = row["return_type"].rstrip("!").strip("[]")

        cursor.execute(
            """
            SELECT COUNT(*) as nested_list_count
            FROM graphql_types t
            JOIN graphql_fields f ON f.type_id = t.type_id
            WHERE t.type_name = ? AND f.is_list = 1
        """,
            (return_type,),
        )

        nested = cursor.fetchone()
        if nested and nested["nested_list_count"] > 0:
            finding = StandardFinding(
                rule_name="graphql_query_depth",
                message=f"Field '{row['type_name']}.{row['field_name']}' allows nested list queries (DoS risk)",
                file_path=row["schema_path"],
                line=row["line"] or 0,
                severity=Severity.MEDIUM,
                category="security",
                confidence=Confidence.HIGH,
                cwe_id="CWE-400",
                additional_info={
                    "field": f"{row['type_name']}.{row['field_name']}",
                    "return_type": row["return_type"],
                    "nested_lists": nested["nested_list_count"],
                    "recommendation": "Implement query depth limiting (max depth 5-10) and complexity analysis",
                },
            )
            findings.append(finding)

    conn.close()
    return findings
