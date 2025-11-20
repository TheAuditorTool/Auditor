"""GraphQL N+1 Query Detection - CFG-Based Loop Analysis.

Detects N+1 query patterns where resolvers execute DB queries inside loops.
Uses cfg_blocks + graphql_execution_edges. NO regex fallbacks.
"""


import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="graphql_nplus1",
    category="performance",
    target_extensions=['.graphql', '.gql', '.graphqls', '.py', '.js', '.ts'],
    execution_scope='database',
    requires_jsx_pass=False
)


def check_graphql_nplus1(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect N+1 query patterns in GraphQL resolvers.

    Strategy:
    1. Find list-returning GraphQL fields (is_list=1)
    2. Get their child field resolvers
    3. Check if child resolvers have loops in CFG
    4. Check if those loops contain DB queries
    5. Report N+1 pattern

    NO FALLBACKS. Database must exist.
    """
    if not context.db_path:
        return []

    findings = []
    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if GraphQL tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='graphql_resolver_mappings'
    """)
    if not cursor.fetchone():
        return findings  # No GraphQL data

    # Find list-returning fields
    cursor.execute("""
        SELECT
            f.field_id,
            f.field_name,
            f.return_type,
            t.type_name,
            rm.resolver_path,
            rm.resolver_line
        FROM graphql_fields f
        JOIN graphql_types t ON t.type_id = f.type_id
        LEFT JOIN graphql_resolver_mappings rm ON rm.field_id = f.field_id
        WHERE f.is_list = 1
        AND rm.resolver_path IS NOT NULL
    """)

    for row in cursor.fetchall():
        field_name = row['field_name']
        type_name = row['type_name']
        resolver_path = row['resolver_path']
        resolver_line = row['resolver_line']
        return_type = row['return_type']

        # Check if resolver has loops in CFG
        cursor.execute("""
            SELECT cb.block_id, cb.kind, cb.start_line, cb.end_line
            FROM cfg_blocks cb
            WHERE cb.file = ?
            AND cb.start_line >= ?
            AND cb.start_line <= ? + 100
            AND cb.kind IN ('for', 'while', 'loop', 'for_each')
        """, (resolver_path, resolver_line, resolver_line))

        loop_blocks = cursor.fetchall()

        for loop in loop_blocks:
            loop_start = loop['start_line']
            loop_end = loop['end_line']

            # Check if loop contains DB queries
            cursor.execute("""
                SELECT query_text, line, command
                FROM sql_queries
                WHERE file = ?
                AND line >= ?
                AND line <= ?
            """, (resolver_path, loop_start, loop_end))

            db_queries = cursor.fetchall()

            if db_queries:
                # Found N+1 pattern - DB query inside loop for list field
                query_lines = [q['line'] for q in db_queries]

                finding = StandardFinding(
                    rule_name="graphql_nplus1",
                    message=f"Potential N+1 query in {type_name}.{field_name} resolver - DB query inside loop",
                    file_path=resolver_path,
                    line=loop_start,
                    severity=Severity.MEDIUM,
                    category="performance",
                    confidence=Confidence.MEDIUM,
                    snippet=f"Loop at lines {loop_start}-{loop_end} contains DB query at line(s): {query_lines}",
                    cwe_id="CWE-1073",  # Non-SQL Invokable Control Element with Excessive Volume of Data
                    additional_info={
                        "graphql_field": f"{type_name}.{field_name}",
                        "return_type": return_type,
                        "loop_lines": f"{loop_start}-{loop_end}",
                        "query_count": len(db_queries),
                        "query_lines": query_lines,
                        "recommendation": "Use DataLoader or batch queries to avoid N+1 pattern"
                    }
                )
                findings.append(finding)
                break  # Only report once per resolver

    conn.close()
    return findings
