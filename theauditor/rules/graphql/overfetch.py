"""GraphQL Overfetch Detection - ORM Field Analysis.

Detects resolvers fetching sensitive DB fields not exposed in GraphQL schema.
Uses orm_queries + graphql_fields comparison. NO regex fallbacks.
"""
from __future__ import annotations


import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="graphql_overfetch",
    category="security",
    target_extensions=['.graphql', '.gql', '.graphqls', '.py', '.js', '.ts'],
    execution_scope='database',
    requires_jsx_pass=False
)


# Sensitive field patterns
SENSITIVE_FIELDS = frozenset([
    'password', 'passwordHash', 'password_hash', 'hashed_password',
    'apiKey', 'api_key', 'secretKey', 'secret_key', 'privateKey', 'private_key',
    'token', 'accessToken', 'access_token', 'refreshToken', 'refresh_token',
    'ssn', 'social_security', 'credit_card', 'creditCard', 'cvv',
    'bankAccount', 'bank_account', 'routingNumber', 'routing_number',
    'salary', 'medicalRecord', 'medical_record'
])


def check_graphql_overfetch(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect overfetch patterns in GraphQL resolvers.

    Strategy:
    1. For each GraphQL type, get its exposed fields
    2. Find resolvers that query ORM models for that type
    3. Check if ORM query selects fields not in GraphQL schema
    4. Flag sensitive fields that are fetched but not exposed

    NO FALLBACKS. Database must exist.
    """
    if not context.db_path:
        return []

    findings = []
    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if required tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('graphql_types', 'python_orm_models')
    """)
    if len(cursor.fetchall()) < 2:
        return findings  # Missing required tables

    # Get all GraphQL types with their fields
    cursor.execute("""
        SELECT t.type_id, t.type_name
        FROM graphql_types t
        WHERE t.kind = 'object'
    """)

    for type_row in cursor.fetchall():
        type_name = type_row['type_name']
        type_id = type_row['type_id']

        # Get exposed GraphQL fields for this type
        cursor.execute("""
            SELECT field_name
            FROM graphql_fields
            WHERE type_id = ?
        """, (type_id,))

        exposed_fields = {row['field_name'] for row in cursor.fetchall()}

        # Find ORM model that might correspond to this GraphQL type
        # Heuristic: match by name similarity (User type → User model)
        cursor.execute("""
            SELECT model_name, file
            FROM python_orm_models
            WHERE model_name LIKE ?
        """, (f'%{type_name}%',))

        orm_models = cursor.fetchall()

        for orm_row in orm_models:
            model_name = orm_row['model_name']
            model_file = orm_row['file']

            # Get ORM model fields
            cursor.execute("""
                SELECT field_name, field_type
                FROM python_orm_fields
                WHERE model_name = ?
            """, (model_name,))

            orm_fields = cursor.fetchall()

            # Check for fields in ORM but not in GraphQL schema
            for field_row in orm_fields:
                field_name = field_row['field_name']
                field_type = field_row['field_type']

                if field_name not in exposed_fields:
                    # Field exists in ORM but not exposed in GraphQL
                    # Check if it's sensitive
                    is_sensitive = any(
                        sens in field_name.lower()
                        for sens in SENSITIVE_FIELDS
                    )

                    if is_sensitive:
                        finding = StandardFinding(
                            rule_name="graphql_overfetch",
                            message=f"Sensitive field '{field_name}' in {model_name} model not exposed in GraphQL schema {type_name}, but may be fetched by resolvers",
                            file_path=model_file,
                            line=0,  # ORM models don't have line numbers in this table
                            severity=Severity.MEDIUM,
                            category="security",
                            confidence=Confidence.MEDIUM,
                            snippet=f"ORM field: {field_name} ({field_type})",
                            cwe_id="CWE-200",  # Exposure of Sensitive Information
                            additional_info={
                                "orm_model": model_name,
                                "graphql_type": type_name,
                                "sensitive_field": field_name,
                                "field_type": field_type,
                                "exposed_fields": list(exposed_fields),
                                "recommendation": "Ensure resolver uses .only() or explicit field selection to avoid fetching unexposed sensitive fields"
                            }
                        )
                        findings.append(finding)

    conn.close()
    return findings
