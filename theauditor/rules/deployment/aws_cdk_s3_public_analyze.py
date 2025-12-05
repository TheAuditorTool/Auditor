"""AWS CDK S3 Public Access Detection - database-first rule."""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="aws_cdk_s3_public",
    category="deployment",
    target_extensions=[],
    exclude_patterns=[
        "test/",
        "__tests__/",
        ".pf/",
        ".auditor_venv/",
    ],
    execution_scope="database",
    primary_table="cdk_constructs",
)


def find_cdk_s3_issues(context: StandardRuleContext) -> RuleResult:
    """Detect S3 buckets with public access enabled in CDK code."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_public_read_access(db))
        findings.extend(_check_missing_block_public_access(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_public_read_access(db: RuleDB) -> list[StandardFinding]:
    """Detect S3 buckets with explicit public_read_access=True using JOIN.

    O(1) query replacing N+1 loop pattern.
    """
    findings = []

    # Single JOIN query: constructs + properties filtered in SQL
    rows = db.query(
        Q("cdk_constructs")
        .select(
            "cdk_constructs.construct_id",
            "cdk_constructs.file_path",
            "cdk_constructs.construct_name",
            "cdk_construct_properties.line",
        )
        .join("cdk_construct_properties", on=[("construct_id", "construct_id")])
        .where(
            "cdk_constructs.cdk_class LIKE ? AND (cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?)",
            "%Bucket%",
            "%s3%",
            "%aws_s3%",
        )
        .where(
            "cdk_construct_properties.property_name IN (?, ?)",
            "public_read_access",
            "publicReadAccess",
        )
        .where("LOWER(cdk_construct_properties.property_value_expr) = ?", "true")
    )

    for construct_id, file_path, construct_name, line in rows:
        name = construct_name or "UnnamedBucket"
        findings.append(
            StandardFinding(
                rule_name="aws-cdk-s3-public-read",
                message=f"S3 bucket '{name}' has public read access enabled",
                severity=Severity.CRITICAL,
                confidence="high",
                file_path=file_path,
                line=line,
                snippet="public_read_access=True",
                category="public_exposure",
                cwe_id="CWE-732",
                additional_info={
                    "construct_id": construct_id,
                    "construct_name": name,
                    "remediation": "Remove public_read_access=True or set to False. Use bucket policies with specific principals instead.",
                },
            )
        )

    return findings


def _check_missing_block_public_access(db: RuleDB) -> list[StandardFinding]:
    """Detect S3 buckets missing block_public_access via set difference.

    Query 1: All S3 Buckets
    Query 2: Constructs with block_public_access property
    Result: Buckets - Configured = Vulnerable
    """
    findings = []

    # Query 1: Get ALL S3 Buckets
    all_buckets = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "cdk_class LIKE ? AND (cdk_class LIKE ? OR cdk_class LIKE ?)",
            "%Bucket%",
            "%s3%",
            "%aws_s3%",
        )
    )

    if not all_buckets:
        return []

    # Query 2: Get construct_ids that HAVE block_public_access property
    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id")
        .where(
            "property_name IN (?, ?)",
            "block_public_access",
            "blockPublicAccess",
        )
    )

    # O(1) lookup set
    configured_ids = {row[0] for row in configured_rows}

    # Set difference: Buckets without block_public_access
    for construct_id, file_path, line, construct_name in all_buckets:
        if construct_id in configured_ids:
            continue

        name = construct_name or "UnnamedBucket"
        findings.append(
            StandardFinding(
                rule_name="aws-cdk-s3-missing-block-public-access",
                message=f"S3 bucket '{name}' missing block_public_access configuration",
                severity=Severity.HIGH,
                confidence="high",
                file_path=file_path,
                line=line,
                snippet=f"s3.Bucket(self, '{name}', ...)",
                category="missing_security_control",
                cwe_id="CWE-732",
                additional_info={
                    "construct_id": construct_id,
                    "construct_name": name,
                    "remediation": "Add block_public_access=s3.BlockPublicAccess.BLOCK_ALL to prevent accidental public exposure.",
                },
            )
        )

    return findings
