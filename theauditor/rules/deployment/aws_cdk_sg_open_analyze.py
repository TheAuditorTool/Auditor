"""AWS CDK Security Group Detection - database-first rule.

Detects overly permissive security groups in CDK code:
- Unrestricted ingress from 0.0.0.0/0 (IPv4 any)
- Unrestricted ingress from ::/0 (IPv6 any)
- allow_all_outbound=True (informational)

CWE-284: Improper Access Control
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
    name="aws_cdk_security_groups",
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


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect overly permissive security groups in CDK code.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_unrestricted_ingress(db))
        findings.extend(_check_allow_all_outbound(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_unrestricted_ingress(db: RuleDB) -> list[StandardFinding]:
    """Detect security groups allowing unrestricted ingress (0.0.0.0/0 or ::/0).

    Note: This flags all instances of 0.0.0.0/0 ingress. In practice, load balancers
    and public-facing services legitimately need this on specific ports (80, 443).
    Review findings in context of the service's purpose.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "SecurityGroup" in cdk_class
            and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedSecurityGroup"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        for prop_name, property_value, prop_line in prop_rows:
            if "0.0.0.0/0" in property_value or "Peer.anyIpv4" in property_value:
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-sg-unrestricted-ingress-ipv4",
                        message=f"Security group '{display_name}' allows unrestricted ingress from 0.0.0.0/0",
                        severity=Severity.CRITICAL,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"{prop_name}={property_value}",
                        category="unrestricted_access",
                        cwe_id="CWE-284",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": 'Restrict ingress to specific IP ranges or security groups. Use ec2.Peer.ipv4("10.0.0.0/8") instead of 0.0.0.0/0.',
                        },
                    )
                )

            if "::/0" in property_value or "Peer.anyIpv6" in property_value:
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-sg-unrestricted-ingress-ipv6",
                        message=f"Security group '{display_name}' allows unrestricted IPv6 ingress from ::/0",
                        severity=Severity.CRITICAL,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"{prop_name}={property_value}",
                        category="unrestricted_access",
                        cwe_id="CWE-284",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Restrict IPv6 ingress to specific ranges or security groups.",
                        },
                    )
                )

    return findings


def _check_allow_all_outbound(db: RuleDB) -> list[StandardFinding]:
    """Detect security groups with allow_all_outbound=True.

    This is LOW severity as egress filtering is defense-in-depth.
    Default AWS behavior is allow-all-outbound, so this is informational.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "SecurityGroup" in cdk_class
            and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedSecurityGroup"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ? OR property_name = ?", "allow_all_outbound", "allowAllOutbound")
        )

        if prop_rows:
            prop_value, prop_line = prop_rows[0]
            if prop_value.lower() == "true":
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-sg-allow-all-outbound",
                        message=f"Security group '{display_name}' allows all outbound traffic",
                        severity=Severity.LOW,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet="allow_all_outbound=True",
                        category="broad_permissions",
                        cwe_id="CWE-284",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Consider restricting outbound traffic to specific destinations if defense-in-depth is required.",
                        },
                    )
                )

    return findings
