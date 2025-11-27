"""AWS CDK security analyzer.

Runs CDK security rules via RulesOrchestrator and stores findings to database.
Follows the same pattern as TerraformAnalyzer for architectural consistency.
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from ..rules.orchestrator import RulesOrchestrator
from ..rules.base import StandardRuleContext, Severity

logger = logging.getLogger(__name__)


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
        """Initialize CDK analyzer.

        Args:
            db_path: Path to repo_index.db database
            severity_filter: Filter findings by severity (all, critical, high, medium, low)
        """
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
        """Run all CDK security rules and return findings.

        Returns:
            List of CdkFinding objects
        """

        project_root = self.db_path.parent
        if project_root.name == ".pf":
            project_root = project_root.parent

        orchestrator = RulesOrchestrator(project_root, self.db_path)

        standard_findings = orchestrator.run_database_rules()

        cdk_findings = [f for f in standard_findings if self._is_cdk_rule(f)]

        converted_findings = self._convert_findings(cdk_findings)

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

    def _is_cdk_rule(self, finding: dict) -> bool:
        """Check if finding comes from a CDK rule.

        CDK rules have rule_name starting with 'aws-cdk-'.

        Args:
            finding: Dictionary from orchestrator.run_database_rules()
                     Note: orchestrator converts StandardFinding.rule_name → dict['rule']
        """

        rule_name = finding.get("rule", "")
        return rule_name.startswith("aws-cdk-")

    def _convert_findings(self, standard_findings: list[dict]) -> list[CdkFinding]:
        """Convert finding dictionaries from orchestrator to CdkFinding format.

        Args:
            standard_findings: List of finding dicts from orchestrator.run_database_rules()
                              Note: StandardFinding.to_dict() converts:
                              - rule_name → 'rule'
                              - file_path → 'file'
                              - snippet → 'code_snippet'
                              - cwe_id → 'cwe'
                              - additional_info → 'details_json' (as JSON string)
        """
        cdk_findings: list["CdkFinding"] = []

        for finding in standard_findings:
            import json

            details_json = finding.get("details_json")
            if details_json and isinstance(details_json, str):
                try:
                    additional = json.loads(details_json)
                except json.JSONDecodeError:
                    additional = {}
            else:
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
        """Generate unique finding ID.

        Args:
            finding: Dictionary from orchestrator.run_database_rules()
                     Note: dict keys are 'rule' and 'file', not 'rule_name' and 'file_path'
        """
        parts = [
            "cdk",
            finding.get("rule", ""),
            finding.get("file", ""),
            str(finding.get("line", 0) or 0),
        ]
        hash_input = "::".join(parts)
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, hash_input))

    def _normalize_severity(self, severity) -> str:
        """Normalize severity to lowercase string."""
        if isinstance(severity, Severity):
            return severity.value.lower()
        return str(severity).lower()

    def _filter_by_severity(self, findings: list["CdkFinding"]) -> list[CdkFinding]:
        """Filter findings by configured severity level."""
        if self.severity_filter == "all":
            return findings

        threshold = self.severity_order.get(self.severity_filter.lower(), 999)
        return [
            f for f in findings if self.severity_order.get(f.severity.lower(), 999) <= threshold
        ]

    def _write_findings(self, findings: list["CdkFinding"]):
        """Write findings to cdk_findings and findings_consolidated tables."""
        if not findings:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
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
                        severity, category, confidence, code_snippet, cwe, timestamp, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        None,
                    ),
                )

            conn.commit()
            logger.info(f"Wrote {len(findings)} CDK findings to database")

        except sqlite3.Error as e:
            logger.error(f"Failed to write CDK findings: {e}")
            conn.rollback()
        finally:
            conn.close()
