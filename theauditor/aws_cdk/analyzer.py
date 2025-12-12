"""AWS CDK security analyzer.

Directly calls the 4 dedicated AWS CDK rules - no orchestrator overhead.
"""

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from theauditor.rules.base import Severity, StandardRuleContext
from theauditor.rules.fidelity import RuleResult
from theauditor.utils.logging import logger

# Direct imports of the 4 CDK rules - no orchestrator
from theauditor.rules.deployment.aws_cdk_encryption_analyze import (
    analyze as analyze_encryption,
)
from theauditor.rules.deployment.aws_cdk_iam_wildcards_analyze import (
    analyze as analyze_iam_wildcards,
)
from theauditor.rules.deployment.aws_cdk_s3_public_analyze import (
    analyze as analyze_s3_public,
)
from theauditor.rules.deployment.aws_cdk_sg_open_analyze import (
    analyze as analyze_sg_open,
)


@dataclass
class CdkFinding:
    """CDK-specific security finding (backward compatibility format)."""

    finding_id: str
    file_path: str
    construct_id: str | None
    category: str
    severity: str
    title: str
    description: str
    line: int | None
    remediation: str = ""


class AWSCdkAnalyzer:
    """Analyzes AWS CDK code for security misconfigurations."""

    def __init__(self, db_path: str, severity_filter: str = "all"):
        """Initialize CDK analyzer."""
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        self.severity_filter = severity_filter
        self.severity_order = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
            "info": 4,
            "all": 999,
        }

    def analyze(self) -> list[CdkFinding]:
        """Run all CDK security rules and return findings."""
        context = self._build_rule_context()

        # Run ONLY the 4 dedicated CDK rules - nothing else
        all_findings = []

        for rule_func in [
            analyze_encryption,
            analyze_iam_wildcards,
            analyze_s3_public,
            analyze_sg_open,
        ]:
            try:
                result = rule_func(context)
                if isinstance(result, RuleResult):
                    findings = result.findings
                else:
                    findings = result

                if findings:
                    for f in findings:
                        if hasattr(f, "to_dict"):
                            all_findings.append(f.to_dict())
                        else:
                            all_findings.append(f)
            except Exception as e:
                logger.warning(f"CDK rule {rule_func.__module__} failed: {e}")

        converted_findings = self._convert_findings(all_findings)
        filtered = self._filter_by_severity(converted_findings)
        self._write_findings(filtered)

        logger.info(f"CDK analysis complete: {len(filtered)} findings")
        return filtered

    def _build_rule_context(self) -> StandardRuleContext:
        """Build StandardRuleContext for CDK rules."""
        project_root = self.db_path.parent
        if project_root.name == ".pf":
            project_root = project_root.parent

        return StandardRuleContext(
            file_path=self.db_path,
            content="",
            language="python-cdk",
            project_path=project_root,
            db_path=str(self.db_path),
        )

    def _convert_findings(self, standard_findings: list[dict]) -> list[CdkFinding]:
        """Convert finding dictionaries from rules to CdkFinding format."""
        cdk_findings: list[CdkFinding] = []

        for finding in standard_findings:
            additional = finding.get("additional_info") or {}

            construct_id = additional.get("construct_id")
            remediation = additional.get("remediation", "")

            cdk_findings.append(
                CdkFinding(
                    finding_id=self._build_finding_id(finding),
                    file_path=finding.get("file", ""),
                    construct_id=construct_id,
                    category=finding.get("category", ""),
                    severity=self._normalize_severity(finding.get("severity", "info")),
                    title=finding.get("message", ""),
                    description=finding.get("message", ""),
                    line=finding.get("line", 0) or 0,
                    remediation=remediation,
                )
            )

        return cdk_findings

    def _build_finding_id(self, finding: dict) -> str:
        """Generate unique finding ID."""
        parts = [
            "cdk",
            finding.get("rule", ""),
            finding.get("file", ""),
            str(finding.get("line", 0) or 0),
            finding.get("message", ""),
        ]
        hash_input = "::".join(parts)
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, hash_input))

    def _normalize_severity(self, severity) -> str:
        """Normalize severity to lowercase string."""
        if isinstance(severity, Severity):
            return severity.value.lower()
        return str(severity).lower()

    def _filter_by_severity(self, findings: list[CdkFinding]) -> list[CdkFinding]:
        """Filter findings by configured severity level."""
        if self.severity_filter == "all":
            return findings

        threshold = self.severity_order.get(self.severity_filter.lower(), 999)
        return [
            f for f in findings if self.severity_order.get(f.severity.lower(), 999) <= threshold
        ]

    def _write_findings(self, findings: list[CdkFinding]):
        """Write findings to cdk_findings and findings_consolidated tables."""
        if not findings:
            return

        with sqlite3.connect(self.db_path, timeout=60) as conn:
            # Enable WAL mode for concurrent access during parallel pipeline execution
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            cursor = conn.cursor()

            for finding in findings:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO cdk_findings (
                        finding_id, file_path, construct_id, category,
                        severity, title, description, remediation, line
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        finding.finding_id,
                        finding.file_path,
                        finding.construct_id,
                        finding.category,
                        finding.severity,
                        finding.title,
                        finding.description,
                        finding.remediation,
                        finding.line,
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO findings_consolidated (
                        file, line, column, rule, tool, message,
                        severity, category, confidence, code_snippet, cwe, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        finding.file_path,
                        finding.line,
                        0,
                        finding.finding_id,
                        "cdk",
                        finding.title,
                        finding.severity,
                        finding.category,
                        "high",
                        finding.description[:200] if finding.description else "",
                        None,
                        datetime.now().isoformat(),
                    ),
                )

            conn.commit()
            logger.info(f"Wrote {len(findings)} CDK findings to database")
