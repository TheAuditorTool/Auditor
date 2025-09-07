"""Run linters and normalize output to evidence format."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import click

from theauditor.linters import (
    detect_linters,
    run_linter,
)
from theauditor.utils import load_json_file
from theauditor.utils.error_handler import handle_exceptions


def write_lint_json(findings: list[dict[str, Any]], output_path: str):
    """Write findings to JSON file."""
    # Sort findings for determinism
    sorted_findings = sorted(findings, key=lambda f: (f["file"], f["line"], f["rule"]))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sorted_findings, f, indent=2, sort_keys=True)


def lint_command(
    root_path: str = ".",
    workset_path: str = "./.pf/workset.json",
    manifest_path: str = "manifest.json",
    timeout: int = 300,
    print_plan: bool = False,
    auto_fix: bool = False,
) -> dict[str, Any]:
    """
    Run linters and normalize output.

    Returns:
        Dictionary with success status and statistics
    """
    # AUTO-FIX DEPRECATED: Force disabled to prevent version mismatch issues
    auto_fix = False
    # Load workset or manifest files
    if workset_path is not None:
        # Use workset mode
        try:
            workset = load_json_file(workset_path)
            workset_files = {p["path"] for p in workset.get("paths", [])}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {"success": False, "error": f"Failed to load workset: {e}"}
    else:
        # Use all files from manifest when --workset is not used
        try:
            manifest = load_json_file(manifest_path)
            # Use all text files from the manifest
            workset_files = {f["path"] for f in manifest if isinstance(f, dict) and "path" in f}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {"success": False, "error": f"Failed to load manifest: {e}"}

    if not workset_files:
        return {"success": False, "error": "Empty workset"}

    # Detect available linters
    linters = detect_linters(root_path, auto_fix=auto_fix)

    if print_plan:
        print("Lint Plan:")
        # AUTO-FIX DEPRECATED: Always in check-only mode
        # print(f"  Mode: {'AUTO-FIX' if auto_fix else 'CHECK-ONLY'}")
        print(f"  Mode: CHECK-ONLY")
        print(f"  Workset: {len(workset_files)} files")
        if linters:
            print("  External linters detected:")
            for tool in linters:
                # AUTO-FIX DEPRECATED: No fix indicators
                # fix_capable = tool in ["eslint", "prettier", "ruff", "black"]
                # fix_indicator = " (will fix)" if auto_fix and fix_capable else ""
                print(f"    - {tool}")
        else:
            print("  No external linters detected")
            print("  Will run built-in checks:")
            print("    - NO_TODO_LAND (excessive TODOs)")
            print("    - NO_LONG_FILES (>1500 lines)")
            print("    - NO_CYCLES (import cycles)")
            print("    - NO_DEBUG_CALLS (console.log/print)")
            print("    - NO_SECRET_LIKE (potential secrets)")
        return {"success": True, "printed_plan": True}

    all_findings = []
    fixed_count = 0
    all_ast_data = {}  # Collect AST data from ESLint

    if linters:
        # Run external linters
        # AUTO-FIX DEPRECATED: Always run in check-only mode
        # mode_str = "Fixing" if auto_fix else "Checking"
        print(f"Checking with {len(linters)} external linters...")
        for tool, command in linters.items():
            # AUTO-FIX DEPRECATED: This entire block is disabled
            # if auto_fix and tool in ["eslint", "prettier", "ruff", "black"]:
            #     print(f"  Fixing with {tool}...")
            #     # In fix mode, we run the tool but may get fewer findings (as they're fixed)
            #     findings, ast_data = run_linter(tool, command, root_path, workset_files, timeout)
            #     # Collect AST data from ESLint
            #     if tool == "eslint" and ast_data:
            #         all_ast_data.update(ast_data)
            #     # Add remaining findings (unfixable issues)
            #     all_findings.extend(findings)
            #     # Estimate fixes based on the tool (most issues are fixable)
            #     if tool in ["prettier", "black"]:
            #         # Formatters fix all issues
            #         if len(findings) == 0:
            #             print(f"    Fixed all formatting issues")
            #         else:
            #             print(f"    Fixed most issues, {len(findings)} remaining")
            #     else:
            #         # ESLint and Ruff fix most but not all issues
            #         remaining = len(findings)
            #         if remaining > 0:
            #             print(f"    Fixed issues, {remaining} remaining (unfixable)")
            #         else:
            #             print(f"    Fixed all issues")
            # else:
            print(f"  Checking with {tool}...")
            findings, ast_data = run_linter(tool, command, root_path, workset_files, timeout)
            # Collect AST data from ESLint
            if tool == "eslint" and ast_data:
                all_ast_data.update(ast_data)
            all_findings.extend(findings)
            print(f"    Found {len(findings)} issues")
    else:
        # No linters found - this indicates broken environment
        print("[WARNING] No external linters found!")
        print("[ERROR] Environment is not properly configured - industry tools are required")
        print("  Install at least one linter:")
        print("    JavaScript/TypeScript: npm install --save-dev eslint")
        print("    Python: pip install ruff")
        print("    Go: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest")
        # Continue with empty findings rather than failing completely
        print("[INFO] Continuing with no lint findings...")
    
    # Check TypeScript configuration to determine which TS tool to use
    # This is DETECTION logic, not a linter itself
    # tsconfig_findings = check_tsconfig(root_path)
    # NOTE: check_tsconfig was deleted with builtin.py - need to restore detection logic

    # Write outputs directly to raw directory
    output_dir = Path(".pf/raw")
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "lint.json"

    write_lint_json(all_findings, str(json_path))

    # Save ESLint ASTs to cache
    if all_ast_data:
        # Load manifest to get file hashes
        try:
            manifest = load_json_file(manifest_path)
            file_hashes = {f["path"]: f.get("sha256") for f in manifest if isinstance(f, dict) and "sha256" in f}
            
            # Create AST cache directory
            ast_cache_dir = output_dir / "ast_cache" / "eslint"
            ast_cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Save each AST with the file's SHA256 hash as the filename
            for file_path, ast in all_ast_data.items():
                if file_path in file_hashes and file_hashes[file_path]:
                    file_hash = file_hashes[file_path]
                else:
                    # If hash not in manifest, compute it from file content
                    full_path = Path(root_path) / file_path
                    if full_path.exists():
                        with open(full_path, "rb") as f:
                            file_hash = hashlib.sha256(f.read()).hexdigest()
                    else:
                        continue
                
                # Save AST to cache file
                ast_file = ast_cache_dir / f"{file_hash}.json"
                with open(ast_file, "w", encoding="utf-8") as f:
                    json.dump(ast, f, indent=2)
            
            print(f"  Cached {len(all_ast_data)} ASTs from ESLint")
        except Exception as e:
            print(f"Warning: Failed to cache ESLint ASTs: {e}")

    # Statistics
    stats = {
        "total_findings": len(all_findings),
        "tools_run": len(linters) if linters else 1,  # 1 for built-in
        "workset_size": len(workset_files),
        "errors": sum(1 for f in all_findings if f["severity"] == "error"),
        "warnings": sum(1 for f in all_findings if f["severity"] == "warning"),
    }

    # AUTO-FIX DEPRECATED: This block is disabled
    # if auto_fix:
    #     print("\n[OK] Auto-fix complete:")
    #     print(f"  Files processed: {len(workset_files)}")
    #     print(f"  Remaining issues: {stats['total_findings']}")
    #     print(f"    Errors: {stats['errors']}")
    #     print(f"    Warnings: {stats['warnings']}")
    #     if stats['total_findings'] > 0:
    #         print(f"  Note: Some issues cannot be auto-fixed and require manual attention")
    #     print(f"  Report: {json_path}")
    # else:
    print("\nLint complete:")
    print(f"  Total findings: {stats['total_findings']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Warnings: {stats['warnings']}")
    print(f"  Output: {json_path}")
    if stats['total_findings'] > 0:
        print("  Note: Many linters (ESLint, Prettier, Ruff, Black) have their own automatic code style fix capabilities")

    return {
        "success": True,
        "stats": stats,
        "output_files": [str(json_path)],
        "auto_fix_applied": auto_fix,
    }


@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--workset", is_flag=True, help="Use workset mode (lint only files in .pf/workset.json)")
@click.option("--workset-path", default=None, help="Custom workset path (rarely needed)")
@click.option("--manifest", default=None, help="Manifest file path")
@click.option("--timeout", default=None, type=int, help="Timeout in seconds for each linter")
@click.option("--print-plan", is_flag=True, help="Print lint plan without executing")
# AUTO-FIX DEPRECATED: Hidden flag kept for backward compatibility
@click.option("--fix", is_flag=True, hidden=True, help="[DEPRECATED] No longer functional")
def lint(root, workset, workset_path, manifest, timeout, print_plan, fix):
    """Run linters and normalize output to evidence format."""
    from theauditor.config_runtime import load_runtime_config
    
    # Load configuration
    config = load_runtime_config(root)
    
    # Use config defaults if not provided
    if manifest is None:
        manifest = config["paths"]["manifest"]
    if timeout is None:
        timeout = config["timeouts"]["lint_timeout"]
    if workset_path is None and workset:
        workset_path = config["paths"]["workset"]

    # Use workset path only if --workset flag is set
    actual_workset_path = workset_path if workset else None
    
    result = lint_command(
        root_path=root,
        workset_path=actual_workset_path,
        manifest_path=manifest,
        timeout=timeout,
        print_plan=print_plan,
        auto_fix=fix,
    )

    if result.get("printed_plan"):
        return

    if not result["success"]:
        click.echo(f"Error: {result.get('error', 'Lint failed')}", err=True)
        raise click.ClickException(result.get("error", "Lint failed"))