"""GraphQL Mutation Authentication Detection.

Detects GraphQL mutations that lack authentication directives or
resolver protection. Unprotected mutations allow unauthorized users
to modify data, leading to privilege escalation and data tampering.

CWE-306: Missing Authentication for Critical Function
CWE-862: Missing Authorization
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
    name="graphql_mutation_auth",
    category="security",
    target_extensions=[".graphql", ".gql", ".graphqls", ".py", ".js", ".ts"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="graphql_fields",
)


AUTH_DIRECTIVES = frozenset(
    [
        "auth",
        "authenticated",
        "requireauth",
        "require_auth",
        "authorize",
        "authorized",
        "protected",
        "secure",
        "isauthenticated",
        "is_authenticated",
        "login_required",
        "permission",
        "role",
        "hasrole",
        "has_role",
    ]
)


PUBLIC_MUTATIONS = frozenset(
    [
        "login",
        "signin",
        "sign_in",
        "signup",
        "sign_up",
        "register",
        "createaccount",
        "create_account",
        "forgotpassword",
        "forgot_password",
        "resetpassword",
        "reset_password",
        "verifyemail",
        "verify_email",
        "refreshtoken",
        "refresh_token",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Check for mutations without authentication.

    Identifies GraphQL mutation fields that lack authentication
    directives like @auth, @authenticated, @protected, etc.

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
                "graphql_types.schema_path",
            )
            .join("graphql_types", on=[("type_id", "type_id")])
            .where("graphql_types.type_name = ?", "Mutation")
        )

        for row in rows:
            field_id, field_name, line, schema_path = row

            if field_name and field_name.lower() in PUBLIC_MUTATIONS:
                continue

            directive_rows = db.query(
                Q("graphql_field_directives")
                .select("directive_name")
                .where("field_id = ?", field_id)
            )

            has_auth_directive = any(
                any(auth in (directive_name or "").lower() for auth in AUTH_DIRECTIVES)
                for (directive_name,) in directive_rows
            )

            if has_auth_directive:
                continue

            resolver_rows = db.query(
                Q("graphql_resolver_mappings")
                .select("resolver_path", "resolver_line")
                .where("field_id = ?", field_id)
            )

            resolver_protected = False
            for resolver_path, resolver_line in resolver_rows:
                if not resolver_path:
                    continue

                decorator_rows = db.query(
                    Q("function_call_args")
                    .select("callee_function")
                    .where("file = ?", resolver_path)
                    .where("line >= ?", max(1, resolver_line - 5))
                    .where("line <= ?", resolver_line)
                )
                for (callee,) in decorator_rows:
                    if callee and any(auth in callee.lower() for auth in AUTH_DIRECTIVES):
                        resolver_protected = True
                        break
                if resolver_protected:
                    break

            if resolver_protected:
                continue

            manual_auth_found = False
            for resolver_path, resolver_line in resolver_rows:
                if not resolver_path:
                    continue

                condition_rows = db.query(
                    Q("cfg_blocks")
                    .select("condition")
                    .where("file = ?", resolver_path)
                    .where("start_line >= ?", resolver_line)
                    .where("start_line <= ?", resolver_line + 50)
                    .where("block_type = ?", "if")
                )
                for (condition,) in condition_rows:
                    if condition:
                        cond_lower = condition.lower()

                        if any(
                            auth_var in cond_lower
                            for auth_var in [
                                "context.user",
                                "request.user",
                                "current_user",
                                "is_authenticated",
                                "user.is_authenticated",
                                "not user",
                                "not context.user",
                                "not request.user",
                                "user is none",
                                "user == none",
                                "user is not none",
                                ".has_permission",
                                ".is_staff",
                                ".is_superuser",
                            ]
                        ):
                            manual_auth_found = True
                            break
                if manual_auth_found:
                    break

            if manual_auth_found:
                continue

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Mutation '{field_name}' lacks authentication directive or resolver protection",
                    file_path=schema_path or "",
                    line=line or 0,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-306",
                    additional_info={
                        "mutation": field_name,
                        "recommendation": "Add @auth, @authenticated, or @protected directive, or protect resolver with authentication decorator",
                    },
                )
            )

        return RuleResult(findings=findings, manifest=db.get_manifest())
