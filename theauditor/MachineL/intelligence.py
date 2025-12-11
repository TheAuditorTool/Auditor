"""Intelligent parsers for raw artifacts and structured events."""

import json
import re
from collections import defaultdict
from pathlib import Path

from theauditor.utils.logging import logger


def parse_pipeline_log(log_path: Path) -> dict[str, dict]:
    """Extract phase-level execution data from pipeline.log."""
    if not log_path.exists():
        return {}

    phase_stats = {}

    try:
        with open(log_path, encoding="utf-8") as f:
            content = f.read()

        phase_pattern = re.compile(r"\[Phase (\d+)/\d+\] (.+)")
        ok_pattern = re.compile(r"\[OK\] (.+?) completed in ([\d.]+)s")
        critical_pattern = re.compile(r"\[OK\] (.+?) completed in ([\d.]+)s - CRITICAL findings")
        high_pattern = re.compile(r"\[OK\] (.+?) completed in ([\d.]+)s - HIGH findings")
        failed_pattern = re.compile(r"\[FAILED\] (.+?) failed")

        lines = content.split("\n")
        current_phase = None
        current_phase_num = None

        for line in lines:
            phase_match = phase_pattern.search(line)
            if phase_match:
                current_phase_num = int(phase_match.group(1))
                current_phase = phase_match.group(2)
                continue

            if current_phase:
                critical_match = critical_pattern.search(line)
                if critical_match:
                    phase_name = critical_match.group(1)
                    elapsed = float(critical_match.group(2))
                    phase_stats[phase_name] = {
                        "elapsed": elapsed,
                        "status": "success",
                        "phase_num": current_phase_num,
                        "exit_code": 2,
                        "findings_level": "critical",
                    }
                    current_phase = None
                    continue

                high_match = high_pattern.search(line)
                if high_match:
                    phase_name = high_match.group(1)
                    elapsed = float(high_match.group(2))
                    phase_stats[phase_name] = {
                        "elapsed": elapsed,
                        "status": "success",
                        "phase_num": current_phase_num,
                        "exit_code": 1,
                        "findings_level": "high",
                    }
                    current_phase = None
                    continue

                ok_match = ok_pattern.search(line)
                if ok_match:
                    phase_name = ok_match.group(1)
                    elapsed = float(ok_match.group(2))
                    phase_stats[phase_name] = {
                        "elapsed": elapsed,
                        "status": "success",
                        "phase_num": current_phase_num,
                        "exit_code": 0,
                    }
                    current_phase = None
                    continue

                failed_match = failed_pattern.search(line)
                if failed_match:
                    phase_name = failed_match.group(1)
                    phase_stats[phase_name] = {
                        "elapsed": 0.0,
                        "status": "failed",
                        "phase_num": current_phase_num,
                        "exit_code": -1,
                    }
                    current_phase = None
                    continue

    except PermissionError:
        logger.warning(f"Permission denied reading pipeline log: {log_path}")
    except OSError as e:
        logger.warning(f"OS error reading pipeline log {log_path}: {e}")

    return phase_stats


def parse_journal_events(journal_path: Path) -> dict:
    """Extract ALL journal event types (not just apply_patch!)."""
    if not journal_path.exists():
        return {
            "phase_timing": {},
            "file_touches": {},
            "findings_by_file": {},
            "patches": {},
            "pipeline_summary": {},
        }

    phase_timing = {}
    file_touches = defaultdict(lambda: {"touches": 0, "findings": 0})
    findings_by_file = defaultdict(list)
    patches = defaultdict(lambda: {"success": 0, "failed": 0})
    pipeline_summary = {}

    try:
        with open(journal_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    event_type = event.get("event_type")

                    if event_type == "phase_start":
                        phase = event.get("phase")
                        if phase and phase not in phase_timing:
                            phase_timing[phase] = {"start_time": event.get("timestamp")}

                    elif event_type == "phase_end":
                        phase = event.get("phase")
                        if phase:
                            phase_timing[phase] = {
                                "elapsed": event.get("elapsed", 0.0),
                                "status": event.get("result", "unknown"),
                                "exit_code": event.get("exit_code", 0),
                                "end_time": event.get("timestamp"),
                            }

                    elif event_type == "file_touch":
                        file_path = event.get("file")
                        if file_path:
                            file_touches[file_path]["touches"] += 1
                            file_touches[file_path]["findings"] += event.get("findings", 0)
                            if event.get("result") == "fail":
                                file_touches[file_path]["failures"] = (
                                    file_touches[file_path].get("failures", 0) + 1
                                )

                    elif event_type == "finding":
                        file_path = event.get("file")
                        if file_path:
                            findings_by_file[file_path].append(
                                {
                                    "severity": event.get("severity"),
                                    "category": event.get("category"),
                                    "message": event.get("message"),
                                    "line": event.get("line"),
                                }
                            )

                    elif event_type == "apply_patch":
                        file_path = event.get("file")
                        if file_path:
                            if event.get("result") == "success":
                                patches[file_path]["success"] += 1
                            else:
                                patches[file_path]["failed"] += 1

                    elif event_type == "pipeline_summary":
                        pipeline_summary = {
                            "total_phases": event.get("total_phases", 0),
                            "failed_phases": event.get("failed_phases", 0),
                            "total_files": event.get("total_files", 0),
                            "total_findings": event.get("total_findings", 0),
                            "elapsed": event.get("elapsed", 0.0),
                            "status": event.get("status", "unknown"),
                        }

                except json.JSONDecodeError:
                    continue

    except PermissionError:
        logger.warning(f"Permission denied reading journal: {journal_path}")
    except OSError as e:
        logger.warning(f"OS error reading journal {journal_path}: {e}")

    return {
        "phase_timing": dict(phase_timing),
        "file_touches": dict(file_touches),
        "findings_by_file": dict(findings_by_file),
        "patches": dict(patches),
        "pipeline_summary": pipeline_summary,
    }


def parse_taint_analysis(raw_path: Path) -> dict[str, dict]:
    """Parse raw/taint_analysis.json for detailed vulnerability data."""
    file_path = raw_path / "taint_analysis.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "vulnerability_paths": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "cwe_list": [],
            "max_taint_path_length": 0,
        }
    )

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        for finding in data.get("findings", []):
            file = finding.get("file", "")
            if not file:
                continue

            stats[file]["vulnerability_paths"] += 1

            severity = finding.get("severity", "").lower()
            if severity == "critical":
                stats[file]["critical_count"] += 1
            elif severity == "high":
                stats[file]["high_count"] += 1
            elif severity == "medium":
                stats[file]["medium_count"] += 1

            cwe = finding.get("cwe")
            if cwe and cwe not in stats[file]["cwe_list"]:
                stats[file]["cwe_list"].append(cwe)

            path_length = len(finding.get("taint_path", []))
            if path_length > stats[file]["max_taint_path_length"]:
                stats[file]["max_taint_path_length"] = path_length

    except json.JSONDecodeError as e:
        logger.warning(f"Corrupt JSON in taint_analysis.json: {e}")
    except PermissionError:
        logger.warning(f"Permission denied reading: {file_path}")
    except OSError as e:
        logger.warning(f"OS error reading {file_path}: {e}")

    return dict(stats)


def parse_vulnerabilities(raw_path: Path) -> dict[str, dict]:
    """Query findings_consolidated for vulnerability findings (tool='vulnerability_scanner')."""
    import sqlite3

    db_path = raw_path.parent / "repo_index.db"
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, severity, confidence
        FROM findings_consolidated
        WHERE tool = 'vulnerability_scanner'
    """)

    stats = defaultdict(
        lambda: {
            "cve_count": 0,
            "max_cvss_score": 0.0,
            "critical_cves": 0,
            "high_cves": 0,
            "exploitable_count": 0,
        }
    )

    for file, severity, confidence in cursor.fetchall():
        if not file:
            continue

        stats[file]["cve_count"] += 1

        if severity == "critical":
            stats[file]["critical_cves"] += 1
            stats[file]["max_cvss_score"] = max(stats[file]["max_cvss_score"], 9.5)
        elif severity == "high":
            stats[file]["high_cves"] += 1
            stats[file]["max_cvss_score"] = max(stats[file]["max_cvss_score"], 7.5)
        elif severity == "medium":
            stats[file]["max_cvss_score"] = max(stats[file]["max_cvss_score"], 5.0)

        if confidence and confidence >= 0.9:
            stats[file]["exploitable_count"] += 1

    conn.close()
    return dict(stats)


def parse_patterns(raw_path: Path) -> dict[str, dict]:
    """Query findings_consolidated for pattern detection findings (tool='patterns')."""
    import sqlite3

    db_path = raw_path.parent / "repo_index.db"
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, category, rule
        FROM findings_consolidated
        WHERE tool = 'patterns'
    """)

    stats = defaultdict(
        lambda: {
            "hardcoded_secrets": 0,
            "weak_crypto": 0,
            "insecure_random": 0,
            "dangerous_functions": 0,
            "total_patterns": 0,
        }
    )

    for file, category, rule in cursor.fetchall():
        if not file:
            continue

        stats[file]["total_patterns"] += 1

        cat_lower = (category or "").lower()
        rule_lower = (rule or "").lower()
        combined = f"{cat_lower} {rule_lower}"

        if (
            "secret" in combined
            or "password" in combined
            or "key" in combined
            or "credential" in combined
        ):
            stats[file]["hardcoded_secrets"] += 1
        elif "crypto" in combined or "md5" in combined or "sha1" in combined or "hash" in combined:
            stats[file]["weak_crypto"] += 1
        elif "random" in combined:
            stats[file]["insecure_random"] += 1
        elif "dangerous" in combined or "eval" in combined or "exec" in combined:
            stats[file]["dangerous_functions"] += 1

    conn.close()
    return dict(stats)


def parse_fce(raw_path: Path) -> dict[str, dict]:
    """Parse raw/fce.json for factual correlation analysis."""
    file_path = raw_path / "fce.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(
        lambda: {"failure_correlations": 0, "cross_file_dependencies": 0, "hotspot_score": 0.0}
    )

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        for correlation in data.get("correlations", []):
            file = correlation.get("file", "")
            if file:
                stats[file]["failure_correlations"] += 1

        for hotspot in data.get("hotspots", []):
            file = hotspot.get("file", "")
            if file:
                score = hotspot.get("score", 0.0)
                stats[file]["hotspot_score"] = max(stats[file]["hotspot_score"], score)

        for dep in data.get("dependencies", []):
            source = dep.get("source", "")
            if source:
                stats[source]["cross_file_dependencies"] += 1

    except json.JSONDecodeError as e:
        logger.warning(f"Corrupt JSON in fce.json: {e}")
    except PermissionError:
        logger.warning(f"Permission denied reading: {file_path}")
    except OSError as e:
        logger.warning(f"OS error reading {file_path}: {e}")

    return dict(stats)


def parse_cfg_analysis(raw_path: Path) -> dict[str, dict]:
    """Parse raw/cfg_analysis.json for control flow complexity per function."""
    file_path = raw_path / "cfg_analysis.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "max_cyclomatic_complexity": 0,
            "avg_cyclomatic_complexity": 0.0,
            "complex_function_count": 0,
            "total_functions": 0,
        }
    )

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        file_functions = defaultdict(list)

        for func_data in data.get("functions", []):
            file = func_data.get("file", "")
            if not file:
                continue

            complexity = func_data.get("cyclomatic_complexity", 0)
            file_functions[file].append(complexity)

            if complexity > stats[file]["max_cyclomatic_complexity"]:
                stats[file]["max_cyclomatic_complexity"] = complexity

            if complexity > 10:
                stats[file]["complex_function_count"] += 1

        for file, complexities in file_functions.items():
            stats[file]["total_functions"] = len(complexities)
            stats[file]["avg_cyclomatic_complexity"] = (
                sum(complexities) / len(complexities) if complexities else 0.0
            )

    except json.JSONDecodeError as e:
        logger.warning(f"Corrupt JSON in cfg_analysis.json: {e}")
    except PermissionError:
        logger.warning(f"Permission denied reading: {file_path}")
    except OSError as e:
        logger.warning(f"OS error reading {file_path}: {e}")

    return dict(stats)


def parse_frameworks(raw_path: Path) -> dict[str, dict]:
    """Parse raw/frameworks.json for detected frameworks and versions."""
    file_path = raw_path / "frameworks.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(
        lambda: {"frameworks": [], "has_vulnerable_version": False, "framework_count": 0}
    )

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        for detection in data.get("detected", []):
            file = detection.get("file", "")
            if not file:
                continue

            framework = detection.get("framework", "").lower()
            if framework and framework not in stats[file]["frameworks"]:
                stats[file]["frameworks"].append(framework)
                stats[file]["framework_count"] += 1

            if detection.get("vulnerable", False):
                stats[file]["has_vulnerable_version"] = True

    except json.JSONDecodeError as e:
        logger.warning(f"Corrupt JSON in frameworks.json: {e}")
    except PermissionError:
        logger.warning(f"Permission denied reading: {file_path}")
    except OSError as e:
        logger.warning(f"OS error reading {file_path}: {e}")

    return dict(stats)


def parse_graph_metrics(raw_path: Path) -> dict[str, float]:
    """Parse raw/graph_metrics.json for centrality scores."""
    file_path = raw_path / "graph_metrics.json"
    if not file_path.exists():
        return {}

    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(f"Corrupt JSON in graph_metrics.json: {e}")
        return {}
    except PermissionError:
        logger.warning(f"Permission denied reading: {file_path}")
        return {}
    except OSError as e:
        logger.warning(f"OS error reading {file_path}: {e}")
        return {}


def parse_all_raw_artifacts(raw_dir: Path) -> dict:
    """Parse ALL raw/*.json files and combine into unified feature dict."""
    if not raw_dir.exists():
        return {}

    return {
        "taint": parse_taint_analysis(raw_dir),
        "vulnerabilities": parse_vulnerabilities(raw_dir),
        "patterns": parse_patterns(raw_dir),
        "fce": parse_fce(raw_dir),
        "cfg": parse_cfg_analysis(raw_dir),
        "frameworks": parse_frameworks(raw_dir),
        "graph_metrics": parse_graph_metrics(raw_dir),
    }


def parse_git_churn(
    root_path: Path, days: int = 90, file_paths: list[str] | None = None
) -> dict[str, dict]:
    """Parse git history for commit churn, author diversity, and recency."""
    try:
        from theauditor.indexer.metadata_collector import MetadataCollector

        collector = MetadataCollector(root_path=str(root_path))
        result = collector.collect_churn(days=days)

        if "error" in result:
            return {}

        git_stats = {}
        for file_data in result.get("files", []):
            path = file_data["path"]

            if file_paths and path not in file_paths:
                continue

            git_stats[path] = {
                "commits_90d": file_data.get("commits_90d", 0),
                "unique_authors": file_data.get("unique_authors", 0),
                "days_since_modified": file_data.get("days_since_modified", 999),
                "days_active_in_range": file_data.get("days_active_in_range", 0),
            }

        return git_stats

    except ImportError:
        return {}
    except OSError as e:
        logger.warning(f"Git churn collection failed: {e}")
        return {}


def parse_git_workflows(root_path: Path) -> dict[str, dict]:
    """Parse .github/workflows/*.yml for CI/CD metadata."""

    return {}


def parse_git_worktrees(root_path: Path) -> dict[str, dict]:
    """Parse git worktrees for active development branch analysis."""

    return {}
