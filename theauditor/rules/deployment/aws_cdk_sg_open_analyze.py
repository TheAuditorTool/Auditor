"""AWS CDK Security Group Detection - database-first rule.

Detects overly permissive security groups in CDK code:
- Unrestricted ingress from 0.0.0.0/0 (IPv4 any)
- Unrestricted ingress from ::/0 (IPv6 any)
- Dangerous ports exposed to internet (SSH, RDP, database ports)
- All traffic rules (protocol -1 or Port.allTraffic)
- allow_all_outbound=True (informational)

CWE-284: Improper Access Control
"""

import re

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

DANGEROUS_PORTS = {
    22: ("SSH", Severity.CRITICAL),
    3389: ("RDP", Severity.CRITICAL),
    23: ("Telnet", Severity.CRITICAL),
    21: ("FTP", Severity.HIGH),
    3306: ("MySQL", Severity.CRITICAL),
    5432: ("PostgreSQL", Severity.CRITICAL),
    1433: ("MSSQL", Severity.CRITICAL),
    1521: ("Oracle", Severity.CRITICAL),
    27017: ("MongoDB", Severity.CRITICAL),
    6379: ("Redis", Severity.CRITICAL),
    9200: ("Elasticsearch", Severity.HIGH),
    5601: ("Kibana", Severity.HIGH),
    2375: ("Docker", Severity.CRITICAL),
    2376: ("Docker TLS", Severity.CRITICAL),
    8080: ("HTTP Alt", Severity.MEDIUM),
    9090: ("Prometheus", Severity.MEDIUM),
}

SAFE_PUBLIC_PORTS = frozenset([80, 443])


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
        findings.extend(_check_dangerous_ports_exposed(db))
        findings.extend(_check_all_traffic_rules(db))
        findings.extend(_check_allow_all_outbound(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _extract_port_from_value(value: str) -> int | None:
    """Extract port number from CDK port expressions."""
    patterns = [
        r"Port\.tcp\((\d+)\)",
        r"Port\.udp\((\d+)\)",
        r"ec2\.Port\.tcp\((\d+)\)",
        r"ec2\.Port\.udp\((\d+)\)",
        r"port[=:]\s*(\d+)",
        r"from_port[=:]\s*(\d+)",
        r"fromPort[=:]\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _is_all_traffic(value: str) -> bool:
    """Check if value indicates all traffic allowed."""
    indicators = [
        "allTraffic",
        "all_traffic",
        "Port.all()",
        "Port.allTcp()",
        "Port.allUdp()",
        "Port.all_tcp()",
        "Port.all_udp()",
        "Port.all_traffic()",
        "ec2.Port.all()",
        "ec2.Port.allTcp()",
        "ec2.Port.allUdp()",
        "ec2.Port.all_tcp()",
        "ec2.Port.all_udp()",
        "ec2.Port.all_traffic()",
        "protocol=-1",
        "protocol: -1",
        "ipProtocol: '-1'",
        "ip_protocol=-1",
        "ip_protocol: -1",
        "tcpRange(0, 65535)",
        "tcp_range(0, 65535)",
        "udpRange(0, 65535)",
        "udp_range(0, 65535)",
    ]
    value_lower = value.lower()
    return any(ind.lower() in value_lower for ind in indicators)


def _check_unrestricted_ingress(db: RuleDB) -> list[StandardFinding]:
    """Detect security groups allowing unrestricted ingress (0.0.0.0/0 or ::/0).

    Note: This flags all instances of 0.0.0.0/0 ingress. In practice, load balancers
    and public-facing services legitimately need this on specific ports (80, 443).
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "SecurityGroup" in cdk_class and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedSecurityGroup"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        for prop_name, property_value, prop_line in prop_rows:
            port = _extract_port_from_value(property_value)

            if "0.0.0.0/0" in property_value or "Peer.anyIpv4" in property_value:
                if port in SAFE_PUBLIC_PORTS:
                    continue

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
                            "port": port,
                            "remediation": 'Restrict ingress to specific IP ranges or security groups. Use ec2.Peer.ipv4("10.0.0.0/8") instead of 0.0.0.0/0.',
                        },
                    )
                )

            if "::/0" in property_value or "Peer.anyIpv6" in property_value:
                if port in SAFE_PUBLIC_PORTS:
                    continue

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
                            "port": port,
                            "remediation": "Restrict IPv6 ingress to specific ranges or security groups.",
                        },
                    )
                )

    return findings


def _check_dangerous_ports_exposed(db: RuleDB) -> list[StandardFinding]:
    """Detect dangerous ports exposed to 0.0.0.0/0.

    Administrative ports (SSH, RDP) and database ports should never be
    exposed to the internet. These are common attack vectors.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "SecurityGroup" in cdk_class and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedSecurityGroup"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        for prop_name, property_value, prop_line in prop_rows:
            is_public = (
                "0.0.0.0/0" in property_value
                or "Peer.anyIpv4" in property_value
                or "::/0" in property_value
                or "Peer.anyIpv6" in property_value
            )

            if not is_public:
                continue

            port = _extract_port_from_value(property_value)

            if port and port in DANGEROUS_PORTS:
                service_name, severity = DANGEROUS_PORTS[port]
                findings.append(
                    StandardFinding(
                        rule_name=f"aws-cdk-sg-{service_name.lower()}-exposed",
                        message=f"Security group '{display_name}' exposes {service_name} (port {port}) to the internet",
                        severity=severity,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"{prop_name}={property_value}",
                        category="dangerous_exposure",
                        cwe_id="CWE-284",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "port": port,
                            "service": service_name,
                            "remediation": f"Never expose {service_name} to the internet. Use VPN, bastion hosts, or AWS Systems Manager Session Manager for access.",
                        },
                    )
                )

    return findings


def _check_all_traffic_rules(db: RuleDB) -> list[StandardFinding]:
    """Detect security groups allowing all traffic (protocol -1).

    All traffic rules bypass port-level filtering entirely, which is
    almost never appropriate for production security groups.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "SecurityGroup" in cdk_class and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedSecurityGroup"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        for prop_name, property_value, prop_line in prop_rows:
            if _is_all_traffic(property_value):
                is_public = (
                    "0.0.0.0/0" in property_value
                    or "Peer.anyIpv4" in property_value
                    or "::/0" in property_value
                    or "Peer.anyIpv6" in property_value
                )

                severity = Severity.CRITICAL if is_public else Severity.HIGH

                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-sg-all-traffic",
                        message=f"Security group '{display_name}' allows all traffic (protocol -1)",
                        severity=severity,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"{prop_name}={property_value}",
                        category="excessive_permissions",
                        cwe_id="CWE-284",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "public_exposure": is_public,
                            "remediation": "Specify exact ports and protocols needed instead of allowing all traffic.",
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
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "SecurityGroup" in cdk_class and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedSecurityGroup"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where(
                "property_name = ? OR property_name = ?", "allow_all_outbound", "allowAllOutbound"
            )
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
