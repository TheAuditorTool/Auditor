"""GraphQL N+1 Query Detection.

Detects N+1 query patterns in GraphQL resolvers where database queries
execute inside loops. This is a common performance anti-pattern that
causes query count to scale linearly with result set size.

CWE-1073: Non-SQL Invocation of SQL-Stored Procedure
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
    name="graphql_nplus1",
    category="performance",
    target_extensions=[".graphql", ".gql", ".graphqls", ".py", ".js", ".ts"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="graphql_resolver_mappings",
)


LOOP_BLOCK_TYPES = frozenset(["for", "while", "loop", "for_each", "foreach", "for_of", "for_in"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect N+1 query patterns in GraphQL resolvers.

    Identifies list-returning fields where the resolver contains
    loops with database queries inside, indicating potential N+1 issues.

    Args:
        context: Rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        rows = db.query(
            Q("graphql_fields")
            .select(
                "graphql_fields.field_id",
                "graphql_fields.field_name",
                "graphql_fields.return_type",
                "graphql_types.type_name",
                "graphql_resolver_mappings.resolver_path",
                "graphql_resolver_mappings.resolver_line",
            )
            .join("graphql_types", on=[("type_id", "type_id")])
            .join("graphql_resolver_mappings", on=[("field_id", "field_id")], join_type="LEFT")
            .where("graphql_fields.is_list = ?", 1)
            .where("graphql_resolver_mappings.resolver_path IS NOT NULL")
        )

        for row in rows:
            _field_id, field_name, return_type, type_name, resolver_path, resolver_line = row

            if not resolver_path or not resolver_line:
                continue

            loop_rows = db.query(
                Q("cfg_blocks")
                .select("id", "block_type", "start_line", "end_line")
                .where("file = ?", resolver_path)
                .where("start_line >= ?", resolver_line)
                .where("start_line <= ?", resolver_line + 100)
            )

            for loop_row in loop_rows:
                _block_id, block_type, loop_start, loop_end = loop_row

                if not block_type or block_type.lower() not in LOOP_BLOCK_TYPES:
                    continue

                if not loop_start or not loop_end:
                    continue

                query_rows = db.query(
                    Q("sql_queries")
                    .select("query_text", "line_number", "command")
                    .where("file_path = ?", resolver_path)
                    .where("line_number >= ?", loop_start)
                    .where("line_number <= ?", loop_end)
                )

                db_queries = [
                    q
                    for q in query_rows
                    if q[0] and " in (" not in q[0].lower() and " in(" not in q[0].lower()
                ]
                if db_queries:
                    query_lines = [q[1] for q in db_queries]

                    findings.append(
                        StandardFinding(
                            rule_name=METADATA.name,
                            message=f"N+1 query pattern in {type_name}.{field_name} resolver - DB query inside loop",
                            file_path=resolver_path,
                            line=loop_start,
                            severity=Severity.MEDIUM,
                            category=METADATA.category,
                            confidence=Confidence.MEDIUM,
                            snippet=f"Loop at lines {loop_start}-{loop_end} contains DB queries at: {query_lines}",
                            cwe_id="CWE-1073",
                            additional_info={
                                "graphql_field": f"{type_name}.{field_name}",
                                "return_type": return_type,
                                "loop_type": block_type,
                                "loop_lines": f"{loop_start}-{loop_end}",
                                "query_count": len(db_queries),
                                "query_lines": query_lines,
                                "recommendation": "Use DataLoader or batch queries to avoid N+1 pattern",
                            },
                        )
                    )
                    break

        return RuleResult(findings=findings, manifest=db.get_manifest())
