"""GraphQL Injection Detection - Database-First Taint Analysis.

Detects GraphQL arguments flowing to SQL queries without parameterization.
Traces from GraphQL schema field arguments through resolver functions to
SQL query construction, flagging string interpolation patterns.

CWE-89: SQL Injection
CWE-943: Improper Neutralization of Special Elements in Data Query Logic
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
    name="graphql_injection",
    category="security",
    target_extensions=[".graphql", ".gql", ".graphqls", ".py", ".js", ".ts"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="graphql_resolver_mappings",
)


SQL_INJECTION_PATTERNS = (
    ".format(",
    'f"',
    "f'",
    "${",
    "`${",
    '" % ',
    "' % ",
    '" +',
    "' +",
    '+ "',
    "+ '",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect GraphQL injection via taint analysis.

    Traces GraphQL field arguments through resolvers to SQL queries,
    detecting unsafe string interpolation patterns.

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
            Q("graphql_field_args")
            .select(
                "graphql_field_args.arg_name",
                "graphql_field_args.arg_type",
                "graphql_field_args.field_id",
                "graphql_fields.field_name",
                "graphql_types.type_name",
                "graphql_resolver_mappings.resolver_path",
                "graphql_resolver_mappings.resolver_line",
            )
            .join("graphql_fields", on=[("field_id", "field_id")])
            .join("graphql_types", on="graphql_fields.type_id = graphql_types.type_id")
            .join("graphql_resolver_mappings", on=[("field_id", "field_id")], join_type="LEFT")
            .where("graphql_resolver_mappings.resolver_path IS NOT NULL")
        )

        for row in rows:
            arg_name, arg_type, _field_id, field_name, type_name, resolver_path, resolver_line = row

            sql_rows = db.query(
                Q("sql_queries")
                .select("query_text", "line_number", "command")
                .where("file_path = ?", resolver_path)
                .where("line_number > ?", resolver_line)
                .where("line_number < ?", resolver_line + 50)
            )

            for sql_row in sql_rows:
                query_text, query_line, command = sql_row

                if not query_text:
                    continue

                if not any(pattern in query_text for pattern in SQL_INJECTION_PATTERNS):
                    continue

                arg_rows = db.query(
                    Q("function_call_args")
                    .select("argument_expr")
                    .where("file = ?", resolver_path)
                    .where("line >= ?", resolver_line)
                    .where("line <= ?", query_line)
                )

                arg_in_context = any(expr and arg_name in expr for (expr,) in arg_rows)

                if arg_in_context:
                    findings.append(
                        StandardFinding(
                            rule_name=METADATA.name,
                            message=f"GraphQL argument '{arg_name}' from {type_name}.{field_name} flows to SQL query without parameterization",
                            file_path=resolver_path,
                            line=query_line,
                            severity=Severity.CRITICAL,
                            category=METADATA.category,
                            confidence=Confidence.HIGH,
                            snippet=query_text[:200] if len(query_text) > 200 else query_text,
                            cwe_id="CWE-89",
                            additional_info={
                                "graphql_field": f"{type_name}.{field_name}",
                                "argument": arg_name,
                                "argument_type": arg_type,
                                "sql_command": command,
                                "recommendation": "Use parameterized queries instead of string interpolation",
                            },
                        )
                    )

        return RuleResult(findings=findings, manifest=db.get_manifest())
