"""Terraform security analyzer."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import Severity, StandardRuleContext
from theauditor.rules.terraform.terraform_analyze import analyze as terraform_analyze
from theauditor.utils.logging import logger


@dataclass
class TerraformFinding:
    """Terraform-specific security finding."""

    finding_id: str
    file_path: str
    resource_id: str | None
    category: str
    severity: str
    title: str
    description: str
    line: int | None
    remediation: str = ""
    graph_context_json: str | None = None


class TerraformAnalyzer:
    """Backward-compatible analyzer that now delegates to standardized rules."""

    def __init__(self, db_path: str, severity_filter: str = "all"):
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

    def analyze(self) -> list[TerraformFinding]:
        """Run standardized Terraform rule and return converted findings."""
        context = self._build_rule_context()
        result = terraform_analyze(context)
        terraform_findings = self._convert_findings(result.findings)

        filtered = self._filter_by_severity(terraform_findings)
        self._write_findings(filtered)

        logger.info(f"Terraform analysis complete: {len(filtered)} findings")
        return filtered

    def _build_rule_context(self) -> StandardRuleContext:
        project_root = self.db_path.parent
        if project_root.name == ".pf":
            project_root = project_root.parent

        return StandardRuleContext(
            file_path=self.db_path,
            content="",
            language="terraform",
            project_path=project_root,
            db_path=str(self.db_path),
        )

    def _convert_findings(self, standard_findings) -> list[TerraformFinding]:
        terraform_findings: list[TerraformFinding] = []

        for finding in standard_findings:
            additional = getattr(finding, "additional_info", None) or {}
            resource_id = additional.get("resource_id") or additional.get("variable_name")
            remediation = additional.get("remediation", "") if additional else ""

            terraform_findings.append(
                TerraformFinding(
                    finding_id=self._build_finding_id(finding),
                    file_path=finding.file_path,
                    resource_id=resource_id,
                    category=getattr(finding, "category", "security"),
                    severity=self._normalize_severity(getattr(finding, "severity", "info")),
                    title=finding.message,
                    description=finding.message,
                    line=getattr(finding, "line", 0) or 0,
                    remediation=remediation,
                )
            )

        return terraform_findings

    def _build_finding_id(self, finding) -> str:
        """Generate unique finding ID.

        Includes message to differentiate multiple findings on the same line.
        """
        file_part = getattr(finding, "file_path", "unknown")
        line_part = getattr(finding, "line", 0) or 0
        rule_name = getattr(finding, "rule_name", "terraform")
        message = getattr(finding, "message", "")
        return f"{rule_name}:{file_part}:{line_part}:{message}"

    def _normalize_severity(self, severity_value) -> str:
        if isinstance(severity_value, Severity):
            return severity_value.value
        return str(severity_value).lower()

    def _filter_by_severity(self, findings: list[TerraformFinding]) -> list[TerraformFinding]:
        if self.severity_filter == "all":
            return findings

        min_severity = self.severity_order.get(self.severity_filter, 999)
        return [f for f in findings if self.severity_order.get(f.severity, 999) <= min_severity]

    def _write_findings(self, findings: list[TerraformFinding]):
        """Write findings to both terraform_findings and consolidated tables."""
        if not findings:
            return

        from datetime import UTC, datetime

        conn = sqlite3.connect(self.db_path, timeout=60)
        # Enable WAL mode for concurrent access during parallel pipeline execution
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        cursor = conn.cursor()

        cursor.execute("DELETE FROM terraform_findings")
        cursor.execute("DELETE FROM findings_consolidated WHERE tool = 'terraform'")

        timestamp = datetime.now(UTC).isoformat()

        for finding in findings:
            cursor.execute(
                """
                INSERT INTO terraform_findings
                (finding_id, file_path, resource_id, category, severity,
                 title, description, graph_context_json, remediation, line)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding.finding_id,
                    finding.file_path,
                    finding.resource_id,
                    finding.category,
                    finding.severity,
                    finding.title,
                    finding.description,
                    finding.graph_context_json,
                    finding.remediation,
                    finding.line,
                ),
            )

            cursor.execute(
                """
                INSERT INTO findings_consolidated
                (file, line, column, rule, tool, message, severity, category,
                 confidence, code_snippet, cwe, timestamp,
                 tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding.file_path,
                    finding.line or 0,
                    None,
                    finding.finding_id,
                    "terraform",
                    finding.title,
                    finding.severity,
                    finding.category,
                    1.0,
                    finding.resource_id or "",
                    "",
                    timestamp,
                    finding.finding_id,
                    finding.resource_id,
                    finding.remediation,
                    finding.graph_context_json,
                ),
            )

        conn.commit()
        conn.close()

        logger.debug(
            f"Wrote {len(findings)} findings to terraform_findings and findings_consolidated"
        )
