"""AWS CDK S3 Public Access Detection - database-first rule.

Detects S3 buckets with public access in CDK code:
- Explicit public_read_access=True
- Missing block_public_access configuration
- Weak block_public_access settings (not BLOCK_ALL)
- Website hosting enabled (inherently public)
- Public ACL settings (PUBLIC_READ, PUBLIC_READ_WRITE)
- Method calls that grant public access (grant_public_access, grantPublicAccess)

CWE-732: Incorrect Permission Assignment for Critical Resource
"""

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
    target_extensions=[".py", ".ts", ".js"],
    exclude_patterns=[
        "test/",
        "__tests__/",
        ".pf/",
        ".auditor_venv/",
        "node_modules/",
    ],
    execution_scope="database",
    primary_table="cdk_constructs",
)

PUBLIC_ACLS = frozenset(
    [
        "PUBLIC_READ",
        "PUBLIC_READ_WRITE",
        "AUTHENTICATED_READ",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect S3 buckets with public access enabled in CDK code.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_public_read_access(db))
        findings.extend(_check_missing_block_public_access(db))
        findings.extend(_check_weak_block_public_access(db))
        findings.extend(_check_website_hosting(db))
        findings.extend(_check_public_acl(db))
        findings.extend(_check_public_access_methods(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_public_read_access(db: RuleDB) -> list[StandardFinding]:
    """Detect S3 buckets with explicit public_read_access=True using JOIN.

    O(1) query replacing N+1 loop pattern.
    """
    findings: list[StandardFinding] = []

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
        display_name = construct_name or "UnnamedBucket"
        findings.append(
            StandardFinding(
                rule_name="aws-cdk-s3-public-read",
                message=f"S3 bucket '{display_name}' has public read access enabled",
                severity=Severity.CRITICAL,
                confidence="high",
                file_path=file_path,
                line=line,
                snippet="public_read_access=True",
                category="public_exposure",
                cwe_id="CWE-732",
                additional_info={
                    "construct_id": construct_id,
                    "construct_name": display_name,
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
    findings: list[StandardFinding] = []

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

    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id")
        .where(
            "property_name IN (?, ?)",
            "block_public_access",
            "blockPublicAccess",
        )
    )

    configured_ids = {row[0] for row in configured_rows}

    for construct_id, file_path, line, construct_name in all_buckets:
        if construct_id in configured_ids:
            continue

        display_name = construct_name or "UnnamedBucket"
        findings.append(
            StandardFinding(
                rule_name="aws-cdk-s3-missing-block-public-access",
                message=f"S3 bucket '{display_name}' missing block_public_access configuration",
                severity=Severity.HIGH,
                confidence="high",
                file_path=file_path,
                line=line,
                snippet=f"s3.Bucket(self, '{display_name}', ...)",
                category="missing_security_control",
                cwe_id="CWE-732",
                additional_info={
                    "construct_id": construct_id,
                    "construct_name": display_name,
                    "remediation": "Add block_public_access=s3.BlockPublicAccess.BLOCK_ALL to prevent accidental public exposure.",
                },
            )
        )

    return findings


def _check_weak_block_public_access(db: RuleDB) -> list[StandardFinding]:
    """Detect S3 buckets with block_public_access that isn't BLOCK_ALL.

    Some configurations only partially block public access, leaving gaps.
    BLOCK_ALL is the only fully secure option.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select(
            "cdk_constructs.construct_id",
            "cdk_constructs.file_path",
            "cdk_constructs.construct_name",
            "cdk_construct_properties.property_value_expr",
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
            "block_public_access",
            "blockPublicAccess",
        )
    )

    for construct_id, file_path, construct_name, prop_value, line in rows:
        if "BLOCK_ALL" in prop_value:
            continue

        display_name = construct_name or "UnnamedBucket"
        findings.append(
            StandardFinding(
                rule_name="aws-cdk-s3-weak-block-public-access",
                message=f"S3 bucket '{display_name}' has block_public_access but not BLOCK_ALL",
                severity=Severity.MEDIUM,
                confidence="high",
                file_path=file_path,
                line=line,
                snippet=f"block_public_access={prop_value}",
                category="weak_security_control",
                cwe_id="CWE-732",
                additional_info={
                    "construct_id": construct_id,
                    "construct_name": display_name,
                    "current_setting": prop_value,
                    "remediation": "Use block_public_access=s3.BlockPublicAccess.BLOCK_ALL for complete protection.",
                },
            )
        )

    return findings


def _check_website_hosting(db: RuleDB) -> list[StandardFinding]:
    """Detect S3 buckets configured for static website hosting.

    Website hosting makes bucket contents publicly accessible by design.
    This is often intentional, but should be flagged for review.
    """
    findings: list[StandardFinding] = []

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
            "cdk_construct_properties.property_name IN (?, ?, ?, ?)",
            "website_index_document",
            "websiteIndexDocument",
            "website_redirect",
            "websiteRedirect",
        )
    )

    seen_constructs = set()

    for construct_id, file_path, construct_name, line in rows:
        if construct_id in seen_constructs:
            continue
        seen_constructs.add(construct_id)

        display_name = construct_name or "UnnamedBucket"
        findings.append(
            StandardFinding(
                rule_name="aws-cdk-s3-website-hosting",
                message=f"S3 bucket '{display_name}' configured for static website hosting (publicly accessible)",
                severity=Severity.MEDIUM,
                confidence="high",
                file_path=file_path,
                line=line,
                snippet="website_index_document or website_redirect configured",
                category="public_exposure",
                cwe_id="CWE-732",
                additional_info={
                    "construct_id": construct_id,
                    "construct_name": display_name,
                    "remediation": "If public access is intentional, ensure no sensitive data is stored. Consider using CloudFront with OAI/OAC for better access control.",
                },
            )
        )

    return findings


def _check_public_acl(db: RuleDB) -> list[StandardFinding]:
    """Detect S3 buckets with public ACL settings.

    PUBLIC_READ, PUBLIC_READ_WRITE, and AUTHENTICATED_READ ACLs
    make bucket contents accessible to unauthorized users.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select(
            "cdk_constructs.construct_id",
            "cdk_constructs.file_path",
            "cdk_constructs.construct_name",
            "cdk_construct_properties.property_value_expr",
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
            "access_control",
            "accessControl",
        )
    )

    for construct_id, file_path, construct_name, prop_value, line in rows:
        for acl in PUBLIC_ACLS:
            if acl in prop_value:
                display_name = construct_name or "UnnamedBucket"
                severity = Severity.CRITICAL if "WRITE" in acl else Severity.HIGH
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-s3-public-acl",
                        message=f"S3 bucket '{display_name}' has public ACL: {acl}",
                        severity=severity,
                        confidence="high",
                        file_path=file_path,
                        line=line,
                        snippet=f"access_control={prop_value}",
                        category="public_exposure",
                        cwe_id="CWE-732",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "acl_setting": acl,
                            "remediation": "Use access_control=s3.BucketAccessControl.PRIVATE and implement bucket policies for controlled access.",
                        },
                    )
                )
                break

    return findings


def _check_public_access_methods(db: RuleDB) -> list[StandardFinding]:
    """Detect method calls that grant public access after bucket initialization.

    Uses single query + Python filtering instead of 4 leading-wildcard queries.
    """
    findings: list[StandardFinding] = []

    public_grant_methods = frozenset({
        "grant_public_access",
        "grantPublicAccess",
        "grant_read",
        "grantRead",
    })

    critical_methods = frozenset({"grant_public_access", "grantPublicAccess"})

    # Single query to get all function calls - filter in Python
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
    )

    for file_path, line, callee, args in rows:
        if not callee:
            continue

        # Extract method name from callee (e.g., "bucket.grant_public_access" -> "grant_public_access")
        method_name = callee.rsplit(".", 1)[-1] if "." in callee else callee

        if method_name not in public_grant_methods:
            continue

        is_public_grant = method_name in critical_methods

        if not is_public_grant:
            args_lower = (args or "").lower()
            if "anyone" not in args_lower and "*" not in args_lower:
                continue

        severity = Severity.CRITICAL if is_public_grant else Severity.HIGH

        findings.append(
            StandardFinding(
                rule_name="aws-cdk-s3-public-grant-method",
                message=f"S3 bucket method call '{callee}' grants public access",
                severity=severity,
                confidence="high",
                file_path=file_path,
                line=line,
                snippet=f"{callee}({args or ''})" if args else f"{callee}()",
                category="public_exposure",
                cwe_id="CWE-732",
                additional_info={
                    "method": callee,
                    "remediation": "Remove public grant method call. Use bucket policies with specific principals instead of granting public access.",
                },
            )
        )

    return findings
