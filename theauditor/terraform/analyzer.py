"""Terraform security analyzer.

Analyzes Terraform configurations for infrastructure security issues including:
- Public exposure (S3 buckets, databases, etc.)
- Overly permissive IAM policies
- Hardcoded secrets in resource configurations
- Missing encryption for sensitive resources
- Unencrypted network traffic

Architecture:
- Database-first: Queries terraform_* tables from repo_index.db
- Zero fallbacks: Hard fail on missing data
- Writes to terraform_findings table
- Returns standardized findings for FCE integration
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class TerraformFinding:
    """Terraform-specific security finding."""

    finding_id: str
    file_path: str
    resource_id: Optional[str]
    category: str
    severity: str
    title: str
    description: str
    line: Optional[int]
    remediation: str = ""
    graph_context_json: Optional[str] = None


class TerraformAnalyzer:
    """Analyzes Terraform configurations for security issues."""

    def __init__(self, db_path: str, severity_filter: str = "all"):
        """Initialize analyzer.

        Args:
            db_path: Path to repo_index.db
            severity_filter: Minimum severity to report
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        self.severity_filter = severity_filter
        self.severity_order = {
            'critical': 0,
            'high': 1,
            'medium': 2,
            'low': 3,
            'info': 4,
            'all': 999
        }

    def analyze(self) -> List[TerraformFinding]:
        """Run all security checks and return findings.

        Returns:
            List of TerraformFinding objects
        """
        findings = []

        # Run all checks
        findings.extend(self._check_public_s3_buckets())
        findings.extend(self._check_unencrypted_storage())
        findings.extend(self._check_iam_wildcards())
        findings.extend(self._check_hardcoded_secrets())
        findings.extend(self._check_missing_encryption())
        findings.extend(self._check_security_groups())

        # Filter by severity
        filtered = self._filter_by_severity(findings)

        # Write to database
        self._write_findings(filtered)

        logger.info(f"Terraform analysis complete: {len(filtered)} findings")
        return filtered

    def _check_public_s3_buckets(self) -> List[TerraformFinding]:
        """Check for S3 buckets with public access."""
        findings = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query S3 bucket resources
        cursor.execute("""
            SELECT resource_id, file_path, resource_name, properties_json, line
            FROM terraform_resources
            WHERE resource_type = 'aws_s3_bucket'
        """)

        for row in cursor.fetchall():
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}

            # Check for public ACL
            acl = properties.get('acl', '')
            if acl in ['public-read', 'public-read-write']:
                findings.append(TerraformFinding(
                    finding_id=f"{row['resource_id']}::public_acl",
                    file_path=row['file_path'],
                    resource_id=row['resource_id'],
                    category='public_exposure',
                    severity='high',
                    title=f"S3 bucket '{row['resource_name']}' has public ACL",
                    description=f"Bucket configured with ACL '{acl}' allowing public access. "
                               f"This exposes data to anyone on the internet.",
                    line=row['line'],
                    remediation="Remove 'acl' property or set to 'private'. "
                               "Use bucket policies for granular access control."
                ))

            # Check for website configuration (implies public)
            if 'website' in properties:
                findings.append(TerraformFinding(
                    finding_id=f"{row['resource_id']}::public_website",
                    file_path=row['file_path'],
                    resource_id=row['resource_id'],
                    category='public_exposure',
                    severity='medium',
                    title=f"S3 bucket '{row['resource_name']}' configured as website",
                    description="Bucket configured for static website hosting, which typically requires public access.",
                    line=row['line'],
                    remediation="Verify public access is intentional. Use CloudFront if public hosting needed."
                ))

        conn.close()
        return findings

    def _check_unencrypted_storage(self) -> List[TerraformFinding]:
        """Check for storage resources without encryption."""
        findings = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check RDS instances
        cursor.execute("""
            SELECT resource_id, file_path, resource_name, properties_json, line
            FROM terraform_resources
            WHERE resource_type IN ('aws_db_instance', 'aws_rds_cluster')
        """)

        for row in cursor.fetchall():
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}

            # Check for storage_encrypted
            storage_encrypted = properties.get('storage_encrypted', False)
            if not storage_encrypted:
                findings.append(TerraformFinding(
                    finding_id=f"{row['resource_id']}::unencrypted",
                    file_path=row['file_path'],
                    resource_id=row['resource_id'],
                    category='missing_encryption',
                    severity='high',
                    title=f"Database '{row['resource_name']}' not encrypted at rest",
                    description="Database instance configured without encryption. "
                               "Data stored on disk is unencrypted.",
                    line=row['line'],
                    remediation="Add 'storage_encrypted = true' to resource configuration."
                ))

        # Check EBS volumes
        cursor.execute("""
            SELECT resource_id, file_path, resource_name, properties_json, line
            FROM terraform_resources
            WHERE resource_type = 'aws_ebs_volume'
        """)

        for row in cursor.fetchall():
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}

            encrypted = properties.get('encrypted', False)
            if not encrypted:
                findings.append(TerraformFinding(
                    finding_id=f"{row['resource_id']}::unencrypted",
                    file_path=row['file_path'],
                    resource_id=row['resource_id'],
                    category='missing_encryption',
                    severity='medium',
                    title=f"EBS volume '{row['resource_name']}' not encrypted",
                    description="EBS volume configured without encryption.",
                    line=row['line'],
                    remediation="Add 'encrypted = true' to resource configuration."
                ))

        conn.close()
        return findings

    def _check_iam_wildcards(self) -> List[TerraformFinding]:
        """Check for overly permissive IAM policies."""
        findings = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT resource_id, file_path, resource_name, properties_json, line
            FROM terraform_resources
            WHERE resource_type IN ('aws_iam_policy', 'aws_iam_role_policy')
        """)

        for row in cursor.fetchall():
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}

            # Check policy document
            policy_str = properties.get('policy', '')
            if isinstance(policy_str, str) and '*' in policy_str:
                # Parse policy JSON
                try:
                    if policy_str.startswith('{'):
                        policy = json.loads(policy_str)
                    else:
                        policy = None
                except:
                    policy = None

                if policy:
                    has_wildcard_action = False
                    has_wildcard_resource = False

                    for statement in policy.get('Statement', []):
                        actions = statement.get('Action', [])
                        if isinstance(actions, str):
                            actions = [actions]
                        if '*' in actions:
                            has_wildcard_action = True

                        resources = statement.get('Resource', [])
                        if isinstance(resources, str):
                            resources = [resources]
                        if '*' in resources:
                            has_wildcard_resource = True

                    if has_wildcard_action and has_wildcard_resource:
                        findings.append(TerraformFinding(
                            finding_id=f"{row['resource_id']}::wildcard_policy",
                            file_path=row['file_path'],
                            resource_id=row['resource_id'],
                            category='iam_wildcard',
                            severity='critical',
                            title=f"IAM policy '{row['resource_name']}' uses wildcard for actions and resources",
                            description="Policy grants full access (*) to all resources (*). "
                                       "This violates principle of least privilege.",
                            line=row['line'],
                            remediation="Restrict 'Action' and 'Resource' to specific values needed."
                        ))

        conn.close()
        return findings

    def _check_hardcoded_secrets(self) -> List[TerraformFinding]:
        """Check for hardcoded secrets in resource properties."""
        findings = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check all resources for sensitive properties with hardcoded values
        cursor.execute("""
            SELECT resource_id, file_path, resource_name, properties_json,
                   sensitive_flags_json, line
            FROM terraform_resources
        """)

        for row in cursor.fetchall():
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}
            sensitive_props = json.loads(row['sensitive_flags_json']) if row['sensitive_flags_json'] else []

            for prop_name in sensitive_props:
                prop_value = properties.get(prop_name)

                # Check if value is hardcoded string (not var reference)
                if isinstance(prop_value, str) and not prop_value.startswith('var.'):
                    # Exclude interpolations
                    if '${' not in prop_value:
                        findings.append(TerraformFinding(
                            finding_id=f"{row['resource_id']}::hardcoded_{prop_name}",
                            file_path=row['file_path'],
                            resource_id=row['resource_id'],
                            category='hardcoded_secret',
                            severity='critical',
                            title=f"Hardcoded secret in '{row['resource_name']}.{prop_name}'",
                            description=f"Property '{prop_name}' contains a hardcoded value. "
                                       f"Secrets should never be committed to version control.",
                            line=row['line'],
                            remediation=f"Replace with variable reference: {prop_name} = var.{prop_name}"
                        ))

        conn.close()
        return findings

    def _check_missing_encryption(self) -> List[TerraformFinding]:
        """Check for resources that should use encryption but don't specify it."""
        findings = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check SNS topics
        cursor.execute("""
            SELECT resource_id, file_path, resource_name, properties_json, line
            FROM terraform_resources
            WHERE resource_type = 'aws_sns_topic'
        """)

        for row in cursor.fetchall():
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}

            if 'kms_master_key_id' not in properties:
                findings.append(TerraformFinding(
                    finding_id=f"{row['resource_id']}::no_kms",
                    file_path=row['file_path'],
                    resource_id=row['resource_id'],
                    category='missing_encryption',
                    severity='low',
                    title=f"SNS topic '{row['resource_name']}' missing KMS encryption",
                    description="SNS topic not configured with KMS encryption.",
                    line=row['line'],
                    remediation="Add 'kms_master_key_id' with KMS key ARN."
                ))

        conn.close()
        return findings

    def _check_security_groups(self) -> List[TerraformFinding]:
        """Check for overly permissive security group rules."""
        findings = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT resource_id, file_path, resource_name, properties_json, line
            FROM terraform_resources
            WHERE resource_type IN ('aws_security_group', 'aws_security_group_rule')
        """)

        for row in cursor.fetchall():
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}

            # Check ingress rules
            ingress_rules = properties.get('ingress', [])
            if not isinstance(ingress_rules, list):
                ingress_rules = [ingress_rules] if ingress_rules else []

            for rule in ingress_rules:
                if not isinstance(rule, dict):
                    continue

                cidr_blocks = rule.get('cidr_blocks', [])
                if '0.0.0.0/0' in cidr_blocks:
                    from_port = rule.get('from_port', 0)
                    to_port = rule.get('to_port', 0)

                    severity = 'high' if from_port != 443 and from_port != 80 else 'medium'

                    findings.append(TerraformFinding(
                        finding_id=f"{row['resource_id']}::open_ingress_{from_port}",
                        file_path=row['file_path'],
                        resource_id=row['resource_id'],
                        category='public_exposure',
                        severity=severity,
                        title=f"Security group '{row['resource_name']}' allows ingress from 0.0.0.0/0",
                        description=f"Ingress rule allows traffic from any IP on port {from_port}-{to_port}.",
                        line=row['line'],
                        remediation="Restrict 'cidr_blocks' to specific IPs or VPC CIDR ranges."
                    ))

        conn.close()
        return findings

    def _filter_by_severity(self, findings: List[TerraformFinding]) -> List[TerraformFinding]:
        """Filter findings by severity threshold."""
        if self.severity_filter == 'all':
            return findings

        min_severity = self.severity_order.get(self.severity_filter, 999)

        return [
            f for f in findings
            if self.severity_order.get(f.severity, 999) <= min_severity
        ]

    def _write_findings(self, findings: List[TerraformFinding]):
        """Write findings to both terraform_findings and findings_consolidated tables.

        Dual-write pattern ensures FCE can correlate Terraform findings with other
        security findings without requiring special-case queries.
        """
        if not findings:
            return

        from datetime import datetime, UTC

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Clear existing terraform findings
        cursor.execute("DELETE FROM terraform_findings")
        cursor.execute("DELETE FROM findings_consolidated WHERE tool = 'terraform'")

        timestamp = datetime.now(UTC).isoformat()

        # Dual-write: terraform_findings (Terraform-specific) AND findings_consolidated (FCE)
        for finding in findings:
            # Write to terraform_findings (Terraform-specific table)
            cursor.execute("""
                INSERT INTO terraform_findings
                (finding_id, file_path, resource_id, category, severity,
                 title, description, graph_context_json, remediation, line)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                finding.finding_id,
                finding.file_path,
                finding.resource_id,
                finding.category,
                finding.severity,
                finding.title,
                finding.description,
                finding.graph_context_json,
                finding.remediation,
                finding.line
            ))

            # Write to findings_consolidated (FCE integration)
            details_json = json.dumps({
                'finding_id': finding.finding_id,
                'resource_id': finding.resource_id,
                'remediation': finding.remediation,
                'graph_context_json': finding.graph_context_json
            })

            cursor.execute("""
                INSERT INTO findings_consolidated
                (file, line, column, rule, tool, message, severity, category,
                 confidence, code_snippet, cwe, timestamp, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                finding.file_path,                      # file
                finding.line or 0,                       # line
                None,                                    # column (not applicable for IaC)
                finding.finding_id,                      # rule (finding_id as unique identifier)
                'terraform',                             # tool
                finding.title,                           # message
                finding.severity,                        # severity
                finding.category,                        # category
                1.0,                                     # confidence (structural checks = high confidence)
                finding.resource_id or '',               # code_snippet (resource identifier)
                '',                                      # cwe (not applicable for IaC)
                timestamp,                               # timestamp
                details_json                             # details_json (full context)
            ))

        conn.commit()
        conn.close()

        logger.debug(f"Wrote {len(findings)} findings to terraform_findings and findings_consolidated tables")
