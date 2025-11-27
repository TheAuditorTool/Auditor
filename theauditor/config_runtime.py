"""Runtime configuration for TheAuditor - centralized configuration management."""

import json
import os
from pathlib import Path
from typing import Any

DEFAULTS = {
    "paths": {
        "manifest": "./.pf/manifest.json",
        "db": "./.pf/repo_index.db",
        "workset": "./.pf/workset.json",
        "pf_dir": "./.pf",
        "capsules_dir": "./.pf/capsules",
        "docs_dir": "./.pf/docs",
        "audit_dir": "./.pf/audit",
        "context_docs_dir": "./.pf/context/docs",
        "doc_capsules_dir": "./.pf/context/doc_capsules",
        "graphs_dir": "./.pf/graphs",
        "model_dir": "./.pf/ml",
        "claude_dir": "./.claude",
        "journal": "./.pf/journal.ndjson",
        "checkpoint": "./.pf/checkpoint.json",
        "run_report": "./.pf/run_report.json",
        "fce_json": "./.pf/raw/fce.json",
        "ast_proofs_json": "./.pf/ast_proofs.json",
        "ast_proofs_md": "./.pf/ast_proofs.md",
        "ml_suggestions": "./.pf/insights/ml_suggestions.json",
        "graphs_db": "./.pf/graphs.db",
        "graph_analysis": "./.pf/graph_analysis.json",
        "deps_json": "./.pf/deps.json",
        "findings_json": "./.pf/findings.json",
        "patterns_json": "./.pf/patterns.json",
        "xgraph_json": "./.pf/xgraph.json",
        "pattern_fce_json": "./.pf/pattern_fce.json",
        "fix_suggestions_json": "./.pf/fix_suggestions.json",
        "policy_yml": "./.pf/policy.yml",
    },
    "limits": {
        "max_file_size": 2 * 1024 * 1024,
        "max_chunks_per_file": 3,
        "max_chunk_size": 56320,
        "default_batch_size": 200,
        "evidence_batch_size": 100,
        "ml_window": 50,
        "git_churn_window_days": 30,
        "max_graph_depth": 3,
        "high_risk_threshold": 0.5,
        "high_risk_limit": 10,
        "graph_limit_nodes": 500,
    },
    "timeouts": {
        "tool_detection": 5,
        "url_fetch": 10,
        "venv_check": 30,
        "test_run": 60,
        "venv_install": 120,
        "lint_timeout": 300,
        "orchestrator_timeout": 300,
        "fce_timeout": 600,
    },
    "report": {
        "max_lint_rows": 50,
        "max_ast_rows": 50,
        "max_snippet_lines": 12,
        "max_snippet_chars": 800,
    },
}


def load_runtime_config(root: str = ".") -> dict[str, Any]:
    """
    Load runtime configuration from .pf/config.json and environment variables.

    Config priority (highest to lowest):
    1. Environment variables (THEAUDITOR_* prefixed)
    2. .pf/config.json file
    3. Built-in defaults

    Args:
        root: Root directory to look for config file

    Returns:
        Configuration dictionary with merged values
    """

    import copy

    cfg = copy.deepcopy(DEFAULTS)

    path = Path(root) / ".pf" / "config.json"
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                user = json.load(f)

            if isinstance(user, dict):
                for section in ["paths", "limits", "timeouts", "report"]:
                    if section in user and isinstance(user[section], dict):
                        for key, value in user[section].items():
                            if key in cfg[section] and isinstance(value, type(cfg[section][key])):
                                cfg[section][key] = value
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARNING] Could not load config file from {path}: {e}")
        print("[INFO] Continuing with default configuration")

    for section in cfg:
        for key in cfg[section]:
            env_var = f"THEAUDITOR_{section.upper()}_{key.upper()}"
            if env_var in os.environ:
                value = os.environ[env_var]
                try:
                    default_value = cfg[section][key]
                    if isinstance(default_value, int):
                        cfg[section][key] = int(value)
                    elif isinstance(default_value, float):
                        cfg[section][key] = float(value)
                    elif isinstance(default_value, list):
                        cfg[section][key] = [v.strip() for v in value.split(",")]
                    else:
                        cfg[section][key] = value
                except (ValueError, AttributeError) as e:
                    print(
                        f"[WARNING] Invalid value for environment variable {env_var}: '{value}' - {e}"
                    )
                    print(f"[INFO] Using default value: {cfg[section][key]}")

    return cfg
