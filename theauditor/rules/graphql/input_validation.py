"""GraphQL Input Validation Detection.

Detects GraphQL mutation arguments that accept user input without
proper validation directives. Missing validation on nullable String
or Input types in mutations is a common source of injection and
data integrity issues.

CWE-20: Improper Input Validation
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
    name="graphql_input_validation",
    category="security",
    target_extensions=[".graphql", ".gql", ".graphqls"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="graphql_field_args",
)


VALIDATION_DIRECTIVES = frozenset(
    [
        "constraint",
        "validate",
        "length",
        "pattern",
        "size",
        "range",
        "min",
        "max",
        "email",
        "url",
        "uuid",
        "regex",
    ]
)


REQUIRES_VALIDATION_TYPES = ("String", "Input", "ID")


VALIDATION_LIBRARIES = frozenset(
    [
        "zod",
        "yup",
        "joi",
        "ajv",
        "class-validator",
        "io-ts",
        "pydantic",
        "marshmallow",
        "cerberus",
        "voluptuous",
        "colander",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Check for missing input validation on mutation arguments.

    Identifies nullable String/Input type arguments on Mutation fields
    that lack validation directives like @constraint, @validate, etc.

    Args:
        context: Rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        files_with_validation = set()
        import_rows = db.query(Q("import_styles").select("file", "package"))
        for file_path, package in import_rows:
            if package and any(lib in package.lower() for lib in VALIDATION_LIBRARIES):
                files_with_validation.add(file_path)

        rows = db.query(
            Q("graphql_field_args")
            .select(
                "graphql_field_args.field_id",
                "graphql_field_args.arg_name",
                "graphql_field_args.arg_type",
                "graphql_fields.field_name",
                "graphql_fields.line",
                "graphql_types.schema_path",
                "graphql_types.type_name",
            )
            .join("graphql_fields", on=[("field_id", "field_id")])
            .join("graphql_types", on="graphql_fields.type_id = graphql_types.type_id")
            .where("graphql_types.type_name = ?", "Mutation")
            .where("graphql_field_args.is_nullable = ?", 1)
        )

        for row in rows:
            field_id, arg_name, arg_type, field_name, line, schema_path, _type_name = row

            if not arg_type:
                continue
            if not any(t in arg_type for t in REQUIRES_VALIDATION_TYPES):
                continue

            directive_rows = db.query(
                Q("graphql_arg_directives")
                .select("directive_name")
                .where("field_id = ?", field_id)
                .where("arg_name = ?", arg_name)
            )

            has_validation = any(
                any(v in (directive_name or "").lower() for v in VALIDATION_DIRECTIVES)
                for (directive_name,) in directive_rows
            )

            if has_validation:
                continue

            resolver_rows = db.query(
                Q("graphql_resolver_mappings")
                .select("resolver_path")
                .where("field_id = ?", field_id)
            )
            resolver_has_validation = any(
                resolver_path in files_with_validation
                for (resolver_path,) in resolver_rows
                if resolver_path
            )

            if resolver_has_validation:
                continue

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Mutation argument '{field_name}.{arg_name}' ({arg_type}) lacks validation directives",
                    file_path=schema_path,
                    line=line or 0,
                    severity=Severity.MEDIUM,
                    category=METADATA.category,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-20",
                    additional_info={
                        "mutation": field_name,
                        "argument": arg_name,
                        "type": arg_type,
                        "recommendation": "Add @constraint, @validate, @length, or @pattern directive to enforce input validation",
                    },
                )
            )

        return RuleResult(findings=findings, manifest=db.get_manifest())
