"""GraphQL Input Validation Check."""


import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="graphql_input_validation",
    category="security",
    execution_scope='database'
)


def check_input_validation(context: StandardRuleContext) -> list[StandardFinding]:
    """Check for missing input validation on mutation arguments."""
    if not context.db_path:
        return []

    findings = []
    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find Mutation fields with String/custom input args (no validation directives)
    cursor.execute("""
        SELECT f.field_name, fa.arg_name, fa.arg_type, fa.directives_json,
               t.schema_path, f.line
        FROM graphql_types t
        JOIN graphql_fields f ON f.type_id = t.type_id
        JOIN graphql_field_args fa ON fa.field_id = f.field_id
        WHERE t.type_name = 'Mutation'
          AND (fa.arg_type LIKE '%String%' OR fa.arg_type LIKE 'Input%')
          AND fa.is_nullable = 1
    """)

    for row in cursor.fetchall():
        directives_json = row['directives_json']

        # Check for validation directives
        has_validation = False
        if directives_json:
            import json
            try:
                directives = json.loads(directives_json)
                for directive in directives:
                    if any(v in directive.get('name', '') for v in ['@constraint', '@validate', '@length', '@pattern']):
                        has_validation = True
                        break
            except json.JSONDecodeError:
                pass

        if not has_validation:
            finding = StandardFinding(
                rule_name="graphql_input_validation",
                message=f"Mutation argument '{row['field_name']}.{row['arg_name']}' lacks validation directives",
                file_path=row['schema_path'],
                line=row['line'] or 0,
                severity=Severity.MEDIUM,
                category="security",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-20",
                additional_info={
                    "mutation": row['field_name'],
                    "argument": row['arg_name'],
                    "type": row['arg_type'],
                    "recommendation": "Add @constraint/@validate directives or implement input validation in resolver"
                }
            )
            findings.append(finding)

    conn.close()
    return findings
