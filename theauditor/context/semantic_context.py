"""Semantic Context Engine - Apply business logic and semantic understanding to findings."""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ContextPattern:
    """Represents a semantic pattern (obsolete, current, or transitional)."""

    id: str
    pattern: str
    reason: str
    category: str
    severity: str | None = None
    replacement: str | None = None
    scope: dict[str, list[str]] | None = None
    expires: str | None = None
    compiled_regex: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        """Compile regex pattern after initialization."""
        try:
            self.compiled_regex = re.compile(self.pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(
                f"Invalid regex pattern '{self.pattern}' in pattern '{self.id}': {e}"
            ) from e

        if self.category not in ["obsolete", "current", "transitional"]:
            raise ValueError(
                f"Invalid category '{self.category}' for pattern '{self.id}'. "
                "Must be 'obsolete', 'current', or 'transitional'"
            )

        if self.severity and self.severity not in ["critical", "high", "medium", "low"]:
            raise ValueError(
                f"Invalid severity '{self.severity}' for pattern '{self.id}'. "
                "Must be 'critical', 'high', 'medium', or 'low'"
            )

        if self.category == "transitional" and not self.expires:
            raise ValueError(f"Transitional pattern '{self.id}' must have an 'expires' date")

    def matches(self, finding: dict[str, Any]) -> bool:
        """Check if a finding matches this pattern."""
        message = finding.get("message", "")
        rule = finding.get("rule", "")
        code_snippet = finding.get("code_snippet", "")

        return bool(
            self.compiled_regex.search(message)
            or self.compiled_regex.search(rule)
            or (code_snippet and self.compiled_regex.search(code_snippet))
        )

    def in_scope(self, file_path: str) -> bool:
        """Check if a file path is in this pattern's scope."""
        if not self.scope:
            return True

        excludes = self.scope.get("exclude", [])
        includes = self.scope.get("include", [])

        for exclude_pattern in excludes:
            if exclude_pattern in file_path:
                return False

        if not includes:
            return True

        return any(include_pattern in file_path for include_pattern in includes)

    def is_expired(self) -> bool:
        """Check if a transitional pattern has expired."""
        if not self.expires:
            return False

        try:
            expire_date = datetime.strptime(self.expires, "%Y-%m-%d").date()
            return date.today() > expire_date
        except ValueError:
            return False


@dataclass
class ClassificationResult:
    """Result of applying semantic context to findings."""

    obsolete: list[dict[str, Any]]
    current: list[dict[str, Any]]
    transitional: list[dict[str, Any]]
    unclassified: list[dict[str, Any]]
    mixed_files: dict[str, dict[str, int]]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "obsolete": self.obsolete,
            "current": self.current,
            "transitional": self.transitional,
            "unclassified": self.unclassified,
            "mixed_files": self.mixed_files,
            "summary": self.summary,
        }

    def get_high_priority_files(self) -> list[str]:
        """Get files with critical or high severity obsolete patterns."""
        high_priority = set()
        for item in self.obsolete:
            if item.get("severity") in ["critical", "high"]:
                high_priority.add(item["finding"]["file"])
        return sorted(high_priority)

    def get_migration_progress(self) -> dict[str, Any]:
        """Calculate migration progress statistics."""
        total_files = len(
            {item["finding"]["file"] for item in self.obsolete + self.current + self.transitional}
        )

        files_with_obsolete = len({item["finding"]["file"] for item in self.obsolete})

        files_fully_current = len({item["finding"]["file"] for item in self.current}) - len(
            self.mixed_files
        )

        return {
            "total_files": total_files,
            "files_need_migration": files_with_obsolete,
            "files_fully_migrated": files_fully_current,
            "files_mixed": len(self.mixed_files),
            "migration_percentage": round(
                (files_fully_current / total_files * 100) if total_files > 0 else 0, 1
            ),
        }


class SemanticContext:
    """Main engine for applying semantic business logic to findings."""

    def __init__(self, context_file: Path):
        """Initialize semantic context."""
        self.context_file = Path(context_file)
        self.context_name: str = ""
        self.description: str = ""
        self.version: str = ""
        self.obsolete_patterns: list[ContextPattern] = []
        self.current_patterns: list[ContextPattern] = []
        self.transitional_patterns: list[ContextPattern] = []
        self.relationships: list[dict[str, Any]] = []
        self.metadata: dict[str, Any] = {}

    @classmethod
    def load(cls, yaml_path: Path) -> SemanticContext:
        """Load semantic context from YAML file."""
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Semantic context file not found: {yaml_path}")

        with open(yaml_path, encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {yaml_path}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid context file format in {yaml_path}: expected dictionary at root"
            )

        instance = cls(yaml_path)

        instance.context_name = data.get("context_name", yaml_path.stem)
        instance.description = data.get("description", "")
        instance.version = data.get("version", "unknown")
        instance.metadata = data.get("metadata", {})
        instance.relationships = data.get("relationships", [])

        patterns_data = data.get("patterns", {})

        for pattern_data in patterns_data.get("obsolete", []):
            try:
                pattern = ContextPattern(
                    id=pattern_data["id"],
                    pattern=pattern_data["pattern"],
                    reason=pattern_data["reason"],
                    category="obsolete",
                    severity=pattern_data.get("severity", "medium"),
                    replacement=pattern_data.get("replacement"),
                    scope=pattern_data.get("scope"),
                )
                instance.obsolete_patterns.append(pattern)
            except (KeyError, ValueError) as e:
                raise ValueError(f"Invalid obsolete pattern in {yaml_path}: {e}") from e

        for pattern_data in patterns_data.get("current", []):
            try:
                pattern = ContextPattern(
                    id=pattern_data["id"],
                    pattern=pattern_data["pattern"],
                    reason=pattern_data["reason"],
                    category="current",
                    scope=pattern_data.get("scope"),
                )
                instance.current_patterns.append(pattern)
            except (KeyError, ValueError) as e:
                raise ValueError(f"Invalid current pattern in {yaml_path}: {e}") from e

        for pattern_data in patterns_data.get("transitional", []):
            try:
                pattern = ContextPattern(
                    id=pattern_data["id"],
                    pattern=pattern_data["pattern"],
                    reason=pattern_data["reason"],
                    category="transitional",
                    expires=pattern_data["expires"],
                    scope=pattern_data.get("scope"),
                )
                instance.transitional_patterns.append(pattern)
            except (KeyError, ValueError) as e:
                raise ValueError(f"Invalid transitional pattern in {yaml_path}: {e}") from e

        total_patterns = (
            len(instance.obsolete_patterns)
            + len(instance.current_patterns)
            + len(instance.transitional_patterns)
        )

        if total_patterns == 0:
            raise ValueError(f"No patterns defined in {yaml_path}")

        return instance

    def classify_findings(self, findings: list[dict[str, Any]]) -> ClassificationResult:
        """Apply semantic context to findings."""
        obsolete_matches: list[dict[str, Any]] = []
        current_matches: list[dict[str, Any]] = []
        transitional_matches: list[dict[str, Any]] = []
        classified_finding_ids: set[int] = set()

        file_stats: dict[str, dict[str, int]] = {}

        for finding_idx, finding in enumerate(findings):
            file_path = finding.get("file", "")

            if file_path not in file_stats:
                file_stats[file_path] = {"obsolete": 0, "current": 0, "transitional": 0}

            for pattern in self.obsolete_patterns:
                if pattern.matches(finding) and pattern.in_scope(file_path):
                    obsolete_matches.append(
                        {
                            "finding": finding,
                            "pattern_id": pattern.id,
                            "pattern_category": "obsolete",
                            "reason": pattern.reason,
                            "severity": pattern.severity or "medium",
                            "replacement": pattern.replacement,
                        }
                    )
                    file_stats[file_path]["obsolete"] += 1
                    classified_finding_ids.add(finding_idx)

            for pattern in self.current_patterns:
                if pattern.matches(finding) and pattern.in_scope(file_path):
                    current_matches.append(
                        {
                            "finding": finding,
                            "pattern_id": pattern.id,
                            "pattern_category": "current",
                            "reason": pattern.reason,
                        }
                    )
                    file_stats[file_path]["current"] += 1
                    classified_finding_ids.add(finding_idx)

            for pattern in self.transitional_patterns:
                if pattern.matches(finding) and pattern.in_scope(file_path):
                    expired = pattern.is_expired()
                    transitional_matches.append(
                        {
                            "finding": finding,
                            "pattern_id": pattern.id,
                            "pattern_category": "transitional",
                            "reason": pattern.reason,
                            "expires": pattern.expires,
                            "expired": expired,
                            "warning": "This transitional pattern has expired!"
                            if expired
                            else None,
                        }
                    )
                    file_stats[file_path]["transitional"] += 1
                    classified_finding_ids.add(finding_idx)

        unclassified = [
            {"finding": finding, "reason": "No matching semantic pattern"}
            for idx, finding in enumerate(findings)
            if idx not in classified_finding_ids
        ]

        mixed_files = {
            file: stats
            for file, stats in file_stats.items()
            if stats["obsolete"] > 0 and stats["current"] > 0
        }

        summary = {
            "total_findings": len(findings),
            "classified": len(classified_finding_ids),
            "unclassified": len(unclassified),
            "obsolete_count": len(obsolete_matches),
            "current_count": len(current_matches),
            "transitional_count": len(transitional_matches),
            "total_files": len(file_stats),
            "mixed_files_count": len(mixed_files),
            "context_name": self.context_name,
            "context_version": self.version,
        }

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for match in obsolete_matches:
            severity = match.get("severity", "medium")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        summary["obsolete_by_severity"] = severity_counts

        return ClassificationResult(
            obsolete=obsolete_matches,
            current=current_matches,
            transitional=transitional_matches,
            unclassified=unclassified,
            mixed_files=mixed_files,
            summary=summary,
        )

    def generate_report(self, result: ClassificationResult, verbose: bool = False) -> str:
        """Generate human-readable report from classification result."""
        lines = []

        lines.append("=" * 80)
        lines.append(f"SEMANTIC CONTEXT ANALYSIS: {self.context_name}")
        lines.append("=" * 80)

        if self.description:
            lines.append(f"\n{self.description}")

        lines.append(f"\nVersion: {self.version}")
        lines.append(f"Total Findings Analyzed: {result.summary['total_findings']}")
        lines.append(
            f"Classified: {result.summary['classified']} | "
            f"Unclassified: {result.summary['unclassified']}"
        )

        progress = result.get_migration_progress()
        lines.append("\nMIGRATION PROGRESS:")
        lines.append(f"  Total Files: {progress['total_files']}")
        lines.append(
            f"  Fully Migrated: {progress['files_fully_migrated']} "
            f"({progress['migration_percentage']}%)"
        )
        lines.append(f"  Need Migration: {progress['files_need_migration']}")
        lines.append(f"  Mixed State: {progress['files_mixed']}")

        if result.obsolete:
            lines.append("\n" + "=" * 80)
            lines.append(f"[X] OBSOLETE PATTERNS ({len(result.obsolete)} occurrences)")
            lines.append("=" * 80)

            by_severity = {"critical": [], "high": [], "medium": [], "low": []}
            for item in result.obsolete:
                severity = item.get("severity", "medium")
                by_severity[severity].append(item)

            for severity in ["critical", "high", "medium", "low"]:
                items = by_severity[severity]
                if items:
                    lines.append(f"\n{severity.upper()} Severity ({len(items)} occurrences):")

                    display_items = items if verbose else items[:5]

                    for item in display_items:
                        finding = item["finding"]
                        lines.append(
                            f"  * {finding['file']}:{finding.get('line', '?')} "
                            f"[{item['pattern_id']}]"
                        )
                        lines.append(f"    Reason: {item['reason']}")
                        if item.get("replacement"):
                            lines.append(f"    Suggested: {item['replacement']}")
                        if verbose and finding.get("message"):
                            lines.append(f"    Message: {finding['message'][:80]}")

                    if not verbose and len(items) > 5:
                        lines.append(f"  ... and {len(items) - 5} more")
        else:
            lines.append("\n[OK] No obsolete patterns found!")

        if result.current:
            lines.append("\n" + "=" * 80)
            lines.append(f"[OK] CURRENT PATTERNS ({len(result.current)} occurrences)")
            lines.append("=" * 80)

            if verbose:
                for item in result.current[:10]:
                    finding = item["finding"]
                    lines.append(
                        f"  * {finding['file']}:{finding.get('line', '?')} [{item['pattern_id']}]"
                    )
                    lines.append(f"    {item['reason']}")
            else:
                lines.append(f"  {len(result.current)} occurrences of correct patterns")
                lines.append("  Use --verbose flag for details")

        if result.transitional:
            lines.append("\n" + "=" * 80)
            lines.append(f"[~] TRANSITIONAL PATTERNS ({len(result.transitional)} occurrences)")
            lines.append("=" * 80)

            for item in result.transitional:
                finding = item["finding"]
                lines.append(
                    f"  * {finding['file']}:{finding.get('line', '?')} [{item['pattern_id']}]"
                )
                lines.append(
                    f"    Expires: {item['expires']} "
                    f"{'[!] EXPIRED' if item.get('expired') else '[OK] Valid'}"
                )
                if item.get("warning"):
                    lines.append(f"    [!] {item['warning']}")

        if result.mixed_files:
            lines.append("\n" + "=" * 80)
            lines.append(f"[!] MIXED FILES ({len(result.mixed_files)} files need attention)")
            lines.append("=" * 80)
            lines.append("\nThese files have both obsolete and current patterns:")

            for file_path, stats in sorted(result.mixed_files.items())[:10]:
                lines.append(f"  * {file_path}")
                lines.append(
                    f"    Obsolete: {stats['obsolete']} | "
                    f"Current: {stats['current']} | "
                    f"Transitional: {stats.get('transitional', 0)}"
                )

            if len(result.mixed_files) > 10:
                lines.append(f"  ... and {len(result.mixed_files) - 10} more mixed files")

        high_priority = result.get_high_priority_files()
        if high_priority:
            lines.append("\n" + "=" * 80)
            lines.append(f"[!!] HIGH PRIORITY FILES ({len(high_priority)} files)")
            lines.append("=" * 80)
            lines.append("\nFiles with CRITICAL or HIGH severity obsolete patterns:")
            for file_path in high_priority[:10]:
                lines.append(f"  * {file_path}")
            if len(high_priority) > 10:
                lines.append(f"  ... and {len(high_priority) - 10} more")

        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS:")
        lines.append("  1. Address HIGH PRIORITY files first")
        lines.append("  2. Update MIXED files to use only current patterns")
        lines.append("  3. Review TRANSITIONAL patterns approaching expiration")
        lines.append("  4. Run 'aud context --verbose' for detailed findings")
        lines.append("=" * 80)

        return "\n".join(lines)

    def suggest_migrations(self, result: ClassificationResult) -> list[dict[str, Any]]:
        """Generate actionable migration suggestions."""
        suggestions = []

        files_with_obsolete: dict[str, list[dict]] = {}
        for item in result.obsolete:
            file_path = item["finding"]["file"]
            if file_path not in files_with_obsolete:
                files_with_obsolete[file_path] = []
            files_with_obsolete[file_path].append(item)

        for file_path, items in sorted(files_with_obsolete.items()):
            high_severity_count = sum(
                1 for item in items if item.get("severity") in ["critical", "high"]
            )
            priority = "high" if high_severity_count > 0 else "medium"

            is_mixed = file_path in result.mixed_files

            patterns_found = {}
            for item in items:
                pattern_id = item["pattern_id"]
                if pattern_id not in patterns_found:
                    patterns_found[pattern_id] = {
                        "pattern_id": pattern_id,
                        "reason": item["reason"],
                        "replacement": item.get("replacement"),
                        "count": 0,
                    }
                patterns_found[pattern_id]["count"] += 1

            suggestions.append(
                {
                    "file": file_path,
                    "priority": priority,
                    "obsolete_count": len(items),
                    "high_severity_count": high_severity_count,
                    "is_mixed": is_mixed,
                    "patterns": list(patterns_found.values()),
                    "recommendation": _generate_file_recommendation(
                        file_path, items, is_mixed, patterns_found
                    ),
                }
            )

        suggestions.sort(
            key=lambda x: (
                0 if x["priority"] == "high" else 1,
                -x["high_severity_count"],
                -x["obsolete_count"],
            )
        )

        return suggestions

    def export_to_json(self, result: ClassificationResult, output_path: Path) -> None:
        """Export classification result to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "context_name": self.context_name,
            "description": self.description,
            "version": self.version,
            "generated_at": datetime.now().isoformat(),
            "classification": result.to_dict(),
            "migration_progress": result.get_migration_progress(),
            "high_priority_files": result.get_high_priority_files(),
            "migration_suggestions": self.suggest_migrations(result),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)


def _generate_file_recommendation(
    file_path: str, obsolete_items: list[dict], is_mixed: bool, patterns: dict
) -> str:
    """Generate specific recommendation for a file."""
    if is_mixed:
        return (
            f"File is partially migrated. Complete migration by updating "
            f"{len(obsolete_items)} obsolete references to use current patterns."
        )
    else:
        pattern_count = len(patterns)
        if pattern_count == 1:
            pattern = list(patterns.values())[0]
            if pattern["replacement"]:
                return f"Replace {pattern['pattern_id']} with {pattern['replacement']}"
            return f"Update {pattern['pattern_id']} usage ({pattern['reason']})"
        else:
            return f"Update {pattern_count} obsolete patterns (see details)"


def load_semantic_context(yaml_path: Path) -> SemanticContext:
    """Helper function to load semantic context."""
    return SemanticContext.load(yaml_path)
