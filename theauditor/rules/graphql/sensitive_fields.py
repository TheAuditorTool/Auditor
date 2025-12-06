"""GraphQL Sensitive Fields Detection.

Detects sensitive fields exposed in GraphQL schemas without proper
protection directives. Exposing password hashes, tokens, SSNs, or
other PII in the schema enables data exfiltration attacks.

CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
CWE-359: Exposure of Private Personal Information to an Unauthorized Actor
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
    name="graphql_sensitive_fields",
    category="security",
    target_extensions=[".graphql", ".gql", ".graphqls"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="graphql_fields",
)


SENSITIVE_PATTERNS = frozenset(
    [
        "password",
        "passwd",
        "pass_hash",
        "passwordhash",
        "secret",
        "secretkey",
        "secret_key",
        "token",
        "apikey",
        "api_key",
        "privatekey",
        "private_key",
        "accesstoken",
        "access_token",
        "refreshtoken",
        "refresh_token",
        "bearertoken",
        "bearer_token",
        "authtoken",
        "auth_token",
        "ssn",
        "socialsecurity",
        "social_security",
        "creditcard",
        "credit_card",
        "cardnumber",
        "card_number",
        "cvv",
        "cvc",
        "pin",
        "salt",
        "hash",
        "encryptionkey",
        "encryption_key",
        "signingkey",
        "signing_key",
        "mfasecret",
        "mfa_secret",
        "totpsecret",
        "totp_secret",
        "recoverycode",
        "recovery_code",
        "bankaccount",
        "bank_account",
        "routingnumber",
        "routing_number",
    ]
)


PROTECTION_DIRECTIVES = frozenset(
    [
        "private",
        "internal",
        "deprecated",
        "hidden",
        "sensitive",
        "redacted",
        "masked",
        "auth",
        "authenticated",
        "admin",
        "restricted",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Check for exposed sensitive fields in GraphQL schema.

    Identifies fields with sensitive names (passwords, tokens, PII)
    that lack protection directives like @private or @internal.

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
                "graphql_fields.line",
                "graphql_types.type_name",
                "graphql_types.schema_path",
            )
            .join("graphql_types", on=[("type_id", "type_id")])
            .where("graphql_types.kind = ?", "OBJECT")
        )

        for row in rows:
            field_id, field_name, line, type_name, schema_path = row

            if not field_name:
                continue

            field_lower = field_name.lower()

            is_sensitive = any(pattern in field_lower for pattern in SENSITIVE_PATTERNS)

            if not is_sensitive:
                continue

            directive_rows = db.query(
                Q("graphql_field_directives")
                .select("directive_name")
                .where("field_id = ?", field_id)
            )

            has_protection = any(
                any(prot in (directive_name or "").lower() for prot in PROTECTION_DIRECTIVES)
                for (directive_name,) in directive_rows
            )

            if not has_protection:
                findings.append(
                    StandardFinding(
                        rule_name=METADATA.name,
                        message=f"Sensitive field '{type_name}.{field_name}' exposed without protection directive",
                        file_path=schema_path or "",
                        line=line or 0,
                        severity=Severity.HIGH,
                        category=METADATA.category,
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-200",
                        additional_info={
                            "type": type_name,
                            "field": field_name,
                            "recommendation": "Remove from schema, add @private/@internal directive, or ensure resolver filters this field",
                        },
                    )
                )

        return RuleResult(findings=findings, manifest=db.get_manifest())
