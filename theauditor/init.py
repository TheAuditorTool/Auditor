"""Initialization module for TheAuditor - handles project setup and initialization."""

from typing import Any
from theauditor.security import sanitize_config_path, SecurityError


def initialize_project(
    offline: bool = False,
    skip_docs: bool = False,
    skip_deps: bool = False,
    progress_callback: Any = None,
) -> dict[str, Any]:
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
    from theauditor.indexer.runner import run_repository_index
    from theauditor.workset import compute_workset
    from theauditor.deps import parse_dependencies, check_latest_versions
    from theauditor.docs_fetch import fetch_docs
    from theauditor.config_runtime import load_runtime_config

    config = load_runtime_config(".")
    stats = {}

    if progress_callback:
        progress_callback("[1/4] Indexing repository...")
    try:
        manifest_path = str(
            sanitize_config_path(config["paths"]["manifest"], "paths", "manifest", ".")
        )
        db_path = str(sanitize_config_path(config["paths"]["db"], "paths", "db", "."))

        result = run_repository_index(
            root_path=".",
            manifest_path=manifest_path,
            db_path=db_path,
            print_stats=False,
            dry_run=False,
            follow_symlinks=False,
        )

        index_stats = result.get("stats", {})
        stats["index"] = {
            "files": index_stats.get("total_files", 0),
            "text_files": index_stats.get("text_files", 0),
            "success": True,
        }
        if progress_callback:
            progress_callback(f"  ✓ Indexed {stats['index']['text_files']} text files")
    except SecurityError as e:
        stats["index"] = {"success": False, "error": f"Security violation: {str(e)}"}
    except Exception as e:
        stats["index"] = {"success": False, "error": str(e)}
        if progress_callback:
            progress_callback(f"  ✗ Failed: {str(e)[:60]}")

    if progress_callback:
        progress_callback("\n[2/4] Creating workset...")
    try:
        if not stats.get("index", {}).get("success"):
            raise Exception("Skipping - indexing failed")
        if stats.get("index", {}).get("text_files", 0) == 0:
            stats["workset"] = {"success": False, "files": 0}
            if progress_callback:
                progress_callback("  ⚠ No files found")
        else:
            db_path = str(sanitize_config_path(config["paths"]["db"], "paths", "db", "."))
            manifest_path = str(
                sanitize_config_path(config["paths"]["manifest"], "paths", "manifest", ".")
            )
            output_path = str(
                sanitize_config_path(config["paths"]["workset"], "paths", "workset", ".")
            )

            result = compute_workset(
                all_files=True,
                root_path=".",
                db_path=db_path,
                manifest_path=manifest_path,
                output_path=output_path,
                max_depth=2,
                print_stats=False,
            )
            stats["workset"] = {
                "files": result.get("expanded_count", 0),
                "coverage": result.get("coverage", 0),
                "success": True,
            }
            if progress_callback:
                progress_callback(f"  ✓ Created workset with {stats['workset']['files']} files")
    except SecurityError as e:
        stats["workset"] = {"success": False, "error": f"Security violation: {str(e)}"}
    except Exception as e:
        stats["workset"] = {"success": False, "error": str(e)}
        if progress_callback:
            progress_callback(f"  ✗ Failed: {str(e)[:60]}")

    if not skip_deps and not offline:
        if progress_callback:
            progress_callback("\n[3/4] Checking dependencies...")
        try:
            deps_list = parse_dependencies(root_path=".")

            if deps_list:
                latest_info = check_latest_versions(deps_list, allow_net=True, offline=False)
                outdated = sum(1 for info in latest_info.values() if info["is_outdated"])
                stats["deps"] = {"total": len(deps_list), "outdated": outdated, "success": True}
                if progress_callback:
                    progress_callback(
                        f"  ✓ Found {len(deps_list)} dependencies ({outdated} outdated)"
                    )
            else:
                stats["deps"] = {"total": 0, "success": True}
                if progress_callback:
                    progress_callback("  ✓ No dependency files found")
        except Exception as e:
            stats["deps"] = {"success": False, "error": str(e)}
            if progress_callback:
                progress_callback(f"  ✗ Failed: {str(e)[:60]}")
    else:
        stats["deps"] = {"skipped": True}

    if not skip_docs and not offline:
        if progress_callback:
            progress_callback("\n[4/4] Fetching documentation...")
        try:
            deps_list = parse_dependencies(root_path=".")

            if deps_list:
                if len(deps_list) > 250:
                    deps_list = deps_list[:250]
                    if progress_callback:
                        progress_callback("  ℹ Limiting to first 250 packages for speed...")

                fetch_result = fetch_docs(deps_list)
                fetched = fetch_result.get("fetched", 0)
                cached = fetch_result.get("cached", 0)
                errors = fetch_result.get("errors", [])

                stats["docs"] = {
                    "fetched": fetched,
                    "cached": cached,
                    "success": True,
                    "errors": errors,
                }
                if progress_callback:
                    progress_callback(f"  ✓ Fetched {fetched} docs ({cached} from cache)")
            else:
                stats["docs"] = {"success": True, "fetched": 0}
                if progress_callback:
                    progress_callback("  ✓ No dependencies to document")
        except KeyboardInterrupt:
            stats["docs"] = {"success": False, "error": "Interrupted by user"}
            if progress_callback:
                progress_callback("\n  ⚠ Interrupted by user (Ctrl+C)")
        except Exception as e:
            stats["docs"] = {"success": False, "error": str(e)}
            if progress_callback:
                progress_callback(f"  ✗ Failed: {str(e)[:60]}")
    else:
        stats["docs"] = {"skipped": True}

    has_failures = any(
        not stats.get(step, {}).get("success", False)
        and not stats.get(step, {}).get("skipped", False)
        for step in ["index", "workset", "deps", "docs"]
    )

    next_steps = []
    if stats.get("workset", {}).get("files", 0) > 0:
        next_steps = ["aud lint --workset", "aud ast-verify --workset", "aud report"]

    return {
        "stats": stats,
        "success": not has_failures,
        "has_failures": has_failures,
        "next_steps": next_steps,
    }
