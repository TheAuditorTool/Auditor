"""GraphQL Sensitive Fields Check - Detect exposed sensitive data."""


import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="graphql_sensitive_fields",
    category="security",
    execution_scope='database'
)


@dataclass(frozen=True)
class SensitiveFieldPatterns:
    """Patterns for sensitive field names."""

    SENSITIVE_NAMES = frozenset([
        'password', 'secret', 'token', 'apiKey', 'api_key',
        'privateKey', 'private_key', 'accessToken', 'access_token',
        'refreshToken', 'refresh_token', 'ssn', 'social_security',
        'creditCard', 'credit_card', 'cvv', 'pin', 'salt', 'hash'
    ])


def check_sensitive_fields(context: StandardRuleContext) -> list[StandardFinding]:
    """Check for exposed sensitive fields in GraphQL schema."""
    if not context.db_path:
        return []

    findings = []
    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find fields with sensitive names in Query/public types
    cursor.execute("""
        SELECT f.field_name, t.type_name, t.schema_path, f.line, f.directives_json
        FROM graphql_types t
        JOIN graphql_fields f ON f.type_id = t.type_id
        WHERE t.kind = 'object'
    """)

    for row in cursor.fetchall():
        field_name_lower = row['field_name'].lower()

        # Check if field name contains sensitive keywords
        is_sensitive = any(sensitive in field_name_lower for sensitive in SensitiveFieldPatterns.SENSITIVE_NAMES)

        if is_sensitive:
            # Check for protection directives
            directives_json = row['directives_json']
            has_protection = False

            if directives_json:
                import json
                try:
                    directives = json.loads(directives_json)
                    for directive in directives:
                        if any(p in directive.get('name', '') for p in ['@private', '@internal', '@deprecated']):
                            has_protection = True
                            break
                except json.JSONDecodeError:
                    pass

            if not has_protection:
                finding = StandardFinding(
                    rule_name="graphql_sensitive_fields",
                    message=f"Sensitive field '{row['type_name']}.{row['field_name']}' exposed without protection directive",
                    file_path=row['schema_path'],
                    line=row['line'] or 0,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-200",
                    additional_info={
                        "type": row['type_name'],
                        "field": row['field_name'],
                        "recommendation": "Remove from schema, add @private directive, or ensure resolver filters this field"
                    }
                )
                findings.append(finding)

    conn.close()
    return findings
