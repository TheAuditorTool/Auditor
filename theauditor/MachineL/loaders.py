"""Historical data loaders for ML training."""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from theauditor.utils.logging import logger


def load_journal_stats(
    history_dir: Path, window: int = 50, run_type: str = "full"
) -> dict[str, dict]:
    """Load and aggregate stats from all historical journal files."""
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "touches": 0,
            "failures": 0,
            "successes": 0,
            "recent_phases": [],
        }
    )

    if run_type == "full":
        journal_files = list(history_dir.glob("full/*/journal.ndjson"))
    elif run_type == "diff":
        journal_files = list(history_dir.glob("diff/*/journal.ndjson"))
    else:
        journal_files = list(history_dir.glob("*/*/journal.ndjson"))

    if not journal_files:
        raise FileNotFoundError(
            f"No journal.ndjson files found in {history_dir}. "
            "ML model training requires execution history from journal files. "
            "Run 'aud full' at least once to generate journal data before training. "
            f"Searched for: {run_type}/*/journal.ndjson"
        )

    for journal_path in journal_files:
        try:
            with open(journal_path) as f:
                lines = f.readlines()[-window * 20 :]

                for line in lines:
                    try:
                        event = json.loads(line)

                        if event.get("phase") == "apply_patch" and "file" in event:
                            file = event["file"]
                            stats[file]["touches"] += 1

                        if "result" in event:
                            for file_path in stats:
                                if event["result"] == "fail":
                                    stats[file_path]["failures"] += 1
                                else:
                                    stats[file_path]["successes"] += 1

                    except json.JSONDecodeError:
                        continue
        except PermissionError:
            logger.warning(f"Permission denied reading: {journal_path}")
        except OSError as e:
            logger.debug(f"Could not read journal {journal_path}: {e}")

    return dict(stats)


def load_rca_stats(history_dir: Path, run_type: str = "full") -> dict[str, dict]:
    """Load RCA failure stats from all historical RCA files."""
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "fail_count": 0,
            "categories": [],
            "messages": [],
        }
    )

    if run_type == "full":
        fce_files = list(history_dir.glob("full/*/fce.json"))
    elif run_type == "diff":
        fce_files = list(history_dir.glob("diff/*/fce.json"))
    else:
        fce_files = list(history_dir.glob("*/*/fce.json"))

    for fce_path in fce_files:
        try:
            with open(fce_path) as f:
                data = json.load(f)

            for failure in data.get("failures", []):
                file = failure.get("file", "")
                if file:
                    stats[file]["fail_count"] += 1
                    if "category" in failure:
                        stats[file]["categories"].append(failure["category"])
                    if "message" in failure:
                        stats[file]["messages"].append(failure["message"][:100])
        except json.JSONDecodeError as e:
            logger.debug(f"Corrupt JSON in {fce_path}: {e}")
        except PermissionError:
            logger.warning(f"Permission denied reading: {fce_path}")
        except OSError as e:
            logger.debug(f"Could not read {fce_path}: {e}")

    return dict(stats)


def load_ast_stats(history_dir: Path, run_type: str = "full") -> dict[str, dict]:
    """Load AST proof stats from all historical AST files."""
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "invariant_fails": 0,
            "invariant_passes": 0,
            "failed_checks": [],
        }
    )

    if run_type == "full":
        ast_files = list(history_dir.glob("full/*/ast_proofs.json"))
    elif run_type == "diff":
        ast_files = list(history_dir.glob("diff/*/ast_proofs.json"))
    else:
        ast_files = list(history_dir.glob("*/*/ast_proofs.json"))

    for ast_path in ast_files:
        try:
            with open(ast_path) as f:
                data = json.load(f)

            for result in data.get("results", []):
                file = result.get("path", "")
                for check in result.get("checks", []):
                    if check["status"] == "FAIL":
                        stats[file]["invariant_fails"] += 1
                        stats[file]["failed_checks"].append(check["id"])
                    elif check["status"] == "PASS":
                        stats[file]["invariant_passes"] += 1
        except json.JSONDecodeError as e:
            logger.debug(f"Corrupt JSON in {ast_path}: {e}")
        except PermissionError:
            logger.warning(f"Permission denied reading: {ast_path}")
        except OSError as e:
            logger.debug(f"Could not read {ast_path}: {e}")
        except KeyError as e:
            logger.debug(f"Missing key in AST data {ast_path}: {e}")

    return dict(stats)


def load_historical_findings(history_dir: Path, run_type: str = "full") -> dict[str, dict]:
    """Load historical findings from findings_consolidated table in past runs."""
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "total_findings": 0,
            "critical_count": 0,
            "high_count": 0,
            "recurring_cwes": [],
        }
    )

    if run_type == "full":
        db_files = list(history_dir.glob("full/*/repo_index.db"))
    elif run_type == "diff":
        db_files = list(history_dir.glob("diff/*/repo_index.db"))
    else:
        db_files = list(history_dir.glob("*/*/repo_index.db"))

    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, severity, cwe, COUNT(*) as count
                FROM findings_consolidated
                GROUP BY file, severity, cwe
            """)

            for file_path, severity, cwe, count in cursor.fetchall():
                stats[file_path]["total_findings"] += count
                if severity == "critical":
                    stats[file_path]["critical_count"] += count
                elif severity == "high":
                    stats[file_path]["high_count"] += count
                if cwe:
                    stats[file_path]["recurring_cwes"].append(cwe)

            conn.close()
        except sqlite3.Error as e:
            logger.debug(f"DB error reading {db_path}: {e}")
        except PermissionError:
            logger.warning(f"Permission denied reading: {db_path}")

    return dict(stats)


def load_git_churn(
    file_paths: list[str], window_days: int = 90, root_path: Path = Path(".")
) -> dict[str, dict]:
    """Load git churn data with author diversity and recency."""
    if not (root_path / ".git").exists():
        return {}

    try:
        from . import intelligence

        return intelligence.parse_git_churn(
            root_path=root_path, days=window_days, file_paths=file_paths
        )
    except ImportError:
        return {}
    except OSError as e:
        logger.debug(f"Git churn collection failed: {e}")
        return {}


def load_all_historical_data(
    history_dir: Path, run_type: str = "full", window: int = 50, enable_git: bool = False
) -> dict:
    """Convenience function to load all historical data at once."""
    return {
        "journal_stats": load_journal_stats(history_dir, window, run_type),
        "rca_stats": load_rca_stats(history_dir, run_type),
        "ast_stats": load_ast_stats(history_dir, run_type),
        "historical_findings": load_historical_findings(history_dir, run_type),
        "git_churn": {},
    }
