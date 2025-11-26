"""Metadata collector for code churn and test coverage.

This module collects temporal (git history) and quality (test coverage) metadata
to provide additional factual dimensions for the FCE correlation engine.
Maintains Truth Courier principles - reports only facts, no interpretation.
"""


import json
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, UTC


class MetadataCollector:
    """Collects temporal (churn) and quality (coverage) metadata as pure facts."""

    def __init__(self, root_path: str = "."):
        """Initialize metadata collector.
        
        Args:
            root_path: Root directory of the project to analyze
        """
        self.root_path = Path(root_path).resolve()

    def collect_churn(self, days: int = 90, output_path: str | None = None) -> dict[str, Any]:
        """Collect git churn metrics for all files.
        
        Returns pure facts:
        - commits_90d: Number of commits in last N days (mathematical count)
        - days_since_modified: Days since last modification (mathematical difference)
        - unique_authors: Number of distinct authors (mathematical count)
        
        Args:
            days: Number of days to analyze (default 90)
            output_path: Optional path to save JSON output
            
        Returns:
            Dictionary with churn metrics per file
        """
        cmd = [
            "git", "log", 
            f"--since={days} days ago",
            "--format=%H|%ae|%at",
            "--name-only",
            "--no-merges"  # Exclude merge commits for cleaner metrics
        ]

        try:
            result = subprocess.run(
                cmd, 
                cwd=str(self.root_path), 
                capture_output=True, 
                text=True,
                timeout=30  # Prevent hanging on huge repos
            )

            if result.returncode != 0:
                return {
                    "error": "Not a git repository or git not available",
                    "files": []
                }
        except subprocess.TimeoutExpired:
            return {
                "error": f"Git history analysis timed out after 30 seconds",
                "files": []
            }
        except FileNotFoundError:
            return {
                "error": "Git command not found",
                "files": []
            }

        # Parse git log output into file metrics
        file_stats = {}
        current_commit = None

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            if '|' in line:  # Commit line: hash|author|timestamp
                parts = line.split('|')
                if len(parts) == 3:
                    current_commit = {
                        'hash': parts[0],
                        'author': parts[1],
                        'timestamp': int(parts[2])
                    }
            elif current_commit:  # File line
                # Normalize path separators for Windows
                file_path = line.replace('\\', '/')

                if file_path not in file_stats:
                    file_stats[file_path] = {
                        'commits_90d': 0,
                        'authors': set(),
                        'last_modified': current_commit['timestamp'],
                        'first_seen': current_commit['timestamp']
                    }

                file_stats[file_path]['commits_90d'] += 1
                file_stats[file_path]['authors'].add(current_commit['author'])
                # Track most recent modification
                file_stats[file_path]['last_modified'] = max(
                    file_stats[file_path]['last_modified'], 
                    current_commit['timestamp']
                )
                # Track oldest modification in range
                file_stats[file_path]['first_seen'] = min(
                    file_stats[file_path]['first_seen'],
                    current_commit['timestamp']
                )

        # Convert to final format with pure facts only
        now = datetime.now(UTC).timestamp()
        files = []

        for path, stats in file_stats.items():
            # Skip common non-source files
            if any(skip in path for skip in ['.git/', 'node_modules/', '__pycache__/', '.pyc']):
                continue

            files.append({
                'path': path,
                'commits_90d': stats['commits_90d'],  # Fact: count
                'unique_authors': len(stats['authors']),  # Fact: count
                'days_since_modified': int((now - stats['last_modified']) / 86400),  # Fact: time delta
                'days_active_in_range': int((stats['last_modified'] - stats['first_seen']) / 86400)  # Fact: time span
            })

        # Sort by commit count descending for easier analysis
        files.sort(key=lambda x: x['commits_90d'], reverse=True)

        result = {
            'analysis_date': datetime.now(UTC).isoformat(),
            'days_analyzed': days,
            'total_files_analyzed': len(files),
            'files': files
        }

        # DUAL-WRITE PATTERN: Write to database for FCE performance + JSON for AI consumption
        from theauditor.utils.meta_findings import format_churn_finding
        from theauditor.indexer.database import DatabaseManager

        # Prepare meta-findings for database
        meta_findings = []
        churn_threshold = 50  # Flag files with 50+ commits

        for file_data in files:
            finding = format_churn_finding(file_data, threshold=churn_threshold)
            if finding:
                meta_findings.append(finding)

        # Write findings to database if available
        db_path = self.root_path / '.pf' / 'repo_index.db'
        if db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(db_path))
                db_manager.write_findings_batch(meta_findings, "churn-analysis")
                db_manager.close()
                print(f"[METADATA] Wrote {len(meta_findings)} churn findings to database")
            except Exception as e:
                print(f"[METADATA] Warning: Could not write findings to database: {e}")

        # Save to file if path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            print(f"[METADATA] Churn analysis saved to {output_path}")

        return result

    def collect_coverage(self, coverage_file: str | None = None, 
                        output_path: str | None = None) -> dict[str, Any]:
        """Parse Python or Node.js coverage reports into pure facts.
        
        Detects format automatically:
        - Python: coverage.json from coverage.py with 'files' key
        - Node.js: coverage-final.json from Istanbul/nyc
        
        Args:
            coverage_file: Path to coverage file (auto-detects if not provided)
            output_path: Optional path to save JSON output
            
        Returns:
            Dictionary with coverage facts per file
        """
        # Auto-detect coverage file if not provided
        if not coverage_file:
            candidates = [
                'coverage.json',
                '.coverage.json',
                'htmlcov/coverage.json',
                'coverage/coverage-final.json',
                'coverage/coverage.json',
                '.nyc_output/coverage-final.json',
                'coverage-reports/coverage.json'
            ]

            for candidate in candidates:
                candidate_path = self.root_path / candidate
                if candidate_path.exists():
                    coverage_file = str(candidate_path)
                    print(f"[METADATA] Auto-detected coverage file: {candidate}")
                    break

        if not coverage_file:
            return {
                "error": "No coverage file found (tried common locations)",
                "files": []
            }

        coverage_path = Path(coverage_file)
        if not coverage_path.exists():
            # Try relative to root
            coverage_path = self.root_path / coverage_file
            if not coverage_path.exists():
                return {
                    "error": f"Coverage file not found: {coverage_file}",
                    "files": []
                }

        try:
            with open(coverage_path, encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid JSON in coverage file: {e}",
                "files": []
            }
        except Exception as e:
            return {
                "error": f"Error reading coverage file: {e}",
                "files": []
            }

        files = []
        format_detected = 'unknown'

        # Detect and parse Python coverage.py format
        if 'files' in data:
            format_detected = 'python'
            for path, metrics in data['files'].items():
                # Normalize path
                path = path.replace('\\', '/')

                # Calculate coverage percentage (pure math fact)
                executed_lines = metrics.get('executed_lines', [])
                missing_lines = metrics.get('missing_lines', [])

                # Total executable lines (excluding comments, blank lines, etc.)
                total_lines = len(executed_lines) + len(missing_lines)

                if total_lines > 0:
                    coverage_pct = (len(executed_lines) / total_lines) * 100
                else:
                    coverage_pct = 100.0  # No executable lines = fully covered

                files.append({
                    'path': path,
                    'line_coverage_percent': round(coverage_pct, 2),  # Fact: percentage
                    'lines_executed': len(executed_lines),  # Fact: count
                    'lines_missing': len(missing_lines),  # Fact: count
                    'uncovered_lines': missing_lines[:100]  # Fact: line numbers (limit for size)
                })

        # Detect and parse Node.js Istanbul/nyc format
        elif isinstance(data, dict) and any(
            isinstance(v, dict) and 's' in v 
            for v in data.values()
        ):
            format_detected = 'nodejs'
            for path, metrics in data.items():
                if not isinstance(metrics, dict) or 's' not in metrics:
                    continue

                # Normalize path
                path = path.replace('\\', '/')

                # Statement coverage (s = statement execution counts)
                statements = metrics.get('s', {})
                total_statements = len(statements)
                covered_statements = sum(1 for count in statements.values() if count > 0)

                if total_statements > 0:
                    coverage_pct = (covered_statements / total_statements) * 100
                else:
                    coverage_pct = 100.0

                # Find uncovered lines from statement map
                uncovered = []
                if 'statementMap' in metrics:
                    for stmt_id, count in statements.items():
                        if count == 0 and stmt_id in metrics['statementMap']:
                            stmt_info = metrics['statementMap'][stmt_id]
                            if 'start' in stmt_info and 'line' in stmt_info['start']:
                                uncovered.append(stmt_info['start']['line'])

                files.append({
                    'path': path,
                    'line_coverage_percent': round(coverage_pct, 2),  # Fact: percentage
                    'statements_executed': covered_statements,  # Fact: count
                    'statements_total': total_statements,  # Fact: count
                    'uncovered_lines': sorted(set(uncovered))[:100]  # Fact: line numbers
                })
        else:
            return {
                "error": "Unrecognized coverage format (expected Python coverage.py or Node.js Istanbul)",
                "files": []
            }

        # Sort by coverage percentage ascending (least covered first)
        files.sort(key=lambda x: x['line_coverage_percent'])

        result = {
            'format_detected': format_detected,
            'analysis_date': datetime.now(UTC).isoformat(),
            'total_files_analyzed': len(files),
            'average_coverage': round(
                sum(f['line_coverage_percent'] for f in files) / len(files), 2
            ) if files else 0.0,
            'files': files
        }

        # DUAL-WRITE PATTERN: Write to database for FCE performance + JSON for AI consumption
        from theauditor.utils.meta_findings import format_coverage_finding
        from theauditor.indexer.database import DatabaseManager

        # Prepare meta-findings for database
        meta_findings = []
        coverage_threshold = 50.0  # Flag files with <50% coverage

        for file_data in files:
            finding = format_coverage_finding(file_data, threshold=coverage_threshold)
            if finding:
                meta_findings.append(finding)

        # Write findings to database if available
        db_path = self.root_path / '.pf' / 'repo_index.db'
        if db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(db_path))
                db_manager.write_findings_batch(meta_findings, "coverage-analysis")
                db_manager.close()
                print(f"[METADATA] Wrote {len(meta_findings)} coverage findings to database")
            except Exception as e:
                print(f"[METADATA] Warning: Could not write findings to database: {e}")

        # Save to file if path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            print(f"[METADATA] Coverage analysis saved to {output_path}")

        return result


def main():
    """CLI entry point for testing."""
    import sys

    collector = MetadataCollector()

    if len(sys.argv) > 1 and sys.argv[1] == 'churn':
        result = collector.collect_churn(output_path='.pf/raw/churn_analysis.json')
        print(f"Analyzed {result.get('total_files_analyzed', 0)} files")
        if result.get('files'):
            print(f"Most active file: {result['files'][0]['path']} "
                  f"({result['files'][0]['commits_90d']} commits)")

    elif len(sys.argv) > 1 and sys.argv[1] == 'coverage':
        coverage_file = sys.argv[2] if len(sys.argv) > 2 else None
        result = collector.collect_coverage(
            coverage_file=coverage_file,
            output_path='.pf/raw/coverage_analysis.json'
        )
        if result.get('files'):
            print(f"Format: {result['format_detected']}")
            print(f"Average coverage: {result['average_coverage']}%")
            if result['files']:
                print(f"Least covered: {result['files'][0]['path']} "
                      f"({result['files'][0]['line_coverage_percent']}%)")
    else:
        print("Usage: python metadata_collector.py [churn|coverage] [coverage_file]")


if __name__ == '__main__':
    main()