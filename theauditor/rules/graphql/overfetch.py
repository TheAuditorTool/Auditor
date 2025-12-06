"""GraphQL Overfetch Detection.

Detects when GraphQL resolvers may fetch sensitive ORM fields that are
not exposed in the schema. Even if a field isn't in the GraphQL type,
the resolver might load the entire model, exposing sensitive data in
memory or logs.

CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
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
    name="graphql_overfetch",
    category="security",
    target_extensions=[".graphql", ".gql", ".graphqls", ".py", ".js", ".ts"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="graphql_types",
)


SENSITIVE_FIELD_PATTERNS = frozenset(
    [
        "password",
        "passwordhash",
        "password_hash",
        "hashed_password",
        "passhash",
        "pass_hash",
        "apikey",
        "api_key",
        "secretkey",
        "secret_key",
        "privatekey",
        "private_key",
        "token",
        "accesstoken",
        "access_token",
        "refreshtoken",
        "refresh_token",
        "bearertoken",
        "bearer_token",
        "authtoken",
        "auth_token",
        "ssn",
        "social_security",
        "socialsecurity",
        "creditcard",
        "credit_card",
        "cardnumber",
        "card_number",
        "cvv",
        "cvc",
        "bankaccount",
        "bank_account",
        "accountnumber",
        "account_number",
        "routingnumber",
        "routing_number",
        "salary",
        "income",
        "medicalrecord",
        "medical_record",
        "healthrecord",
        "health_record",
        "diagnosis",
        "prescription",
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
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect overfetch patterns in GraphQL resolvers.

    Identifies cases where ORM models have sensitive fields that are
    not exposed in the corresponding GraphQL type, but could be
    fetched by resolvers loading full model instances.

    Args:
        context: Rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        type_rows = db.query(
            Q("graphql_types")
            .select("type_id", "type_name", "schema_path")
            .where("kind = ?", "OBJECT")
        )

        for type_row in type_rows:
            type_id, type_name, _schema_path = type_row

            if not type_name:
                continue

            field_rows = db.query(
                Q("graphql_fields").select("field_name").where("type_id = ?", type_id)
            )
            exposed_fields = {row[0].lower() for row in field_rows if row[0]}

            resolver_rows = db.query(
                Q("graphql_resolver_mappings")
                .select("resolver_path", "resolver_line")
                .where("type_id = ?", type_id)
            )

            has_field_selection = False
            for resolver_path, resolver_line in resolver_rows:
                if not resolver_path:
                    continue

                selection_rows = db.query(
                    Q("function_call_args")
                    .select("callee_function")
                    .where("file = ?", resolver_path)
                    .where("line >= ?", resolver_line)
                    .where("line <= ?", resolver_line + 50)
                )
                for (callee,) in selection_rows:
                    if callee and any(
                        method in callee.lower()
                        for method in [
                            ".only(",
                            ".defer(",
                            ".values(",
                            ".values_list(",
                            ".select(",
                            ".select_related(",
                            ".prefetch_related(",
                        ]
                    ):
                        has_field_selection = True
                        break
                if has_field_selection:
                    break

            if has_field_selection:
                continue

            orm_rows = db.query(
                Q("python_orm_models")
                .select("model_name", "file", "line")
                .where("model_name LIKE ?", f"%{type_name}%")
            )

            for orm_row in orm_rows:
                model_name, model_file, model_line = orm_row

                if not model_name:
                    continue

                orm_field_rows = db.query(
                    Q("python_orm_fields")
                    .select("field_name", "field_type", "line")
                    .where("model_name = ?", model_name)
                )

                for orm_field_row in orm_field_rows:
                    field_name, field_type, field_line = orm_field_row

                    if not field_name:
                        continue

                    field_lower = field_name.lower()

                    if field_lower in exposed_fields:
                        continue

                    is_sensitive = any(
                        pattern in field_lower for pattern in SENSITIVE_FIELD_PATTERNS
                    )

                    if is_sensitive:
                        findings.append(
                            StandardFinding(
                                rule_name=METADATA.name,
                                message=f"Sensitive ORM field '{field_name}' in {model_name} not exposed in GraphQL type {type_name}, but may be overfetched by resolvers",
                                file_path=model_file or "",
                                line=field_line or model_line or 0,
                                severity=Severity.MEDIUM,
                                category=METADATA.category,
                                confidence=Confidence.MEDIUM,
                                snippet=f"ORM field: {field_name} ({field_type or 'unknown type'})",
                                cwe_id="CWE-200",
                                additional_info={
                                    "orm_model": model_name,
                                    "graphql_type": type_name,
                                    "sensitive_field": field_name,
                                    "field_type": field_type,
                                    "recommendation": "Use .only() or explicit field selection in resolver to avoid fetching sensitive fields",
                                },
                            )
                        )

        return RuleResult(findings=findings, manifest=db.get_manifest())
