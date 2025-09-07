"""Initialization module for TheAuditor - handles project setup and initialization."""

from pathlib import Path
from typing import Dict, Any
from theauditor.security import sanitize_config_path, SecurityError


def initialize_project(
    offline: bool = False,
    skip_docs: bool = False,
    skip_deps: bool = False
) -> Dict[str, Any]:
    """
    Initialize TheAuditor for first-time use by running all setup steps.
    
    This function handles the sequence of operations:
    1. Index repository
    2. Create workset
    3. Check dependencies (unless skipped/offline)
    4. Fetch documentation (unless skipped/offline)
    
    Args:
        offline: Skip network operations (deps check, docs fetch)
        skip_docs: Skip documentation fetching
        skip_deps: Skip dependency checking
    
    Returns:
        Dict containing:
            - stats: Statistics for each step
            - success: Overall success status
            - has_failures: Whether any steps failed
            - next_steps: List of recommended next commands
    """
    from theauditor.indexer import build_index
    from theauditor.workset import compute_workset
    from theauditor.deps import parse_dependencies, check_latest_versions
    from theauditor.docs_fetch import fetch_docs
    from theauditor.docs_summarize import summarize_docs
    from theauditor.config_runtime import load_runtime_config
    
    # Load configuration
    config = load_runtime_config(".")
    stats = {}
    
    # 1. Index
    try:
        # Sanitize paths from config before use
        manifest_path = str(sanitize_config_path(config["paths"]["manifest"], "paths", "manifest", "."))
        db_path = str(sanitize_config_path(config["paths"]["db"], "paths", "db", "."))
        
        result = build_index(
            root_path=".",
            manifest_path=manifest_path,
            db_path=db_path,
            print_stats=False,
            dry_run=False,
            follow_symlinks=False
        )
        if result.get("error"):
            raise Exception(result["error"])
        # Extract stats from nested structure
        index_stats = result.get("stats", {})
        stats["index"] = {
            "files": index_stats.get("total_files", 0),
            "text_files": index_stats.get("text_files", 0),
            "success": True
        }
    except SecurityError as e:
        stats["index"] = {"success": False, "error": f"Security violation: {str(e)}"}
    except Exception as e:
        stats["index"] = {"success": False, "error": str(e)}
    
    # 2. Workset
    try:
        # Skip if indexing failed or found no files
        if not stats.get("index", {}).get("success"):
            raise Exception("Skipping - indexing failed")
        if stats.get("index", {}).get("text_files", 0) == 0:
            stats["workset"] = {"success": False, "files": 0}
        else:
            # Sanitize paths from config before use
            db_path = str(sanitize_config_path(config["paths"]["db"], "paths", "db", "."))
            manifest_path = str(sanitize_config_path(config["paths"]["manifest"], "paths", "manifest", "."))
            output_path = str(sanitize_config_path(config["paths"]["workset"], "paths", "workset", "."))
            
            result = compute_workset(
                all_files=True,
                root_path=".",
                db_path=db_path,
                manifest_path=manifest_path,
                output_path=output_path,
                max_depth=2,
                print_stats=False
            )
            stats["workset"] = {
                "files": result.get("expanded_count", 0),
                "coverage": result.get("coverage", 0),
                "success": True
            }
    except SecurityError as e:
        stats["workset"] = {"success": False, "error": f"Security violation: {str(e)}"}
    except Exception as e:
        stats["workset"] = {"success": False, "error": str(e)}
    
    # 3. Dependencies
    if not skip_deps and not offline:
        try:
            deps_list = parse_dependencies(root_path=".")
            
            if deps_list:
                latest_info = check_latest_versions(deps_list, allow_net=True, offline=False)
                outdated = sum(1 for info in latest_info.values() if info["is_outdated"])
                stats["deps"] = {
                    "total": len(deps_list),
                    "outdated": outdated,
                    "success": True
                }
            else:
                stats["deps"] = {"total": 0, "success": True}
        except Exception as e:
            stats["deps"] = {"success": False, "error": str(e)}
    else:
        stats["deps"] = {"skipped": True}
    
    # 4. Documentation
    if not skip_docs and not offline:
        try:
            deps_list = parse_dependencies(root_path=".")
            
            if deps_list:
                # Limit to first 50 deps for init command to avoid hanging
                if len(deps_list) > 50:
                    deps_list = deps_list[:50]
                
                # Fetch with progress indicator
                fetch_result = fetch_docs(deps_list)
                fetched = fetch_result.get('fetched', 0)
                cached = fetch_result.get('cached', 0)
                errors = fetch_result.get('errors', [])
                
                # Summarize
                summarize_result = summarize_docs()
                stats["docs"] = {
                    "fetched": fetched,
                    "cached": cached,
                    "capsules": summarize_result.get('capsules_created', 0),
                    "success": True,
                    "errors": errors
                }
            else:
                stats["docs"] = {"success": True, "fetched": 0, "capsules": 0}
        except KeyboardInterrupt:
            stats["docs"] = {"success": False, "error": "Interrupted by user"}
        except Exception as e:
            stats["docs"] = {"success": False, "error": str(e)}
    else:
        stats["docs"] = {"skipped": True}
    
    # Code capsules feature has been removed - the command was deleted
    # Doc capsules (for dependency documentation) are handled by 'aud docs summarize'
    
    # Check if initialization was successful
    has_failures = any(
        not stats.get(step, {}).get("success", False) and not stats.get(step, {}).get("skipped", False)
        for step in ["index", "workset", "deps", "docs"]
    )
    
    # Determine next steps
    next_steps = []
    if stats.get("workset", {}).get("files", 0) > 0:
        next_steps = [
            "aud lint --workset",
            "aud ast-verify --workset",
            "aud report"
        ]
    
    return {
        "stats": stats,
        "success": not has_failures,
        "has_failures": has_failures,
        "next_steps": next_steps
    }