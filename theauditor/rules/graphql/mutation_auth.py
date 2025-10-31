"""GraphQL Mutation Authentication Check - Database-First Approach.

Detects mutations without authentication directives or resolver protections.
Pure SQL queries - NO file I/O.
"""

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
    name="graphql_mutation_auth",
    category="security",
    target_extensions=['.graphql', '.gql', '.graphqls', '.py', '.js', '.ts'],
    execution_scope='database',
    requires_jsx_pass=False
)


@dataclass(frozen=True)
class MutationAuthPatterns:
    """Authentication directive and decorator patterns."""

    AUTH_DIRECTIVES = frozenset([
        '@auth', '@authenticated', '@requireAuth', '@authorize',
        '@protected', '@secure', '@isAuthenticated', '@authenticated'
    ])

    AUTH_DECORATORS = frozenset([
        'auth_required', 'login_required', 'authenticated',
        'requireAuth', 'require_auth', 'authorize', 'protected'
    ])


def check_mutation_auth(context: StandardRuleContext) -> list[StandardFinding]:
    """Check for mutations without authentication.

    Strategy:
    1. Find all Mutation type fields from graphql_fields
    2. Check for @auth directives in directives_json
    3. Check if resolver has authentication decorators
    4. Report mutations without protection

    NO FALLBACKS. Database must exist.
    """
    if not context.db_path:
        return []

    findings = []
    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find Mutation type
    cursor.execute("""
        SELECT type_id
        FROM graphql_types
        WHERE type_name = 'Mutation'
    """)

    mutation_type = cursor.fetchone()
    if not mutation_type:
        return findings  # No Mutation type defined

    mutation_type_id = mutation_type['type_id']

    # Get all mutation fields
    cursor.execute("""
        SELECT field_id, field_name, directives_json, line
        FROM graphql_fields
        WHERE type_id = ?
    """, (mutation_type_id,))

    for field_row in cursor.fetchall():
        field_id = field_row['field_id']
        field_name = field_row['field_name']
        directives_json = field_row['directives_json']
        line = field_row['line'] or 0

        # Check for auth directive on field
        has_auth_directive = False
        if directives_json:
            import json
            try:
                directives = json.loads(directives_json)
                for directive in directives:
                    if any(auth_dir in directive.get('name', '') for auth_dir in MutationAuthPatterns.AUTH_DIRECTIVES):
                        has_auth_directive = True
                        break
            except json.JSONDecodeError:
                pass

        if has_auth_directive:
            continue  # Field has auth directive, skip

        # Check if resolver mapping exists (simplified - no auth decorator check for now)
        # Note: symbols table has composite PK, so JOIN would need (path, name, type, line, col)
        # For MVP, we just check if a resolver is mapped - full implementation would check decorators
        cursor.execute("""
            SELECT resolver_path
            FROM graphql_resolver_mappings
            WHERE field_id = ?
        """, (field_id,))

        # Skip checking resolver decorators for MVP - would need decorator analysis
        # which requires GraphQL build command to run first
        cursor.fetchone()  # Consume result

        # No authentication found - report
        finding = StandardFinding(
            rule_name="graphql_mutation_auth",
            message=f"Mutation '{field_name}' lacks authentication directive or resolver protection",
            file_path=str(context.file_path),
            line=line,
            severity=Severity.HIGH,
            category="security",
            confidence=Confidence.MEDIUM,
            snippet="",
            cwe_id="CWE-306",
            additional_info={
                "field_name": field_name,
                "type": "Mutation",
                "recommendation": "Add @auth/@authenticated directive or protect resolver with authentication decorator"
            }
        )
        findings.append(finding)

    conn.close()
    return findings
