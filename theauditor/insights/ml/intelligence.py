"""Intelligent parsers for raw artifacts and structured events.

This module provides THE MISSING 90% of ML intelligence:
- Tier 1: Pipeline.log parsing (macro phase timing)
- Tier 2: Enhanced journal parsing (ALL event types, not just apply_patch)
- Tier 3: Raw/*.json parsing (ground truth findings from all tools)
- Tier 4: Git analysis (churn, authors, workflows, worktrees)

FIXES:
- Old journal parser only looked at apply_patch (10% of data)
- Raw directory completely ignored except graph_metrics.json
- Phase differentiation non-existent (all 26 phases treated the same)
- Git analysis limited to commit counts (missing authors, recency, workflow data)
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional


# ============================================================================
# TIER 1: Pipeline Log Parsing (Macro Phase Timing)
# ============================================================================

def parse_pipeline_log(log_path: Path) -> dict[str, dict]:
    """
    Extract phase-level execution data from pipeline.log.

    Returns dict mapping phase names to timing/status:
    {
        "1. Index repository": {
            "elapsed": 45.2,
            "status": "success",
            "phase_num": 1,
            "exit_code": 0
        },
        "14. Taint analysis": {
            "elapsed": 120.5,
            "status": "success",
            "phase_num": 14,
            "exit_code": 0,
            "findings": "CRITICAL"
        }
    }
    """
    if not log_path.exists():
        return {}

    phase_stats = {}

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Pattern: [Phase X/Y] Phase Name
        # Then either [OK] or [FAILED]
        phase_pattern = re.compile(r'\[Phase (\d+)/\d+\] (.+)')
        ok_pattern = re.compile(r'\[OK\] (.+?) completed in ([\d.]+)s')
        critical_pattern = re.compile(r'\[OK\] (.+?) completed in ([\d.]+)s - CRITICAL findings')
        high_pattern = re.compile(r'\[OK\] (.+?) completed in ([\d.]+)s - HIGH findings')
        failed_pattern = re.compile(r'\[FAILED\] (.+?) failed')

        lines = content.split('\n')
        current_phase = None
        current_phase_num = None

        for line in lines:
            # Match phase start
            phase_match = phase_pattern.search(line)
            if phase_match:
                current_phase_num = int(phase_match.group(1))
                current_phase = phase_match.group(2)
                continue

            # Match completion
            if current_phase:
                # Check for CRITICAL findings
                critical_match = critical_pattern.search(line)
                if critical_match:
                    phase_name = critical_match.group(1)
                    elapsed = float(critical_match.group(2))
                    phase_stats[phase_name] = {
                        "elapsed": elapsed,
                        "status": "success",
                        "phase_num": current_phase_num,
                        "exit_code": 2,
                        "findings_level": "critical"
                    }
                    current_phase = None
                    continue

                # Check for HIGH findings
                high_match = high_pattern.search(line)
                if high_match:
                    phase_name = high_match.group(1)
                    elapsed = float(high_match.group(2))
                    phase_stats[phase_name] = {
                        "elapsed": elapsed,
                        "status": "success",
                        "phase_num": current_phase_num,
                        "exit_code": 1,
                        "findings_level": "high"
                    }
                    current_phase = None
                    continue

                # Check for normal success
                ok_match = ok_pattern.search(line)
                if ok_match:
                    phase_name = ok_match.group(1)
                    elapsed = float(ok_match.group(2))
                    phase_stats[phase_name] = {
                        "elapsed": elapsed,
                        "status": "success",
                        "phase_num": current_phase_num,
                        "exit_code": 0
                    }
                    current_phase = None
                    continue

                # Check for failure
                failed_match = failed_pattern.search(line)
                if failed_match:
                    phase_name = failed_match.group(1)
                    phase_stats[phase_name] = {
                        "elapsed": 0.0,
                        "status": "failed",
                        "phase_num": current_phase_num,
                        "exit_code": -1
                    }
                    current_phase = None
                    continue

    except Exception:
        pass  # Return partial data on error

    return phase_stats


# ============================================================================
# TIER 2: Enhanced Journal Parsing (ALL Event Types)
# ============================================================================

def parse_journal_events(journal_path: Path) -> dict:
    """
    Extract ALL journal event types (not just apply_patch!).

    Returns rich dict with:
    {
        "phase_timing": {phase_name: {"elapsed": 120.5, "status": "success"}},
        "file_touches": {file_path: {"analyze": 3, "findings": 12}},
        "findings_by_file": {file_path: [{"severity": "critical", "category": "sqli"}]},
        "patches": {file_path: {"success": 2, "failed": 1}},
        "pipeline_summary": {"total_phases": 25, "failed_phases": 0, ...}
    }
    """
    if not journal_path.exists():
        return {
            "phase_timing": {},
            "file_touches": {},
            "findings_by_file": {},
            "patches": {},
            "pipeline_summary": {}
        }

    phase_timing = {}
    file_touches = defaultdict(lambda: {"touches": 0, "findings": 0})
    findings_by_file = defaultdict(list)
    patches = defaultdict(lambda: {"success": 0, "failed": 0})
    pipeline_summary = {}

    try:
        with open(journal_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    event_type = event.get("event_type")

                    # phase_start: Track phase initiation
                    if event_type == "phase_start":
                        phase = event.get("phase")
                        if phase:
                            if phase not in phase_timing:
                                phase_timing[phase] = {"start_time": event.get("timestamp")}

                    # phase_end: Track phase completion with timing
                    elif event_type == "phase_end":
                        phase = event.get("phase")
                        if phase:
                            phase_timing[phase] = {
                                "elapsed": event.get("elapsed", 0.0),
                                "status": event.get("result", "unknown"),
                                "exit_code": event.get("exit_code", 0),
                                "end_time": event.get("timestamp")
                            }

                    # file_touch: Track file analysis operations
                    elif event_type == "file_touch":
                        file_path = event.get("file")
                        if file_path:
                            file_touches[file_path]["touches"] += 1
                            file_touches[file_path]["findings"] += event.get("findings", 0)
                            if event.get("result") == "fail":
                                file_touches[file_path]["failures"] = file_touches[file_path].get("failures", 0) + 1

                    # finding: Track individual findings per file
                    elif event_type == "finding":
                        file_path = event.get("file")
                        if file_path:
                            findings_by_file[file_path].append({
                                "severity": event.get("severity"),
                                "category": event.get("category"),
                                "message": event.get("message"),
                                "line": event.get("line")
                            })

                    # apply_patch: Track patch applications
                    elif event_type == "apply_patch":
                        file_path = event.get("file")
                        if file_path:
                            if event.get("result") == "success":
                                patches[file_path]["success"] += 1
                            else:
                                patches[file_path]["failed"] += 1

                    # pipeline_summary: Overall run summary
                    elif event_type == "pipeline_summary":
                        pipeline_summary = {
                            "total_phases": event.get("total_phases", 0),
                            "failed_phases": event.get("failed_phases", 0),
                            "total_files": event.get("total_files", 0),
                            "total_findings": event.get("total_findings", 0),
                            "elapsed": event.get("elapsed", 0.0),
                            "status": event.get("status", "unknown")
                        }

                except json.JSONDecodeError:
                    continue

    except Exception:
        pass  # Return partial data

    return {
        "phase_timing": dict(phase_timing),
        "file_touches": dict(file_touches),
        "findings_by_file": dict(findings_by_file),
        "patches": dict(patches),
        "pipeline_summary": pipeline_summary
    }


# ============================================================================
# TIER 3: Raw Artifact Parsers (THE MISSING 90%)
# ============================================================================

def parse_taint_analysis(raw_path: Path) -> dict[str, dict]:
    """
    Parse raw/taint_analysis.json for detailed vulnerability data.

    Returns dict mapping file paths to vulnerability details:
    {
        "auth.py": {
            "vulnerability_paths": 3,
            "critical_count": 2,
            "high_count": 1,
            "cwe_list": ["CWE-89", "CWE-79"],
            "max_taint_path_length": 5
        }
    }
    """
    file_path = raw_path / "taint_analysis.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(lambda: {
        "vulnerability_paths": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "cwe_list": [],
        "max_taint_path_length": 0
    })

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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

            # Track taint path complexity
            path_length = len(finding.get("taint_path", []))
            if path_length > stats[file]["max_taint_path_length"]:
                stats[file]["max_taint_path_length"] = path_length

    except Exception:
        pass

    return dict(stats)


def parse_vulnerabilities(raw_path: Path) -> dict[str, dict]:
    """
    Parse raw/vulnerabilities.json for CVE data with CVSS scores.

    Returns dict mapping file paths to CVE details:
    {
        "package.json": {
            "cve_count": 5,
            "max_cvss_score": 9.8,
            "critical_cves": 2,
            "exploitable_count": 1
        }
    }
    """
    file_path = raw_path / "vulnerabilities.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(lambda: {
        "cve_count": 0,
        "max_cvss_score": 0.0,
        "critical_cves": 0,
        "high_cves": 0,
        "exploitable_count": 0
    })

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for vuln in data.get("vulnerabilities", []):
            file = vuln.get("file", vuln.get("package", ""))
            if not file:
                continue

            stats[file]["cve_count"] += 1

            cvss = vuln.get("cvss_score", 0.0)
            if cvss > stats[file]["max_cvss_score"]:
                stats[file]["max_cvss_score"] = cvss

            if cvss >= 9.0:
                stats[file]["critical_cves"] += 1
            elif cvss >= 7.0:
                stats[file]["high_cves"] += 1

            if vuln.get("exploitable", False):
                stats[file]["exploitable_count"] += 1

    except Exception:
        pass

    return dict(stats)


def parse_patterns(raw_path: Path) -> dict[str, dict]:
    """
    Parse raw/patterns.json for pattern detection findings.

    Returns dict mapping file paths to pattern counts:
    {
        "config.py": {
            "hardcoded_secrets": 3,
            "weak_crypto": 1,
            "insecure_random": 0,
            "dangerous_functions": 2
        }
    }
    """
    file_path = raw_path / "patterns.json"
    if not file_path.exists():
        # Fallback to findings.json (alternate name)
        file_path = raw_path / "findings.json"
        if not file_path.exists():
            return {}

    stats = defaultdict(lambda: {
        "hardcoded_secrets": 0,
        "weak_crypto": 0,
        "insecure_random": 0,
        "dangerous_functions": 0,
        "total_patterns": 0
    })

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for finding in data.get("findings", []):
            file = finding.get("file", "")
            if not file:
                continue

            stats[file]["total_patterns"] += 1

            category = finding.get("category", "").lower()
            if "secret" in category or "password" in category or "key" in category:
                stats[file]["hardcoded_secrets"] += 1
            elif "crypto" in category or "md5" in category or "sha1" in category:
                stats[file]["weak_crypto"] += 1
            elif "random" in category:
                stats[file]["insecure_random"] += 1
            elif "dangerous" in category or "eval" in category:
                stats[file]["dangerous_functions"] += 1

    except Exception:
        pass

    return dict(stats)


def parse_fce(raw_path: Path) -> dict[str, dict]:
    """
    Parse raw/fce.json for factual correlation analysis.

    Returns dict mapping file paths to correlation data:
    {
        "auth.py": {
            "failure_correlations": 3,
            "cross_file_dependencies": 5,
            "hotspot_score": 0.85
        }
    }
    """
    file_path = raw_path / "fce.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(lambda: {
        "failure_correlations": 0,
        "cross_file_dependencies": 0,
        "hotspot_score": 0.0
    })

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Parse failure correlations
        for correlation in data.get("correlations", []):
            file = correlation.get("file", "")
            if file:
                stats[file]["failure_correlations"] += 1

        # Parse hotspots
        for hotspot in data.get("hotspots", []):
            file = hotspot.get("file", "")
            if file:
                score = hotspot.get("score", 0.0)
                stats[file]["hotspot_score"] = max(stats[file]["hotspot_score"], score)

        # Parse cross-file dependencies
        for dep in data.get("dependencies", []):
            source = dep.get("source", "")
            if source:
                stats[source]["cross_file_dependencies"] += 1

    except Exception:
        pass

    return dict(stats)


def parse_cfg_analysis(raw_path: Path) -> dict[str, dict]:
    """
    Parse raw/cfg_analysis.json for control flow complexity per function.

    Returns dict mapping file paths to CFG metrics:
    {
        "service.py": {
            "max_cyclomatic_complexity": 18,
            "avg_cyclomatic_complexity": 6.5,
            "complex_function_count": 3
        }
    }
    """
    file_path = raw_path / "cfg_analysis.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(lambda: {
        "max_cyclomatic_complexity": 0,
        "avg_cyclomatic_complexity": 0.0,
        "complex_function_count": 0,
        "total_functions": 0
    })

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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

            if complexity > 10:  # Threshold for "complex"
                stats[file]["complex_function_count"] += 1

        # Calculate averages
        for file, complexities in file_functions.items():
            stats[file]["total_functions"] = len(complexities)
            stats[file]["avg_cyclomatic_complexity"] = sum(complexities) / len(complexities) if complexities else 0.0

    except Exception:
        pass

    return dict(stats)


def parse_frameworks(raw_path: Path) -> dict[str, dict]:
    """
    Parse raw/frameworks.json for detected frameworks and versions.

    Returns dict mapping file paths to framework info:
    {
        "app.py": {
            "frameworks": ["flask", "sqlalchemy"],
            "has_vulnerable_version": True,
            "framework_count": 2
        }
    }
    """
    file_path = raw_path / "frameworks.json"
    if not file_path.exists():
        return {}

    stats = defaultdict(lambda: {
        "frameworks": [],
        "has_vulnerable_version": False,
        "framework_count": 0
    })

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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

    except Exception:
        pass

    return dict(stats)


def parse_graph_metrics(raw_path: Path) -> dict[str, float]:
    """
    Parse raw/graph_metrics.json for centrality scores.

    Returns dict mapping file paths to centrality scores:
    {"auth.py": 0.85, "service.py": 0.62}
    """
    file_path = raw_path / "graph_metrics.json"
    if not file_path.exists():
        return {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def parse_all_raw_artifacts(raw_dir: Path) -> dict:
    """
    Parse ALL raw/*.json files and combine into unified feature dict.

    Returns dict with all parsed artifact categories:
    {
        "taint": {...},
        "vulnerabilities": {...},
        "patterns": {...},
        "fce": {...},
        "cfg": {...},
        "frameworks": {...},
        "graph_metrics": {...}
    }
    """
    if not raw_dir.exists():
        return {}

    return {
        "taint": parse_taint_analysis(raw_dir),
        "vulnerabilities": parse_vulnerabilities(raw_dir),
        "patterns": parse_patterns(raw_dir),
        "fce": parse_fce(raw_dir),
        "cfg": parse_cfg_analysis(raw_dir),
        "frameworks": parse_frameworks(raw_dir),
        "graph_metrics": parse_graph_metrics(raw_dir)
    }


# ============================================================================
# TIER 4: Git Analysis (Churn, Authors, Workflows, Worktrees)
# ============================================================================

def parse_git_churn(root_path: Path, days: int = 90, file_paths: Optional[list[str]] = None) -> dict[str, dict]:
    """
    Parse git history for commit churn, author diversity, and recency.

    Delegates to existing MetadataCollector.collect_churn() for DRY compliance.
    NOTE: Git analysis does NOT skip .venv or excluded dirs (user requirement).

    Args:
        root_path: Project root directory
        days: Number of days to analyze (default 90)
        file_paths: Optional list of files to filter (None = all files)

    Returns:
        Dict mapping file paths to git metrics:
        {
            "auth.py": {
                "commits_90d": 23,
                "unique_authors": 5,
                "days_since_modified": 2,
                "days_active_in_range": 45
            }
        }
    """
    try:
        from theauditor.indexer.metadata_collector import MetadataCollector

        collector = MetadataCollector(root_path=str(root_path))
        result = collector.collect_churn(days=days, output_path=None)

        if "error" in result:
            return {}

        # Convert list format to dict format
        git_stats = {}
        for file_data in result.get("files", []):
            path = file_data["path"]

            # Filter to file_paths if provided
            if file_paths and path not in file_paths:
                continue

            git_stats[path] = {
                "commits_90d": file_data.get("commits_90d", 0),
                "unique_authors": file_data.get("unique_authors", 0),
                "days_since_modified": file_data.get("days_since_modified", 999),
                "days_active_in_range": file_data.get("days_active_in_range", 0)
            }

        return git_stats

    except Exception:
        # Gracefully degrade if git not available
        return {}


def parse_git_workflows(root_path: Path) -> dict[str, dict]:
    """
    Parse .github/workflows/*.yml for CI/CD metadata.

    FUTURE ENHANCEMENT: Not implemented yet, but reserved for:
    - Workflow trigger frequency
    - Test success rates
    - Deployment frequency

    Returns:
        Dict mapping workflow files to metadata (currently empty)
    """
    # Stub for future expansion (user mentioned workflows)
    return {}


def parse_git_worktrees(root_path: Path) -> dict[str, dict]:
    """
    Parse git worktrees for active development branch analysis.

    FUTURE ENHANCEMENT: Not implemented yet, but reserved for:
    - Number of active worktrees
    - Branch divergence metrics
    - Parallel development detection

    Returns:
        Dict mapping worktree paths to metadata (currently empty)
    """
    # Stub for future expansion (user mentioned worktrees)
    return {}
