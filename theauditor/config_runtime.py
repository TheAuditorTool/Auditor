"""Runtime configuration for TheAuditor - centralized configuration management."""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any


DEFAULTS = {
    "paths": {
        # Core files
        "manifest": "./.pf/manifest.json",
        "db": "./.pf/repo_index.db",
        "workset": "./.pf/workset.json",
        
        # Directories
        "pf_dir": "./.pf",
        "capsules_dir": "./.pf/capsules",
        "docs_dir": "./.pf/docs",
        "audit_dir": "./.pf/audit",
        "context_docs_dir": "./.pf/context/docs",
        "doc_capsules_dir": "./.pf/context/doc_capsules",
        "graphs_dir": "./.pf/graphs",
        "model_dir": "./.pf/ml",
        "claude_dir": "./.claude",
        
        # Core artifacts
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
        # File size limits
        "max_file_size": 2 * 1024 * 1024,  # 2 MiB
        
        # Chunking limits for extraction
        "max_chunks_per_file": 3,  # Maximum number of chunks per extracted file
        "max_chunk_size": 56320,  # Maximum size per chunk in bytes (55KB)
        
        # Batch processing
        "default_batch_size": 200,
        "evidence_batch_size": 100,
        
        # ML and analysis windows
        "ml_window": 50,
        "git_churn_window_days": 30,
        
        # Graph analysis
        "max_graph_depth": 3,
        "high_risk_threshold": 0.5,
        "high_risk_limit": 10,
        "graph_limit_nodes": 500,
    },
    "timeouts": {
        # Tool detection (quick checks)
        "tool_detection": 5,
        
        # Network operations
        "url_fetch": 10,
        "venv_check": 30,
        
        # Build/test operations
        "test_run": 60,
        "venv_install": 120,
        
        # Analysis operations
        "lint_timeout": 300,
        "orchestrator_timeout": 300,
        
        # FCE and long operations
        "fce_timeout": 600,
    },
    "report": {
        "max_lint_rows": 50,
        "max_ast_rows": 50,
        "max_snippet_lines": 12,
        "max_snippet_chars": 800,
    }
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
    # Start with deep copy of defaults
    import copy
    cfg = copy.deepcopy(DEFAULTS)
    
    # Try to load user config from .pf/config.json
    path = Path(root) / ".pf" / "config.json"
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
                
            # Merge each section if present
            if isinstance(user, dict):
                for section in ["paths", "limits", "timeouts", "report"]:
                    if section in user and isinstance(user[section], dict):
                        for key, value in user[section].items():
                            # Validate type matches default
                            if key in cfg[section]:
                                if isinstance(value, type(cfg[section][key])):
                                    cfg[section][key] = value
    except (json.JSONDecodeError, IOError, OSError) as e:
        print(f"[WARNING] Could not load config file from {path}: {e}")
        print("[INFO] Continuing with default configuration")
        # Continue with defaults - config file is optional
    
    # Environment variable overrides (flattened namespace)
    # Format: THEAUDITOR_SECTION_KEY (e.g., THEAUDITOR_PATHS_MANIFEST)
    for section in cfg:
        for key in cfg[section]:
            env_var = f"THEAUDITOR_{section.upper()}_{key.upper()}"
            if env_var in os.environ:
                value = os.environ[env_var]
                try:
                    # Try to cast to the same type as the default
                    default_value = cfg[section][key]
                    if isinstance(default_value, int):
                        cfg[section][key] = int(value)
                    elif isinstance(default_value, float):
                        cfg[section][key] = float(value)
                    elif isinstance(default_value, list):
                        # Parse comma-separated values for lists
                        cfg[section][key] = [v.strip() for v in value.split(",")]
                    else:
                        cfg[section][key] = value
                except (ValueError, AttributeError) as e:
                    print(f"[WARNING] Invalid value for environment variable {env_var}: '{value}' - {e}")
                    print(f"[INFO] Using default value: {cfg[section][key]}")
                    # Continue with default value - env vars are optional overrides
    
    return cfg