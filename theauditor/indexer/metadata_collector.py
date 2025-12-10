"""Metadata collector for code churn and test coverage."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger


class MetadataCollector:
    """Collects temporal (churn) and quality (coverage) metadata as pure facts."""

    def __init__(self, root_path: str = "."):
        """Initialize metadata collector."""
        self.root_path = Path(root_path).resolve()

    def collect_churn(self, days: int = 90) -> dict[str, Any]:
        """Collect git churn metrics for all files."""
        cmd = [
            "git",
            "log",
            f"--since={days} days ago",
            "--format=%H|%ae|%at",
            "--name-only",
            "--no-merges",
        ]

        try:
            result = subprocess.run(
                cmd, cwd=str(self.root_path), capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                return {"error": "Not a git repository or git not available", "files": []}
        except subprocess.TimeoutExpired:
            return {"error": "Git history analysis timed out after 30 seconds", "files": []}
        except FileNotFoundError:
            return {"error": "Git command not found", "files": []}

        file_stats = {}
        current_commit = None

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            if "|" in line:
                parts = line.split("|")
                if len(parts) == 3:
                    current_commit = {
                        "hash": parts[0],
                        "author": parts[1],
                        "timestamp": int(parts[2]),
                    }
            elif current_commit:
                file_path = line.replace("\\", "/")

                if file_path not in file_stats:
                    file_stats[file_path] = {
                        "commits_90d": 0,
                        "authors": set(),
                        "last_modified": current_commit["timestamp"],
                        "first_seen": current_commit["timestamp"],
                    }

                file_stats[file_path]["commits_90d"] += 1
                file_stats[file_path]["authors"].add(current_commit["author"])

                file_stats[file_path]["last_modified"] = max(
                    file_stats[file_path]["last_modified"], current_commit["timestamp"]
                )

                file_stats[file_path]["first_seen"] = min(
                    file_stats[file_path]["first_seen"], current_commit["timestamp"]
                )

        now = datetime.now(UTC).timestamp()
        files = []

        for path, stats in file_stats.items():
            if any(skip in path for skip in [".git/", "node_modules/", "__pycache__/", ".pyc"]):
                continue

            files.append(
                {
                    "path": path,
                    "commits_90d": stats["commits_90d"],
                    "unique_authors": len(stats["authors"]),
                    "days_since_modified": int((now - stats["last_modified"]) / 86400),
                    "days_active_in_range": int(
                        (stats["last_modified"] - stats["first_seen"]) / 86400
                    ),
                }
            )

        files.sort(key=lambda x: x["commits_90d"], reverse=True)

        result = {
            "analysis_date": datetime.now(UTC).isoformat(),
            "days_analyzed": days,
            "total_files_analyzed": len(files),
            "files": files,
        }

        from theauditor.indexer.database import DatabaseManager
        from theauditor.utils.findings import format_churn_finding

        meta_findings = []
        churn_threshold = 50

        for file_data in files:
            finding = format_churn_finding(file_data, threshold=churn_threshold)
            if finding:
                meta_findings.append(finding)

        db_path = self.root_path / ".pf" / "repo_index.db"
        if db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(db_path))
                db_manager.write_findings_batch(meta_findings, "churn-analysis")
                db_manager.close()
                logger.info(f"Wrote {len(meta_findings)} churn findings to database")
            except Exception as e:
                logger.info(f"Warning: Could not write findings to database: {e}")

        return result

    def collect_coverage(self, coverage_file: str | None = None) -> dict[str, Any]:
        """Parse Python or Node.js coverage reports into pure facts."""

        if not coverage_file:
            candidates = [
                "coverage.json",
                ".coverage.json",
                "htmlcov/coverage.json",
                "coverage/coverage-final.json",
                "coverage/coverage.json",
                ".nyc_output/coverage-final.json",
                "coverage-reports/coverage.json",
            ]

            for candidate in candidates:
                candidate_path = self.root_path / candidate
                if candidate_path.exists():
                    coverage_file = str(candidate_path)
                    logger.info(f"Auto-detected coverage file: {candidate}")
                    break

        if not coverage_file:
            return {"error": "No coverage file found (tried common locations)", "files": []}

        coverage_path = Path(coverage_file)
        if not coverage_path.exists():
            coverage_path = self.root_path / coverage_file
            if not coverage_path.exists():
                return {"error": f"Coverage file not found: {coverage_file}", "files": []}

        try:
            with open(coverage_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON in coverage file: {e}", "files": []}
        except Exception as e:
            return {"error": f"Error reading coverage file: {e}", "files": []}

        files = []
        format_detected = "unknown"

        if "files" in data:
            format_detected = "python"
            for path, metrics in data["files"].items():
                path = path.replace("\\", "/")

                executed_lines = metrics.get("executed_lines", [])
                missing_lines = metrics.get("missing_lines", [])

                total_lines = len(executed_lines) + len(missing_lines)

                coverage_pct = len(executed_lines) / total_lines * 100 if total_lines > 0 else 100.0

                files.append(
                    {
                        "path": path,
                        "line_coverage_percent": round(coverage_pct, 2),
                        "lines_executed": len(executed_lines),
                        "lines_missing": len(missing_lines),
                        "uncovered_lines": missing_lines[:100],
                    }
                )

        elif isinstance(data, dict) and any(
            isinstance(v, dict) and "s" in v for v in data.values()
        ):
            format_detected = "nodejs"
            for path, metrics in data.items():
                if not isinstance(metrics, dict) or "s" not in metrics:
                    continue

                path = path.replace("\\", "/")

                statements = metrics.get("s", {})
                total_statements = len(statements)
                covered_statements = sum(1 for count in statements.values() if count > 0)

                if total_statements > 0:
                    coverage_pct = (covered_statements / total_statements) * 100
                else:
                    coverage_pct = 100.0

                uncovered = []
                if "statementMap" in metrics:
                    for stmt_id, count in statements.items():
                        if count == 0 and stmt_id in metrics["statementMap"]:
                            stmt_info = metrics["statementMap"][stmt_id]
                            if "start" in stmt_info and "line" in stmt_info["start"]:
                                uncovered.append(stmt_info["start"]["line"])

                files.append(
                    {
                        "path": path,
                        "line_coverage_percent": round(coverage_pct, 2),
                        "statements_executed": covered_statements,
                        "statements_total": total_statements,
                        "uncovered_lines": sorted(set(uncovered))[:100],
                    }
                )
        else:
            return {
                "error": "Unrecognized coverage format (expected Python coverage.py or Node.js Istanbul)",
                "files": [],
            }

        files.sort(key=lambda x: x["line_coverage_percent"])

        result = {
            "format_detected": format_detected,
            "analysis_date": datetime.now(UTC).isoformat(),
            "total_files_analyzed": len(files),
            "average_coverage": round(
                sum(f["line_coverage_percent"] for f in files) / len(files), 2
            )
            if files
            else 0.0,
            "files": files,
        }

        from theauditor.indexer.database import DatabaseManager
        from theauditor.utils.findings import format_coverage_finding

        meta_findings = []
        coverage_threshold = 50.0

        for file_data in files:
            finding = format_coverage_finding(file_data, threshold=coverage_threshold)
            if finding:
                meta_findings.append(finding)

        db_path = self.root_path / ".pf" / "repo_index.db"
        if db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(db_path))
                db_manager.write_findings_batch(meta_findings, "coverage-analysis")
                db_manager.close()
                logger.info(f"Wrote {len(meta_findings)} coverage findings to database")
            except Exception as e:
                logger.info(f"Warning: Could not write findings to database: {e}")

        return result


def main():
    """CLI entry point for testing."""
    import sys

    collector = MetadataCollector()

    if len(sys.argv) > 1 and sys.argv[1] == "churn":
        result = collector.collect_churn()
        logger.info(f"Analyzed {result.get('total_files_analyzed', 0)} files")
        if result.get("files"):
            logger.info(
                f"Most active file: {result['files'][0]['path']} "
                f"({result['files'][0]['commits_90d']} commits)"
            )

    elif len(sys.argv) > 1 and sys.argv[1] == "coverage":
        coverage_file = sys.argv[2] if len(sys.argv) > 2 else None
        result = collector.collect_coverage(coverage_file=coverage_file)
        if result.get("files"):
            logger.info(f"Format: {result['format_detected']}")
            logger.info(f"Average coverage: {result['average_coverage']}%")
            if result["files"]:
                logger.info(
                    f"Least covered: {result['files'][0]['path']} "
                    f"({result['files'][0]['line_coverage_percent']}%)"
                )
    else:
        logger.info("Usage: python metadata_collector.py [churn|coverage] [coverage_file]")


if __name__ == "__main__":
    main()
