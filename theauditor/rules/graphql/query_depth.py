"""GraphQL Query Depth Detection.

Detects GraphQL schemas that allow deeply nested queries without
depth limits. Unbounded nesting enables denial-of-service attacks
where attackers craft exponentially expensive queries.

CWE-400: Uncontrolled Resource Consumption
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
    name="graphql_query_depth",
    category="security",
    target_extensions=[".graphql", ".gql", ".graphqls"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="graphql_fields",
)


SCALAR_TYPES = frozenset(
    ["String", "Int", "Float", "Boolean", "ID", "DateTime", "Date", "Time", "JSON"]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Check for unrestricted query depth (DoS risk).

    Identifies list fields that return types which themselves have
    list fields, enabling recursive nesting attacks.

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
                "graphql_fields.line",
                "graphql_types.type_name",
                "graphql_types.schema_path",
            )
            .join("graphql_types", on=[("type_id", "type_id")])
            .where("graphql_fields.is_list = ?", 1)
        )

        for row in rows:
            _field_id, field_name, return_type, line, type_name, schema_path = row

            if not return_type:
                continue

            base_return_type = return_type.rstrip("!").strip("[]").rstrip("!")

            if base_return_type in SCALAR_TYPES:
                continue

            nested_rows = db.query(
                Q("graphql_types")
                .select("graphql_types.type_id")
                .where("graphql_types.type_name = ?", base_return_type)
            )

            for (nested_type_id,) in nested_rows:
                count_rows = db.query(
                    Q("graphql_fields")
                    .select("field_id")
                    .where("type_id = ?", nested_type_id)
                    .where("is_list = ?", 1)
                )
                nested_list_count = len(list(count_rows))

                if nested_list_count > 0:
                    findings.append(
                        StandardFinding(
                            rule_name=METADATA.name,
                            message=f"Field '{type_name}.{field_name}' allows nested list queries ({nested_list_count} nested list fields) - DoS risk",
                            file_path=schema_path or "",
                            line=line or 0,
                            severity=Severity.MEDIUM,
                            category=METADATA.category,
                            confidence=Confidence.HIGH,
                            cwe_id="CWE-400",
                            additional_info={
                                "field": f"{type_name}.{field_name}",
                                "return_type": return_type,
                                "nested_type": base_return_type,
                                "nested_list_fields": nested_list_count,
                                "recommendation": "Implement query depth limiting (max 5-10) and query complexity analysis",
                            },
                        )
                    )
                    break

        return RuleResult(findings=findings, manifest=db.get_manifest())
