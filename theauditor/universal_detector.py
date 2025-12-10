"""Universal pattern detector - AST-first approach with minimal regex fallback."""

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from theauditor.ast_extractors.ast_parser import ASTParser
from theauditor.rules.orchestrator import RuleContext, RulesOrchestrator
from theauditor.utils.logging import logger


@dataclass
class Finding:
    """Represents a pattern finding."""

    pattern_name: str
    message: str
    file: str
    line: int
    column: int
    severity: str
    snippet: str
    category: str
    match_type: str = "ast"

    def to_dict(self):
        """Convert finding to dictionary."""
        return asdict(self)


class UniversalPatternDetector:
    """Coordinates pattern detection using AST-first approach."""

    AST_SUPPORTED = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

    def __init__(
        self,
        project_path: Path,
        with_ast: bool = True,
        with_frameworks: bool = True,
        exclude_patterns: list[str] = None,
    ):
        """Initialize detector."""
        self.project_path = Path(project_path).resolve()
        self.findings: list[Finding] = []
        self.exclude_patterns = exclude_patterns or []

        self.orchestrator = RulesOrchestrator(
            project_path=self.project_path, db_path=self.project_path / ".pf" / "repo_index.db"
        )

        self.ast_parser = ASTParser()

        stats = self.orchestrator.get_rule_stats()
        logger.debug(f"[DETECTOR] Orchestrator loaded {stats['total_rules']} rules")

    def detect_patterns(
        self, categories: list[str] | None = None, file_filter: str | None = None
    ) -> list[Finding]:
        """Run pattern detection across project."""
        self.findings = []

        db_path = self.project_path / ".pf" / "repo_index.db"
        if not db_path.exists():
            logger.info("Error: Database not found. Run 'aud full' first.")
            return []

        files_to_scan = self._query_files(db_path, file_filter)
        if not files_to_scan:
            logger.info("No files to scan.")
            return []

        logger.info(f"Found {len(files_to_scan)} files to scan...")

        ast_files = [f for f in files_to_scan if f[1] in self.AST_SUPPORTED]

        if ast_files:
            logger.info(f"Processing {len(ast_files)} files with AST analysis...")
            self._process_ast_files(ast_files)

        logger.info("Running database-aware rules...")
        db_findings = self._run_database_rules()
        self.findings.extend(db_findings)

        logger.info(f"Total findings: {len(self.findings)}")
        return self.findings

    def detect_patterns_for_files(
        self, file_list: list[str], categories: list[str] = None
    ) -> list[Finding]:
        """Targeted pattern detection for specific files."""
        if not file_list:
            return []

        self.findings = []

        normalized_files = []
        for f in file_list:
            try:
                rel_path = Path(f).relative_to(self.project_path)
            except ValueError:
                rel_path = Path(f)
            normalized_files.append(rel_path)

        db_path = self.project_path / ".pf" / "repo_index.db"
        if not db_path.exists():
            logger.info("Error: Database not found. Run 'aud full' first.")
            return []

        files_to_scan = self._query_specific_files(db_path, normalized_files)

        ast_files = [f for f in files_to_scan if f[1] in self.AST_SUPPORTED]

        if ast_files:
            self._process_ast_files(ast_files)

        return self.findings

    def _query_files(self, db_path: Path, file_filter: str = None) -> list[tuple]:
        """Query files from database."""
        files = []

        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()

            if file_filter:
                query = "SELECT path, ext, sha256 FROM files WHERE path GLOB ?"
                rows = cursor.execute(query, (file_filter,)).fetchall()
            else:
                query = "SELECT path, ext, sha256 FROM files"
                rows = cursor.execute(query).fetchall()

            for path, ext, sha256_hash in rows:
                full_path = self.project_path / path
                files.append((full_path, ext, sha256_hash))

        return files

    def _query_specific_files(self, db_path: Path, file_list: list[Path]) -> list[tuple]:
        """Query specific files from database."""
        files = []

        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()

            path_strings = [p.as_posix() for p in file_list]

            placeholders = ",".join(["?"] * len(path_strings))
            query = f"SELECT path, ext, sha256 FROM files WHERE path IN ({placeholders})"

            rows = cursor.execute(query, path_strings).fetchall()

            for path, ext, sha256_hash in rows:
                full_path = self.project_path / path
                files.append((full_path, ext, sha256_hash))

        return files

    def _process_ast_files(self, files: list[tuple]):
        """Process AST-parseable files through orchestrator."""

        max_workers = min(8, os.cpu_count() or 4)

        def process_file(file_info):
            """Process single file through orchestrator."""
            file_path, ext, _sha256_hash = file_info
            local_findings = []

            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                language = "python" if ext == ".py" else "javascript"

                ast_result = self.ast_parser.parse_content(content, language, str(file_path))
                ast_tree = None

                if ast_result:
                    ast_tree = ast_result
                    if os.environ.get("THEAUDITOR_DEBUG", "").lower() == "true":
                        ast_type = ast_result.get("type", "unknown")
                        logger.debug(f"Parsed {file_path} as {ast_type}")
                else:
                    logger.warning(f"Failed to parse AST for {file_path}")

                context = RuleContext(
                    file_path=file_path,
                    content=content,
                    ast_tree=ast_tree,
                    language=language,
                    db_path=str(self.project_path / ".pf" / "repo_index.db"),
                    project_path=self.project_path,
                )

                rule_findings = self.orchestrator.run_rules_for_file(context)

                for finding in rule_findings:
                    local_findings.append(
                        Finding(
                            pattern_name=finding.get(
                                "rule", finding.get("pattern_name", finding.get("type", "UNKNOWN"))
                            ),
                            message=finding.get("message", "Issue detected"),
                            file=str(file_path.relative_to(self.project_path)),
                            line=finding.get("line") or 0,
                            column=finding.get("column") or finding.get("col") or 0,
                            severity=finding.get("severity", "medium").lower(),
                            snippet=finding.get("snippet", finding.get("hint", ""))[:200],
                            category=finding.get("category", "security"),
                            match_type="ast",
                        )
                    )

            except Exception as e:
                logger.debug(f"Error processing {file_path}: {e}")

            return local_findings

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_file, f) for f in files]

            for future in as_completed(futures):
                try:
                    file_findings = future.result()
                    self.findings.extend(file_findings)
                except Exception as e:
                    logger.debug(f"Worker error: {e}")

    def _run_database_rules(self) -> list[Finding]:
        """Run database-level rules through orchestrator."""
        findings = []

        db_findings = self.orchestrator.run_database_rules()

        for finding in db_findings:
            findings.append(
                Finding(
                    pattern_name=finding.get("rule", finding.get("pattern_name", "DATABASE_RULE")),
                    message=finding.get("message", "Database issue detected"),
                    file=finding.get("file", ""),
                    line=finding.get("line") or 0,
                    column=finding.get("column") or 0,
                    severity=finding.get("severity", "medium").lower(),
                    snippet=finding.get("snippet", "")[:200],
                    category=finding.get("category", "database"),
                    match_type="database",
                )
            )

        return findings

    def format_table(self, max_rows: int = 50) -> str:
        """Format findings as a human-readable table."""
        if not self.findings:
            return "No issues found."

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_findings = sorted(
            self.findings, key=lambda f: (severity_order.get(f.severity, 4), f.file, f.line or 0)
        )

        lines = []
        lines.append(
            "PATTERN                          FILE                             LINE  SEVERITY"
        )
        lines.append("-" * 80)

        for _i, finding in enumerate(sorted_findings[:max_rows]):
            pattern = finding.pattern_name[:32].ljust(32)
            file_str = finding.file
            if len(file_str) > 35:
                file_str = "..." + file_str[-32:]
            file_str = file_str.ljust(35)

            line = f"{pattern} {file_str} {finding.line:4d}  {finding.severity.upper()}"
            lines.append(line)

        if len(sorted_findings) > max_rows:
            lines.append(f"\n... and {len(sorted_findings) - max_rows} more findings")
            lines.append("\nTIP: Use --json for full output (pipe to file if needed)")

        return "\n".join(lines)

    def to_json(self, output_file: Path | None = None) -> str:
        """Export findings to JSON."""
        data = {"findings": [f.to_dict() for f in self.findings]}

        json_str = json.dumps(data, indent=2, sort_keys=True)

        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json_str)
            logger.info(f"Findings written to {output_file}")

        return json_str

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics of findings."""
        stats = {
            "total_findings": len(self.findings),
            "by_severity": {},
            "by_category": {},
            "by_pattern": {},
            "files_affected": len({f.file for f in self.findings}),
        }

        for finding in self.findings:
            severity = finding.severity
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

            category = finding.category
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1

            pattern = finding.pattern_name
            stats["by_pattern"][pattern] = stats["by_pattern"].get(pattern, 0) + 1

        return stats
