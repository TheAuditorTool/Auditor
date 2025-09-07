"""Claude Code integration setup - Zero-optional bulletproof installer."""

import hashlib
import json
import platform
import shutil
import stat
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .venv_install import setup_project_venv, find_theauditor_root

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"


def write_file_atomic(path: Path, content: str, executable: bool = False) -> str:
    """
    Write file atomically with backup if content differs.
    
    Args:
        path: File path to write
        content: Content to write
        executable: Make file executable (Unix only)
    
    Returns:
        "created" if new file
        "updated" if file changed (creates .bak)
        "skipped" if identical content
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if path.exists():
        existing = path.read_text(encoding='utf-8')
        if existing == content:
            return "skipped"
        
        # Create backup (only once per unique content)
        bak_path = path.with_suffix(path.suffix + ".bak")
        if not bak_path.exists():
            shutil.copy2(path, bak_path)
        
        path.write_text(content, encoding='utf-8')
        status = "updated"
    else:
        path.write_text(content, encoding='utf-8')
        status = "created"
    
    # Set executable if needed
    if executable and platform.system() != "Windows":
        st = path.stat()
        path.chmod(st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    
    return status


class WrapperTemplates:
    """Cross-platform wrapper script templates."""
    
    POSIX_WRAPPER = '''#!/usr/bin/env bash
# Auto-generated wrapper for project-local aud
PROJ_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$PROJ_ROOT/.auditor_venv/bin/aud"
if [ -x "$VENV" ]; then
    exec "$VENV" "$@"
fi
# Fallback to module execution
exec "$PROJ_ROOT/.auditor_venv/bin/python" -m theauditor.cli "$@"
'''
    
    POWERSHELL_WRAPPER = r'''# Auto-generated wrapper for project-local aud
$proj = Split-Path -Path (Split-Path -Parent $MyInvocation.MyCommand.Path) -Parent
$aud = Join-Path $proj ".auditor_venv\Scripts\aud.exe"
if (Test-Path $aud) {
    & $aud @args
    exit $LASTEXITCODE
}
# Fallback to module execution
$python = Join-Path $proj ".auditor_venv\Scripts\python.exe"
& $python "-m" "theauditor.cli" @args
exit $LASTEXITCODE
'''
    
    CMD_WRAPPER = r'''@echo off
REM Auto-generated wrapper for project-local aud
set PROJ=%~dp0..\..
if exist "%PROJ%\.auditor_venv\Scripts\aud.exe" (
    "%PROJ%\.auditor_venv\Scripts\aud.exe" %*
    exit /b %ERRORLEVEL%
)
REM Fallback to module execution
"%PROJ%\.auditor_venv\Scripts\python.exe" -m theauditor.cli %*
exit /b %ERRORLEVEL%
'''


def create_wrappers(target_dir: Path) -> Dict[str, str]:
    """
    Create cross-platform wrapper scripts.
    
    Args:
        target_dir: Project root directory
        
    Returns:
        Dict mapping wrapper paths to their status
    """
    wrappers_dir = target_dir / ".claude" / "bin"
    results = {}
    
    # POSIX wrapper (bash)
    posix_wrapper = wrappers_dir / "aud"
    status = write_file_atomic(posix_wrapper, WrapperTemplates.POSIX_WRAPPER, executable=True)
    results[str(posix_wrapper)] = status
    
    # PowerShell wrapper
    ps_wrapper = wrappers_dir / "aud.ps1"
    status = write_file_atomic(ps_wrapper, WrapperTemplates.POWERSHELL_WRAPPER)
    results[str(ps_wrapper)] = status
    
    # CMD wrapper
    cmd_wrapper = wrappers_dir / "aud.cmd"
    status = write_file_atomic(cmd_wrapper, WrapperTemplates.CMD_WRAPPER)
    results[str(cmd_wrapper)] = status
    
    return results


def copy_agent_templates(source_dir: Path, target_dir: Path) -> Dict[str, str]:
    """
    Copy all .md agent template files directly to target/.claude/agents/.
    
    Args:
        source_dir: Directory containing agent template .md files
        target_dir: Project root directory
        
    Returns:
        Dict mapping agent paths to their status
    """
    agents_dir = target_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Find all .md files in source directory
    for md_file in source_dir.glob("*.md"):
        if md_file.is_file():
            # Read content
            content = md_file.read_text(encoding='utf-8')
            
            # Write to target
            target_file = agents_dir / md_file.name
            status = write_file_atomic(target_file, content)
            results[str(target_file)] = status
    
    return results


def setup_claude_complete(
    target: str,
    source: str = "agent_templates",
    sync: bool = False,
    dry_run: bool = False
) -> Dict[str, List[str]]:
    """
    Complete Claude setup: venv, wrappers, hooks, and agents.
    
    Args:
        target: Target project root (absolute or relative path)
        source: Path to TheAuditor agent templates directory
        sync: Force update (still creates .bak on first change)
        dry_run: Print plan without executing
        
    Returns:
        Dict with created, updated, and skipped file lists
    """
    # Resolve paths
    target_dir = Path(target).resolve()
    
    if not target_dir.exists():
        raise ValueError(f"Target directory does not exist: {target_dir}")
    
    # Find source docs
    if Path(source).is_absolute():
        source_dir = Path(source)
    else:
        theauditor_root = find_theauditor_root()
        source_dir = theauditor_root / source
    
    if not source_dir.exists():
        raise ValueError(f"Source agent templates directory not found: {source_dir}")
    
    print(f"\n{'='*60}")
    print(f"Claude Setup - Zero-Optional Installation")
    print(f"{'='*60}")
    print(f"Target:  {target_dir}")
    print(f"Source:  {source_dir}")
    print(f"Mode:    {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"{'='*60}\n")
    
    if dry_run:
        print("DRY RUN - Plan of operations:")
        print(f"1. Create/verify venv at {target_dir}/.auditor_venv")
        print(f"2. Install TheAuditor (editable) into venv")
        print(f"3. Create wrappers at {target_dir}/.claude/bin/")
        print(f"4. Copy agent templates from {source_dir}/*.md")
        print(f"5. Write agents to {target_dir}/.claude/agents/")
        print("\nNo files will be modified.")
        return {"created": [], "updated": [], "skipped": []}
    
    results = {
        "created": [],
        "updated": [],
        "skipped": [],
        "failed": []
    }
    
    # Step 1: Setup venv
    print("Step 1: Setting up Python virtual environment...", flush=True)
    try:
        venv_path, success = setup_project_venv(target_dir, force=sync)
        if success:
            results["created"].append(str(venv_path))
        else:
            results["failed"].append(f"venv setup at {venv_path}")
            print("ERROR: Failed to setup venv. Aborting.")
            return results
    except Exception as e:
        print(f"ERROR setting up venv: {e}")
        results["failed"].append("venv setup")
        return results
    
    # Step 2: Create wrappers
    print("\nStep 2: Creating cross-platform wrappers...", flush=True)
    wrapper_results = create_wrappers(target_dir)
    for path, status in wrapper_results.items():
        results[status].append(path)
    
    # Step 3: Copy agent templates
    print("\nStep 3: Copying agent templates...", flush=True)
    try:
        agent_results = copy_agent_templates(source_dir, target_dir)
        for path, status in agent_results.items():
            results[status].append(path)
        
        if not agent_results:
            print("WARNING: No .md files found in agent_templates directory")
    
    except Exception as e:
        print(f"ERROR copying agent templates: {e}")
        results["failed"].append("agent template copy")
    
    # Summary
    print(f"\n{'='*60}")
    print("Setup Complete - Summary:")
    print(f"{'='*60}")
    print(f"Created: {len(results['created'])} files")
    print(f"Updated: {len(results['updated'])} files")
    print(f"Skipped: {len(results['skipped'])} files (unchanged)")
    
    if results['failed']:
        print(f"FAILED:  {len(results['failed'])} operations")
        for item in results['failed']:
            print(f"  - {item}")
    
    check_mark = "[OK]" if IS_WINDOWS else "✓"
    print(f"\n{check_mark} Project configured at: {target_dir}")
    print(f"{check_mark} Wrapper available at: {target_dir}/.claude/bin/aud")
    print(f"{check_mark} Agents installed to: {target_dir}/.claude/agents/")
    print(f"{check_mark} Professional linters installed (ruff, mypy, black, ESLint, etc.)")
    
    return results