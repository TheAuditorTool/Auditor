"""Pipeline execution module for TheAuditor.

2025 Modern Architecture: AsyncIO + Memory Pipes
- No temp files for subprocess IPC
- No threading/ThreadPoolExecutor
- Parallel execution via asyncio.gather()
"""


import asyncio
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Tuple, Optional

from collections.abc import Callable
from theauditor.events import PipelineObserver

# Windows compatibility
IS_WINDOWS = platform.system() == "Windows"

# Command-specific timeout configuration (in seconds)
# UPDATED 2024-11: With tree-sitter parsing, batch DB ops, and proper indexes,
# full pipeline takes 3-5 min (normal) to 15 min (large). If >30 min, something is broken.
# Previous 10-hour timeouts were relics from week 3 regex parsing era.
COMMAND_TIMEOUTS = {
    "index": 600,               # 10 minutes - AST parsing with tree-sitter is fast
    "detect-frameworks": 180,   # 3 minutes - Quick scan of config files
    "deps": 1200,               # 20 minutes - Network I/O for 500+ deps (Track C)
    "docs": 600,                # 10 minutes - Network I/O for fetching docs (Track C)
    "workset": 180,             # 3 minutes - File system traversal
    "lint": 600,                # 10 minutes - ESLint/ruff are fast now
    "detect-patterns": 1800,    # 30 minutes - If longer, check for missing indexes
    "graph": 600,               # 10 minutes - Building dependency graphs
    "terraform": 600,           # 10 minutes - Building Terraform provisioning graphs
    "taint-analyze": 1800,      # 30 minutes - If longer, something is broken
    "taint": 1800,              # 30 minutes - Alias for taint-analyze
    "fce": 900,                 # 15 minutes - Correlation analysis (usually <5 min)
    "report": 300,              # 5 minutes - Report generation
}

# Allow environment variable override for all timeouts
DEFAULT_TIMEOUT = int(os.environ.get('THEAUDITOR_TIMEOUT_SECONDS', '900'))  # Default 15 minutes

def get_command_timeout(cmd: list[str]) -> int:
    """
    Determine appropriate timeout for a command based on its name.
    
    Args:
        cmd: Command array to execute
        
    Returns:
        Timeout in seconds
    """
    # Extract command name from the command array
    # Format: [python, -m, theauditor.cli, COMMAND_NAME, ...]
    cmd_str = " ".join(cmd)
    
    # Check for specific command patterns
    for cmd_name, timeout in COMMAND_TIMEOUTS.items():
        if cmd_name in cmd_str:
            # Check for environment variable override for specific command
            env_key = f'THEAUDITOR_TIMEOUT_{cmd_name.upper().replace("-", "_")}_SECONDS'
            return int(os.environ.get(env_key, timeout))
    
    # Default timeout if command not recognized
    return DEFAULT_TIMEOUT

# Global stop flag for interrupt handling (asyncio-compatible)
_stop_requested = False

def signal_handler(signum, frame):
    """Handle Ctrl+C by setting stop flag."""
    global _stop_requested
    print("\n[INFO] Interrupt received, stopping pipeline gracefully...", file=sys.stderr)
    _stop_requested = True

def is_stop_requested() -> bool:
    """Check if stop was requested (asyncio-safe)."""
    return _stop_requested

def reset_stop_flag():
    """Reset stop flag for new pipeline run."""
    global _stop_requested
    _stop_requested = False

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
if not IS_WINDOWS:
    signal.signal(signal.SIGTERM, signal_handler)


# =============================================================================
# MODERN ASYNCIO ENGINE (2025)
# =============================================================================

async def run_command_async(cmd: list[str], cwd: str, timeout: int = 900) -> dict:
    """Execute subprocess using asyncio memory pipes (no temp files).

    This is the modern replacement for run_subprocess_with_interrupt().
    Uses memory pipes instead of disk I/O for 10-100x faster IPC.

    Args:
        cmd: Command array to execute
        cwd: Working directory
        timeout: Maximum execution time in seconds

    Returns:
        Dict with success, returncode, stdout, stderr, elapsed
    """
    start_time = time.time()

    try:
        # Create subprocess with memory pipes (not temp files!)
        # On Windows, this uses I/O Completion Ports (very fast)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            # Wait for completion with timeout
            # communicate() reads data from memory pipes
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            return {
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": stdout_data.decode('utf-8', errors='replace'),
                "stderr": stderr_data.decode('utf-8', errors='replace'),
                "elapsed": time.time() - start_time
            }

        except asyncio.TimeoutError:
            # Modern timeout handling: kill then wait
            print(f"[TIMEOUT] Command timed out after {timeout}s: {cmd[0]}", file=sys.stderr)
            process.kill()
            await process.wait()
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "elapsed": time.time() - start_time
            }

    except Exception as e:
        # Zero Fallback: catch to report, but error is preserved
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Subprocess error: {str(e)}",
            "elapsed": time.time() - start_time
        }


async def run_chain_async(
    commands: list[tuple[str, list[str]]],
    root: str,
    chain_name: str,
    observer: Optional[PipelineObserver] = None
) -> dict:
    """Execute a chain of commands asynchronously.

    This is the modern replacement for run_command_chain().
    No status files on disk - state is in memory.

    Args:
        commands: List of (description, command_array) tuples
        root: Working directory
        chain_name: Name of this chain for logging

    Returns:
        Dict with chain results including success, output, timing
    """
    chain_start = time.time()
    chain_output = []
    chain_errors = []
    failed = False

    if observer:
        observer.on_parallel_track_start(chain_name)
    print(f"[START] {chain_name}...", file=sys.stderr)

    completed_count = 0
    total_count = len(commands)

    for description, cmd in commands:
        # Check for interrupt
        if is_stop_requested():
            failed = True
            chain_output.append(f"[INTERRUPTED] Pipeline stopped by user")
            break

        # Log progress
        print(f"[STATUS] {chain_name}: Running: {description} [{completed_count}/{total_count}]", file=sys.stderr)

        # Get appropriate timeout
        cmd_timeout = get_command_timeout(cmd)

        # Execute command asynchronously (yields control for other tracks!)
        result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)

        # Format output
        header = f"[{chain_name}] {description}"
        chain_output.append(f"\n{'='*60}\n{header}\n{'='*60}")

        # Check for special exit codes (findings commands)
        cmd_str = " ".join(str(c) for c in cmd)
        is_findings_command = (
            "taint-analyze" in cmd_str or
            ("deps" in cmd_str and "--vuln-scan" in cmd_str) or
            "cdk" in cmd_str or
            "terraform" in cmd_str or
            "workflows" in cmd_str
        )

        if is_findings_command:
            success = result['returncode'] in [0, 1, 2]
        else:
            success = result['success']

        if success:
            completed_count += 1
            chain_output.append(f"[OK] {description} ({result['elapsed']:.1f}s)")

            # Add stdout snippet
            if result['stdout']:
                lines = result['stdout'].strip().split('\n')
                if len(lines) <= 5:
                    chain_output.extend([f"  {line}" for line in lines])
                else:
                    chain_output.extend([f"  {line}" for line in lines[:5]])
                    chain_output.append(f"  ... ({len(lines) - 5} more lines)")
        else:
            failed = True
            chain_output.append(f"[FAILED] {description} (Exit: {result['returncode']})")
            if result['stderr']:
                chain_errors.append(f"Error in {description}: {result['stderr']}")
                # Show first 500 chars of error
                chain_output.append(f"[ERROR OUTPUT]:\n{result['stderr'][:500]}")
            break  # Stop chain on failure

    elapsed = time.time() - chain_start
    status = "FAILED" if failed else "COMPLETED"
    if observer:
        if not failed:
            observer.on_parallel_track_complete(chain_name, elapsed)
    print(f"[{status}] {chain_name} ({elapsed:.1f}s)", file=sys.stderr)

    return {
        "success": not failed,
        "name": chain_name,
        "output": "\n".join(chain_output),
        "errors": "\n".join(chain_errors) if chain_errors else "",
        "elapsed": elapsed
    }


async def run_full_pipeline(
    root: str = ".",
    quiet: bool = False,
    exclude_self: bool = False,
    offline: bool = False,
    use_subprocess_for_taint: bool = False,  # default to in-process for performance
    wipe_cache: bool = False,  # force cache rebuild (for corruption recovery)
    index_only: bool = False,  # Run only Stage 1 + 2 (indexing, skip heavy analysis)
    observer: Optional[PipelineObserver] = None
) -> dict[str, Any]:
    """
    Run complete audit pipeline in exact order specified in teamsop.md.

    2025 MODERN: This is now an async function using asyncio for parallel execution.

    Args:
        root: Root directory to analyze
        quiet: Whether to run in quiet mode (minimal output)
        exclude_self: Whether to exclude TheAuditor's own files from analysis
        offline: Whether to skip network operations (deps, docs)
        use_subprocess_for_taint: Whether to run taint analysis as subprocess (slower)
        wipe_cache: Whether to delete caches before run (for corruption recovery)
        index_only: Whether to run only Stage 1+2 (indexing) and skip heavy analysis
        observer: Optional PipelineObserver for receiving structured events
        
    Returns:
        Dict containing:
            - success: Whether all phases succeeded
            - failed_phases: Number of failed phases
            - total_phases: Total number of phases
            - elapsed_time: Total execution time in seconds
            - created_files: List of all created files
            - log_lines: List of all log lines
    """
    # Reset interrupt flag for new pipeline run
    reset_stop_flag()

    # CRITICAL: Archive previous run BEFORE any new artifacts are created
    # Hard dependency - archive MUST succeed or pipeline fails
    from theauditor.commands._archive import _archive
    _archive.callback(run_type="full", diff_spec=None, wipe_cache=wipe_cache)
    print("[INFO] Previous run archived successfully", file=sys.stderr)

    # CRITICAL: Initialize journal writer for ML training data
    # Journal tracks fine-grained events (file touches, findings, patches)
    # Complements pipeline.log (macro timing) and raw/*.json (ground truth)
    # Hard dependency - journal MUST initialize or pipeline fails
    from theauditor.journal import get_journal_writer
    journal = get_journal_writer(run_type="full")
    print("[INFO] Journal writer initialized for ML training", file=sys.stderr)

    # Track all created files throughout execution
    all_created_files = []
    
    # CRITICAL FIX: Open log file immediately for real-time writing
    # This ensures we don't lose logs if the pipeline crashes
    # Write directly to .pf root, not in readthis (which gets recreated by extraction)
    pf_dir = Path(root) / ".pf"
    pf_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = pf_dir / "pipeline.log"
    error_log_path = pf_dir / "error.log"  # CI/CD failure detection
    log_lines = []  # Keep for return value
    
    # Open log file in write mode with line buffering for immediate writes
    # Hard dependency - log file MUST open or pipeline fails
    log_file = open(log_file_path, 'w', encoding='utf-8', buffering=1)
    
    # CRITICAL: Create the .pf/raw/ directory for ground truth preservation
    # This directory will store immutable copies of all analysis artifacts
    # Hard dependency - raw dir MUST be created or pipeline fails
    raw_dir = Path(root) / ".pf" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Ensure readthis directory exists for fresh chunks
    # Archive has already moved old content to history
    readthis_dir = Path(root) / ".pf" / "readthis"
    readthis_dir.mkdir(parents=True, exist_ok=True)

    # Log header
    if log_file:
        log_file.write(f"TheAuditor Full Pipeline Execution Log\n")
        log_file.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"Working Directory: {Path(root).resolve()}\n")
        if index_only:
            log_file.write(f"Mode: INDEX-ONLY (Stage 1 + 2 only, skipping heavy analysis)\n")
        log_file.write("=" * 80 + "\n")
        log_file.flush()

    log_lines.append(f"TheAuditor Full Pipeline Execution Log")
    log_lines.append(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append(f"Working Directory: {Path(root).resolve()}")
    if index_only:
        log_lines.append(f"Mode: INDEX-ONLY (Stage 1 + 2 only, skipping heavy analysis)")
    log_lines.append("=" * 80)

    # Dynamically discover available commands from CLI registration (Courier principle)
    from theauditor.cli import cli
    
    # Get all registered commands, excluding internal (_) and special commands
    available_commands = sorted(cli.commands.keys())
    
    # Define execution order and arguments for known commands
    # This provides the order and arguments, but dynamically adapts to available commands
    command_order = [
        ("index", []),
        ("detect-frameworks", []),
        ("deps", ["--vuln-scan"]),  # Phase 1: Offline vulnerability scanning (Track B)
        ("deps", ["--check-latest"]),  # Phase 2: Network version checks (Track C)
        ("docs", ["fetch", "--deps", "./.pf/raw/deps.json"]),
        ("workset", ["--all"]),
        ("lint", ["--workset"]),
        ("detect-patterns", []),
        ("graph", ["build"]),
        ("graph", ["build-dfg"]),  # DFG builder - MUST run after graph build
        ("terraform", ["provision"]),  # Terraform provisioning graph - MUST run after graph build-dfg
        ("terraform", ["analyze"]),  # Terraform security analysis (database-first)
        ("cdk", ["analyze"]),  # AWS CDK security analysis (database-first)
        ("workflows", ["analyze"]),  # GitHub Actions workflow security analysis (database-first)
        ("graph", ["analyze"]),
        ("graph", ["viz", "--view", "full", "--include-analysis"]),
        ("graph", ["viz", "--view", "cycles", "--include-analysis"]),
        ("graph", ["viz", "--view", "hotspots", "--include-analysis"]),
        ("graph", ["viz", "--view", "layers", "--include-analysis"]),
        ("cfg", ["analyze", "--complexity-threshold", "10"]),
        ("metadata", ["churn"]),  # Collect git history (temporal dimension)
        ("taint-analyze", []),
        ("fce", []),
        ("session", ["analyze"]),  # Tier 5: AI agent behavior analysis
        ("report", []),
    ]
    
    # Build command list from available commands in the defined order
    commands = []
    phase_num = 0
    
    for cmd_name, extra_args in command_order:
        # Check if command exists (dynamic discovery)
        if cmd_name in available_commands or (cmd_name == "docs" and "docs" in available_commands) or (cmd_name == "graph" and "graph" in available_commands) or (cmd_name == "cfg" and "cfg" in available_commands) or (cmd_name == "terraform" and "terraform" in available_commands) or (cmd_name == "workflows" and "workflows" in available_commands) or (cmd_name == "session" and "session" in available_commands):
            phase_num += 1
            # Generate human-readable description from command name
            if cmd_name == "index":
                description = f"{phase_num}. Index repository"
                # Add --exclude-self flag if requested
                if exclude_self and cmd_name == "index":
                    extra_args = extra_args + ["--exclude-self"]
            elif cmd_name == "detect-frameworks":
                description = f"{phase_num}. Detect frameworks"
            elif cmd_name == "deps" and "--vuln-scan" in extra_args and "--check-latest" not in extra_args:
                description = f"{phase_num}. Scan dependencies for vulnerabilities (offline)"
                # Add --offline flag when pipeline is in offline mode (fixes misleading message)
                if offline and "--offline" not in extra_args:
                    extra_args = extra_args + ["--offline"]
            elif cmd_name == "deps" and "--check-latest" in extra_args:
                description = f"{phase_num}. Check dependency versions (network)"
            elif cmd_name == "docs" and "fetch" in extra_args:
                description = f"{phase_num}. Fetch documentation"
            elif cmd_name == "workset":
                description = f"{phase_num}. Create workset (all files)"
            elif cmd_name == "lint":
                description = f"{phase_num}. Run linting"
            elif cmd_name == "detect-patterns":
                description = f"{phase_num}. Detect patterns"
                # Add --exclude-self flag if requested
                if exclude_self and cmd_name == "detect-patterns":
                    extra_args = extra_args + ["--exclude-self"]
            elif cmd_name == "graph" and "build" in extra_args:
                description = f"{phase_num}. Build graph"
            elif cmd_name == "graph" and "build-dfg" in extra_args:
                description = f"{phase_num}. Build data flow graph"
            elif cmd_name == "terraform" and "provision" in extra_args:
                description = f"{phase_num}. Build Terraform provisioning graph"
            elif cmd_name == "terraform" and "analyze" in extra_args:
                description = f"{phase_num}. Analyze Terraform security"
            elif cmd_name == "cdk" and "analyze" in extra_args:
                description = f"{phase_num}. Analyze AWS CDK security"
            elif cmd_name == "workflows" and "analyze" in extra_args:
                description = f"{phase_num}. Analyze GitHub Actions workflows"
            elif cmd_name == "graph" and "analyze" in extra_args:
                description = f"{phase_num}. Analyze graph"
            elif cmd_name == "graph" and "viz" in extra_args:
                # Extract view type from arguments
                if "--view" in extra_args:
                    view_idx = extra_args.index("--view")
                    if view_idx + 1 < len(extra_args):
                        view_type = extra_args[view_idx + 1]
                        description = f"{phase_num}. Visualize graph ({view_type})"
                    else:
                        description = f"{phase_num}. Visualize graph"
                else:
                    description = f"{phase_num}. Visualize graph"
            elif cmd_name == "cfg":
                description = f"{phase_num}. Control flow analysis"
            elif cmd_name == "metadata":
                if "churn" in extra_args:
                    description = f"{phase_num}. Analyze code churn (git history)"
                else:
                    description = f"{phase_num}. Collect metadata"
            elif cmd_name == "taint-analyze":
                description = f"{phase_num}. Taint analysis"
            elif cmd_name == "fce":
                description = f"{phase_num}. Factual correlation engine"
            elif cmd_name == "session":
                description = f"{phase_num}. Analyze AI agent sessions (Tier 5)"
            elif cmd_name == "report":
                description = f"{phase_num}. Generate report"
            else:
                # Generic description for any new commands
                description = f"{phase_num}. Run {cmd_name.replace('-', ' ')}"
            
            # Build command array - use project's sandboxed aud if available
            # CRITICAL: Use project's sandbox to ensure complete isolation
            venv_dir = Path(root) / ".auditor_venv"
            if platform.system() == "Windows":
                venv_aud = venv_dir / "Scripts" / "aud.exe"
            else:
                venv_aud = venv_dir / "bin" / "aud"

            if venv_aud.exists():
                # Use sandboxed aud executable for complete isolation
                command_array = [str(venv_aud), cmd_name] + extra_args
            else:
                # No sandbox found - this is a setup error
                err1 = f"[ERROR] Sandbox not found at {venv_aud}"
                err2 = f"[ERROR] Run 'aud setup-ai --target .' to create sandbox"
                if observer:
                    observer.on_log(err1, is_error=True)
                    observer.on_log(err2, is_error=True)
                if log_file:
                    log_file.write(err1 + "\n")
                    log_file.write(err2 + "\n")
                    log_file.flush()
                log_lines.append(err1)
                log_lines.append(err2)
                # Still try with system Python as emergency fallback (will likely fail)
                command_array = [sys.executable, "-m", "theauditor.cli", cmd_name] + extra_args

            commands.append((description, command_array))
        else:
            # Command not available, log warning but continue (resilient)
            warning_msg = f"[WARNING] Command '{cmd_name}' not available, skipping"
            if observer:
                observer.on_log(warning_msg, is_error=False)
            if log_file:
                log_file.write(warning_msg + "\n")
                log_file.flush()
            log_lines.append(warning_msg)
    
    total_phases = len(commands)
    current_phase = 0
    failed_phases = 0
    phases_with_warnings = 0  # Track phases that completed but had errors in output
    pipeline_start = time.time()
    
    def collect_created_files():
        """Collect all files created during execution."""
        files = []
        
        # Core files
        if (Path(root) / "manifest.json").exists():
            files.append("manifest.json")
        if (Path(root) / "repo_index.db").exists():
            files.append("repo_index.db")
        
        # .pf directory files
        pf_dir = Path(root) / ".pf"
        if pf_dir.exists():
            for item in pf_dir.rglob("*"):
                if item.is_file():
                    files.append(item.relative_to(Path(root)).as_posix())
        
        # docs directory files (in .pf/docs)
        docs_dir = Path(root) / ".pf" / "docs"
        if docs_dir.exists():
            for item in docs_dir.rglob("*"):
                if item.is_file():
                    files.append(item.relative_to(Path(root)).as_posix())
        
        return sorted(set(files))
    
    # PARALLEL PIPELINE IMPLEMENTATION - REBALANCED 4-STAGE STRUCTURE
    # Reorganize commands into stages for optimal parallel execution
    
    # Stage categorization
    foundation_commands = []     # Stage 1: Must run first sequentially
    data_prep_commands = []      # Stage 2: Data preparation (sequential)
    track_a_commands = []        # Stage 3A: Taint analysis (isolated heavy task)
    track_b_commands = []        # Stage 3B: Static & graph analysis
    track_c_commands = []        # Stage 3C: Network I/O (deps, docs)
    final_commands = []          # Stage 4: Must run last sequentially
    
    # Categorize each command into appropriate stage/track
    for phase_name, cmd in commands:
        cmd_str = " ".join(cmd)
        
        # Stage 1: Foundation (must complete first)
        if "index" in cmd_str:
            foundation_commands.append((phase_name, cmd))
        elif "detect-frameworks" in cmd_str:
            foundation_commands.append((phase_name, cmd))
        
        # Stage 2: Data Preparation (sequential, enables parallel work)
        elif "workset" in cmd_str:
            data_prep_commands.append((phase_name, cmd))
        elif "graph build-dfg" in cmd_str:
            # DFG builder must run AFTER graph build (needs repo_index.db)
            data_prep_commands.append((phase_name, cmd))
        elif "graphql build" in cmd_str:
            # GraphQL resolver correlation must run AFTER graph build (needs repo_index.db + call graph)
            data_prep_commands.append((phase_name, cmd))
        elif "terraform provision" in cmd_str:
            # Terraform provisioning graph must run AFTER graph build-dfg
            data_prep_commands.append((phase_name, cmd))
        elif "terraform analyze" in cmd_str:
            track_b_commands.append((phase_name, cmd))
        elif "graph build" in cmd_str:
            data_prep_commands.append((phase_name, cmd))
        elif "cfg" in cmd_str:
            data_prep_commands.append((phase_name, cmd))
        elif "metadata" in cmd_str:
            data_prep_commands.append((phase_name, cmd))
        
        # Stage 3: Heavy Parallel Analysis
        # Track A: Taint analysis (isolated heavy task)
        elif "taint" in cmd_str:
            track_a_commands.append((phase_name, cmd))
        
        # Track B: Static & graph analysis
        elif "lint" in cmd_str:
            track_b_commands.append((phase_name, cmd))
        elif "detect-patterns" in cmd_str:
            track_b_commands.append((phase_name, cmd))
        elif "graph analyze" in cmd_str:
            track_b_commands.append((phase_name, cmd))
        elif "graph viz" in cmd_str:
            track_b_commands.append((phase_name, cmd))
        # NEW: Offline vulnerability scanning goes to Track B
        elif "deps" in cmd_str and "--vuln-scan" in cmd_str and "--check-latest" not in cmd_str:
            track_b_commands.append((phase_name, cmd))

        # Track C: Network I/O
        # NEW: Network version checks go to Track C
        elif "deps" in cmd_str and "--check-latest" in cmd_str:
            if not offline:  # Skip deps if offline mode
                track_c_commands.append((phase_name, cmd))
        elif "docs" in cmd_str:
            if not offline:  # Skip docs if offline mode
                track_c_commands.append((phase_name, cmd))
        
        # Stage 4: Final aggregation (must run last)
        elif "fce" in cmd_str:
            final_commands.append((phase_name, cmd))
        elif "session" in cmd_str:
            final_commands.append((phase_name, cmd))
        elif "report" in cmd_str:
            final_commands.append((phase_name, cmd))
        else:
            # Default to final commands for safety
            final_commands.append((phase_name, cmd))

    # Recalculate total_phases for index_only mode (Stage 1 + 2 only)
    if index_only:
        total_phases = len(foundation_commands) + len(data_prep_commands)
        mode_msg = f"\n[INDEX-ONLY MODE] Running {total_phases} phases (Stage 1 + 2)"
        skip_msg = f"  Skipping: Track A (taint), Track B (patterns, lint), Track C (network), Stage 4 (fce, report)"
        if observer:
            observer.on_log(mode_msg)
            observer.on_log(skip_msg)
        if log_file:
            log_file.write(mode_msg + "\n")
            log_file.write(skip_msg + "\n")
            log_file.flush()
        log_lines.append(mode_msg)
        log_lines.append(skip_msg)

    # STAGE 1: Foundation (Sequential)
    if observer:
        observer.on_stage_start("FOUNDATION - Sequential Execution", 1)
    if log_file:
        log_file.write("\n" + "="*60 + "\n")
        log_file.write("[STAGE 1] FOUNDATION - Sequential Execution\n")
        log_file.write("="*60 + "\n")
        log_file.flush()
    log_lines.append("\n" + "="*60)
    log_lines.append("[STAGE 1] FOUNDATION - Sequential Execution")
    log_lines.append("="*60)
    
    for phase_name, cmd in foundation_commands:
        current_phase += 1
        if observer:
            observer.on_phase_start(phase_name, current_phase, total_phases)
        if log_file:
            log_file.write(f"\n[Phase {current_phase}/{total_phases}] {phase_name}\n")
            log_file.flush()
        log_lines.append(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")
        start_time = time.time()

        # Record phase start in journal
        if journal:
            try:
                journal.phase_start(phase_name, " ".join(cmd), current_phase)
            except Exception as e:
                print(f"[WARN] Journal phase_start failed: {e}", file=sys.stderr)

        try:
            # CLEAN ARCHITECTURE: Index phase runs in-process via runner
            # Avoids subprocess recursion (index.py redirects to 'full')
            if "index" in " ".join(cmd):
                idx_msg = "[INDEX] Running in-process via indexer.runner"
                if observer:
                    observer.on_log(idx_msg)
                if log_file:
                    log_file.write(idx_msg + "\n")
                    log_file.flush()
                log_lines.append(idx_msg)

                from theauditor.indexer.runner import run_repository_index
                from theauditor.utils.helpers import get_self_exclusion_patterns

                # Get exclusion patterns if --exclude-self flag present
                exclude_patterns = None
                if exclude_self:
                    exclude_patterns = get_self_exclusion_patterns(True)
                    excl_msg = f"[INDEX] Excluding {len(exclude_patterns)} TheAuditor patterns"
                    if observer:
                        observer.on_log(excl_msg)
                    if log_file:
                        log_file.write(excl_msg + "\n")
                        log_file.flush()
                    log_lines.append(excl_msg)

                # Run indexer in thread pool (non-blocking for async loop)
                try:
                    idx_result = await asyncio.to_thread(
                        run_repository_index,
                        root_path=root,
                        manifest_path=".pf/manifest.json",
                        db_path=".pf/repo_index.db",
                        exclude_patterns=exclude_patterns,
                        print_stats=True
                    )

                    stats = idx_result.get('stats', {})
                    counts = idx_result.get('extract_counts', {})
                    result = {
                        'returncode': 0,
                        'stdout': f"[INDEX] Indexed {stats.get('text_files', 0)} files, {counts.get('symbols', 0)} symbols\n",
                        'stderr': ""
                    }
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    result = {
                        'returncode': 1,
                        'stdout': "",
                        'stderr': f"[INDEX ERROR] {str(e)}\n{tb}\n"
                    }
            else:
                # All other commands run via async subprocess (memory pipes)
                cmd_timeout = get_command_timeout(cmd)
                result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)

            elapsed = time.time() - start_time

            # Record phase end in journal
            if journal:
                try:
                    journal.phase_end(phase_name, success=(result['returncode'] == 0),
                                    elapsed=elapsed, exit_code=result['returncode'])
                except Exception as e:
                    print(f"[WARN] Journal phase_end failed: {e}", file=sys.stderr)

            if result['returncode'] == 0:
                if observer:
                    observer.on_phase_complete(phase_name, elapsed)
                if log_file:
                    log_file.write(f"[OK] {phase_name} completed in {elapsed:.1f}s\n")
                    log_file.flush()
                log_lines.append(f"[OK] {phase_name} completed in {elapsed:.1f}s")

                if result['stdout']:
                    lines = result['stdout'].strip().split('\n')
                    # Write FULL output to log file
                    if log_file and len(lines) > 3:
                        log_file.write("  [Full output below, truncated in terminal]\n")
                        for line in lines:
                            log_file.write(f"  {line}\n")
                        log_file.flush()

                    # Special handling for framework detection to show actual results
                    if "Detect frameworks" in phase_name and len(lines) > 3:
                        # Check if this looks like table output (has header separator)
                        has_table = any("---" in line for line in lines[:5])
                        if has_table:
                            # Show ALL lines for framework table - users want to see all detected frameworks
                            for line in lines:
                                if observer:
                                    observer.on_log(f"  {line}")
                                log_lines.append(f"  {line}")
                        else:
                            # Regular truncation for non-table output
                            for line in lines[:3]:
                                if observer:
                                    observer.on_log(f"  {line}")
                                log_lines.append(f"  {line}")
                            if len(lines) > 3:
                                truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                                if observer:
                                    observer.on_log(truncate_msg)
                                log_lines.append(truncate_msg)
                    else:
                        # Regular truncation for other commands
                        for line in lines[:3]:
                            if observer:
                                observer.on_log(f"  {line}")
                            log_lines.append(f"  {line}")
                        if len(lines) > 3:
                            truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                            if observer:
                                observer.on_log(truncate_msg)
                            log_lines.append(truncate_msg)
            else:
                failed_phases += 1
                if observer:
                    observer.on_phase_failed(phase_name, result['stderr'], result['returncode'])
                if log_file:
                    log_file.write(f"[FAILED] {phase_name} failed (exit code {result['returncode']})\n")
                    log_file.flush()
                log_lines.append(f"[FAILED] {phase_name} failed (exit code {result['returncode']})")

                # CI/CD: Write to dedicated error.log
                try:
                    with open(error_log_path, 'a', encoding='utf-8') as ef:
                        ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [FAILED] {phase_name} (Exit: {result['returncode']})\n")
                        if result['stderr']:
                            ef.write(result['stderr'] + "\n")
                        ef.write("-" * 40 + "\n")
                except Exception:
                    pass  # Ensure logging failure doesn't crash the pipeline

                if result['stderr']:
                    # Write FULL error to log file
                    if log_file:
                        log_file.write(f"  [Full error output]:\n")
                        log_file.write(f"  {result['stderr']}\n")
                        log_file.flush()
                    # Show truncated in terminal
                    error_msg = f"  Error: {result['stderr'][:200]}"
                    if len(result['stderr']) > 200:
                        error_msg += "... [see pipeline.log for full error]"
                    if observer:
                        observer.on_log(error_msg, is_error=True)
                    log_lines.append(error_msg)
                # Foundation failure stops pipeline
                critical_msg = "[CRITICAL] Foundation stage failed - stopping pipeline"
                if observer:
                    observer.on_log(critical_msg, is_error=True)
                if log_file:
                    log_file.write(critical_msg + "\n")
                    log_file.flush()
                log_lines.append(critical_msg)
                break

        except Exception as e:
            failed_phases += 1
            fail_msg = f"[FAILED] {phase_name} failed: {e}"
            if observer:
                observer.on_log(fail_msg, is_error=True)
            if log_file:
                log_file.write(fail_msg + "\n")
                log_file.flush()
            log_lines.append(fail_msg)

            # CI/CD: Write to dedicated error.log
            try:
                with open(error_log_path, 'a', encoding='utf-8') as ef:
                    ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [EXCEPTION] {phase_name}: {e}\n")
                    ef.write("-" * 40 + "\n")
            except Exception:
                pass  # Ensure logging failure doesn't crash the pipeline

            break

    # STAGE 2: Data Preparation (Sequential) - Only if foundation succeeded
    if failed_phases == 0 and data_prep_commands:
        if observer:
            observer.on_stage_start("DATA PREPARATION - Sequential Execution", 2)
            observer.on_log("Preparing data structures for parallel analysis...")
        if log_file:
            log_file.write("\n" + "="*60 + "\n")
            log_file.write("[STAGE 2] DATA PREPARATION - Sequential Execution\n")
            log_file.write("="*60 + "\n")
            log_file.write("Preparing data structures for parallel analysis...\n")
            log_file.flush()
        log_lines.append("\n" + "="*60)
        log_lines.append("[STAGE 2] DATA PREPARATION - Sequential Execution")
        log_lines.append("="*60)
        log_lines.append("Preparing data structures for parallel analysis...")
        
        for phase_name, cmd in data_prep_commands:
            current_phase += 1
            if observer:
                observer.on_phase_start(phase_name, current_phase, total_phases)
            if log_file:
                log_file.write(f"\n[Phase {current_phase}/{total_phases}] {phase_name}\n")
                log_file.flush()
            log_lines.append(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")
            start_time = time.time()

            # Record phase start in journal
            if journal:
                try:
                    journal.phase_start(phase_name, " ".join(cmd), current_phase)
                except Exception as e:
                    print(f"[WARN] Journal phase_start failed: {e}", file=sys.stderr)

            try:
                # Execute data preparation command via async subprocess (memory pipes)
                cmd_timeout = get_command_timeout(cmd)
                result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)

                elapsed = time.time() - start_time

                # Record phase end in journal
                if journal:
                    try:
                        journal.phase_end(phase_name, success=(result['returncode'] == 0),
                                        elapsed=elapsed, exit_code=result['returncode'])
                    except Exception as e:
                        print(f"[WARN] Journal phase_end failed: {e}", file=sys.stderr)

                if result['returncode'] == 0:
                    if observer:
                        observer.on_phase_complete(phase_name, elapsed)
                    if log_file:
                        log_file.write(f"[OK] {phase_name} completed in {elapsed:.1f}s\n")
                        log_file.flush()
                    log_lines.append(f"[OK] {phase_name} completed in {elapsed:.1f}s")

                    if result['stdout']:
                        lines = result['stdout'].strip().split('\n')
                        # Write FULL output to log file
                        if log_file and len(lines) > 3:
                            log_file.write("  [Full output below, truncated in terminal]\n")
                            for line in lines:
                                log_file.write(f"  {line}\n")
                            log_file.flush()

                        # Show first few lines in terminal
                        for line in lines[:3]:
                            if observer:
                                observer.on_log(f"  {line}")
                            log_lines.append(f"  {line}")
                        if len(lines) > 3:
                            truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                            if observer:
                                observer.on_log(truncate_msg)
                            log_lines.append(truncate_msg)
                else:
                    failed_phases += 1
                    if observer:
                        observer.on_phase_failed(phase_name, result['stderr'], result['returncode'])
                    if log_file:
                        log_file.write(f"[FAILED] {phase_name} failed (exit code {result['returncode']})\n")
                        log_file.flush()
                    log_lines.append(f"[FAILED] {phase_name} failed (exit code {result['returncode']})")

                    if result['stderr']:
                        # Write FULL error to log file
                        if log_file:
                            log_file.write(f"  [Full error output]:\n")
                            log_file.write(f"  {result['stderr']}\n")
                            log_file.flush()
                        # Show truncated in terminal
                        error_msg = f"  Error: {result['stderr'][:200]}"
                        if len(result['stderr']) > 200:
                            error_msg += "... [see pipeline.log for full error]"
                        if observer:
                            observer.on_log(error_msg, is_error=True)
                        log_lines.append(error_msg)
                    # Data prep failure stops pipeline
                    critical_msg = "[CRITICAL] Data preparation stage failed - stopping pipeline"
                    if observer:
                        observer.on_log(critical_msg, is_error=True)
                    if log_file:
                        log_file.write(critical_msg + "\n")
                        log_file.flush()
                    log_lines.append(critical_msg)
                    break

            except Exception as e:
                failed_phases += 1
                fail_msg = f"[FAILED] {phase_name} failed: {e}"
                if observer:
                    observer.on_log(fail_msg, is_error=True)
                if log_file:
                    log_file.write(fail_msg + "\n")
                    log_file.flush()
                log_lines.append(fail_msg)

                # CI/CD: Write to dedicated error.log
                try:
                    with open(error_log_path, 'a', encoding='utf-8') as ef:
                        ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [EXCEPTION] {phase_name}: {e}\n")
                        ef.write("-" * 40 + "\n")
                except Exception:
                    pass  # Ensure logging failure doesn't crash the pipeline

                break
    
    # Only proceed to parallel stage if foundation and data prep succeeded (skip in index_only mode)
    if failed_phases == 0 and not index_only and (track_a_commands or track_b_commands or track_c_commands):
        # STAGE 3: Heavy Parallel Analysis (Rebalanced)
        if observer:
            observer.on_stage_start("HEAVY PARALLEL ANALYSIS - Optimized Execution", 3)
            observer.on_log("Launching rebalanced parallel tracks:")
            if track_a_commands:
                observer.on_log("  Track A: Taint Analysis (isolated heavy task)")
            if track_b_commands:
                observer.on_log("  Track B: Static Analysis & Offline Security (lint, patterns, graph, vuln-scan)")
            if track_c_commands and not offline:
                observer.on_log("  Track C: Network I/O (version checks, docs)")
            elif offline:
                observer.on_log("  [OFFLINE MODE] Track C skipped")
        if log_file:
            log_file.write("\n" + "="*60 + "\n")
            log_file.write("[STAGE 3] HEAVY PARALLEL ANALYSIS - Optimized Execution\n")
            log_file.write("="*60 + "\n")
            log_file.write("Launching rebalanced parallel tracks:\n")
            if track_a_commands:
                log_file.write("  Track A: Taint Analysis (isolated heavy task)\n")
            if track_b_commands:
                log_file.write("  Track B: Static Analysis & Offline Security (lint, patterns, graph, vuln-scan)\n")
            if track_c_commands and not offline:
                log_file.write("  Track C: Network I/O (version checks, docs)\n")
            elif offline:
                log_file.write("  [OFFLINE MODE] Track C skipped\n")
            log_file.flush()
        log_lines.append("\n" + "="*60)
        log_lines.append("[STAGE 3] HEAVY PARALLEL ANALYSIS - Optimized Execution")
        log_lines.append("="*60)
        log_lines.append("Launching rebalanced parallel tracks:")
        if track_a_commands:
            log_lines.append("  Track A: Taint Analysis (isolated heavy task)")
        if track_b_commands:
            log_lines.append("  Track B: Static Analysis & Offline Security (lint, patterns, graph, vuln-scan)")
        if track_c_commands and not offline:
            log_lines.append("  Track C: Network I/O (version checks, docs)")
        elif offline:
            log_lines.append("  [OFFLINE MODE] Track C skipped")
        
        # Execute parallel tracks using asyncio (2025 Modern)
        parallel_results = []
        tasks = []

        # Track A: Taint Analysis
        if track_a_commands:
            if not use_subprocess_for_taint:
                # Direct taint execution - run synchronous code in thread pool
                def run_taint_sync():
                    """Run taint analysis synchronously (will be wrapped in thread)."""
                    from theauditor.taint import trace_taint, save_taint_analysis, TaintRegistry
                    from theauditor.utils.memory import get_recommended_memory_limit
                    from theauditor.rules.orchestrator import RulesOrchestrator

                    print(f"[STATUS] Track A (Taint Analysis): Running: Taint analysis [0/1]", file=sys.stderr)
                    start_time = time.time()

                    memory_limit = get_recommended_memory_limit()
                    db_path = Path(root) / ".pf" / "repo_index.db"

                    # Initialize infrastructure
                    print(f"[TAINT] Initializing security analysis infrastructure...", file=sys.stderr)
                    registry = TaintRegistry()
                    orchestrator = RulesOrchestrator(project_path=Path(root), db_path=db_path)
                    orchestrator.collect_rule_patterns(registry)

                    all_findings = []

                    # Run standalone rules
                    print(f"[TAINT] Running infrastructure and configuration analysis...", file=sys.stderr)
                    infra_findings = orchestrator.run_standalone_rules()
                    all_findings.extend(infra_findings)
                    print(f"[TAINT]   Found {len(infra_findings)} infrastructure issues", file=sys.stderr)

                    # Run discovery rules
                    print(f"[TAINT] Discovering framework-specific patterns...", file=sys.stderr)
                    discovery_findings = orchestrator.run_discovery_rules(registry)
                    all_findings.extend(discovery_findings)

                    stats = registry.get_stats()
                    print(f"[TAINT]   Registry now has {stats['total_sinks']} sinks, {stats['total_sources']} sources", file=sys.stderr)

                    # Run taint analysis
                    print(f"[TAINT] Performing data-flow taint analysis...", file=sys.stderr)
                    graph_db_path = Path(root) / ".pf" / "graphs.db"
                    result = trace_taint(
                        db_path=str(db_path),
                        max_depth=10,
                        registry=registry,
                        use_memory_cache=True,
                        memory_limit_mb=memory_limit,
                        graph_db_path=str(graph_db_path),
                        mode="complete"
                    )

                    taint_paths = result.get("taint_paths", result.get("paths", []))

                    if result.get("mode") == "complete":
                        print(f"[TAINT] COMPLETE MODE RESULTS:", file=sys.stderr)
                        print(f"[TAINT]   IFDS (backward): {len(taint_paths)} vulnerable paths", file=sys.stderr)
                        print(f"[TAINT]   FlowResolver (forward): {result.get('total_flows_resolved', 0)} total flows", file=sys.stderr)
                    else:
                        print(f"[TAINT]   Found {len(taint_paths)} taint flow vulnerabilities", file=sys.stderr)

                    # Run advanced rules
                    print(f"[TAINT] Running advanced security analysis...", file=sys.stderr)

                    def taint_checker(var_name, line_num=None):
                        for path in taint_paths:
                            if path.get("source", {}).get("name") == var_name:
                                return True
                            if path.get("sink", {}).get("name") == var_name:
                                return True
                            for step in path.get("path", []):
                                if isinstance(step, dict) and step.get("name") == var_name:
                                    return True
                        return False

                    advanced_findings = orchestrator.run_taint_dependent_rules(taint_checker)
                    all_findings.extend(advanced_findings)
                    print(f"[TAINT]   Found {len(advanced_findings)} advanced security issues", file=sys.stderr)

                    print(f"[TAINT] Total vulnerabilities found: {len(all_findings) + len(taint_paths)}", file=sys.stderr)

                    result["infrastructure_issues"] = infra_findings
                    result["discovery_findings"] = discovery_findings
                    result["advanced_findings"] = advanced_findings
                    result["all_rule_findings"] = all_findings
                    result["total_vulnerabilities"] = len(taint_paths) + len(all_findings)

                    # Save results
                    output_path = Path(root) / ".pf" / "raw" / "taint_analysis.json"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    save_taint_analysis(result, str(output_path))

                    # Write to database
                    if db_path.exists():
                        from theauditor.indexer.database import DatabaseManager
                        db_manager = DatabaseManager(str(db_path))
                        findings_dicts = []

                        for taint_path in result.get('taint_paths', []):
                            sink = taint_path.get('sink', {})
                            source = taint_path.get('source', {})
                            vuln_type = taint_path.get('vulnerability_type', 'Unknown')
                            message = f"{vuln_type}: {source.get('name', 'unknown')} -> {sink.get('name', 'unknown')}"

                            findings_dicts.append({
                                'file': sink.get('file', ''),
                                'line': int(sink.get('line', 0)),
                                'column': sink.get('column'),
                                'rule': f"taint-{sink.get('category', 'unknown')}",
                                'tool': 'taint',
                                'message': message,
                                'severity': 'high',
                                'category': 'injection',
                                'code_snippet': None,
                                'additional_info': taint_path
                            })

                        for finding in all_findings:
                            findings_dicts.append({
                                'file': finding.get('file', ''),
                                'line': int(finding.get('line', 0)),
                                'rule': finding.get('rule', 'unknown'),
                                'tool': 'taint',
                                'message': finding.get('message', ''),
                                'severity': finding.get('severity', 'medium'),
                                'category': finding.get('category', 'security')
                            })

                        if findings_dicts:
                            db_manager.write_findings_batch(findings_dicts, tool_name='taint')
                            db_manager.close()
                            print(f"[DB] Wrote {len(findings_dicts)} taint findings to database", file=sys.stderr)

                    elapsed = time.time() - start_time
                    db_findings_count = len(result.get('taint_paths', [])) + len(all_findings)

                    output_lines = [
                        f"\n{'='*60}",
                        f"[Track A (Taint Analysis)] Taint analysis",
                        '='*60,
                        f"[OK] Taint analysis completed in {elapsed:.1f}s",
                        f"  Infrastructure issues: {len(infra_findings)}",
                        f"  Framework patterns: {len(discovery_findings)}",
                        f"  Taint sources: {result.get('sources_found', 0)}",
                        f"  Security sinks: {result.get('sinks_found', 0)}",
                        f"  Taint paths (IFDS): {len(taint_paths)}",
                        f"  Advanced security issues: {len(advanced_findings)}",
                        f"  Total vulnerabilities: {len(all_findings) + len(taint_paths)}",
                        f"  Results saved to .pf/raw/taint_analysis.json",
                        f"  Wrote {db_findings_count} findings to database for FCE"
                    ]

                    print(f"[STATUS] Track A (Taint Analysis): Completed: Taint analysis [1/1]", file=sys.stderr)

                    return {
                        "success": True,
                        "output": "\n".join(output_lines),
                        "errors": "",
                        "elapsed": elapsed,
                        "name": "Track A (Taint Analysis)"
                    }

                # Wrap sync function for asyncio
                async def run_taint_async():
                    try:
                        return await asyncio.to_thread(run_taint_sync)
                    except Exception as e:
                        error_msg = f"Direct taint analysis failed: {str(e)}"
                        print(f"[ERROR] {error_msg}", file=sys.stderr)
                        return {
                            "success": False,
                            "output": "[FAILED] Taint analysis failed",
                            "errors": error_msg,
                            "elapsed": 0,
                            "name": "Track A (Taint Analysis)"
                        }

                tasks.append(run_taint_async())
                current_phase += len(track_a_commands)
            else:
                # Subprocess execution via async chain
                tasks.append(run_chain_async(track_a_commands, root, "Track A (Taint Analysis)", observer))
                current_phase += len(track_a_commands)

        # Track B: Static Analysis
        if track_b_commands:
            tasks.append(run_chain_async(track_b_commands, root, "Track B (Static & Graph)", observer))
            current_phase += len(track_b_commands)

        # Track C: Network I/O
        if track_c_commands:
            tasks.append(run_chain_async(track_c_commands, root, "Track C (Network I/O)", observer))
            current_phase += len(track_c_commands)

        # SYNC POINT: Run all tracks in parallel
        sync_msg = "\n[SYNC] Launching parallel tracks with asyncio.gather()..."
        if observer:
            observer.on_log(sync_msg)
        if log_file:
            log_file.write(sync_msg + "\n")
            log_file.flush()
        log_lines.append(sync_msg)

        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in parallel_results:
            if isinstance(result, Exception):
                err_msg = f"[ERROR] Track failed with exception: {result}"
                if observer:
                    observer.on_log(err_msg, is_error=True)
                if log_file:
                    log_file.write(err_msg + "\n")
                    log_file.flush()
                log_lines.append(err_msg)
                failed_phases += 1

                # CI/CD: Write to dedicated error.log
                try:
                    with open(error_log_path, 'a', encoding='utf-8') as ef:
                        ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] Track exception: {result}\n")
                        ef.write("-" * 40 + "\n")
                except Exception:
                    pass  # Ensure logging failure doesn't crash the pipeline
            elif result["success"]:
                ok_msg = f"[OK] {result['name']} completed in {result['elapsed']:.1f}s"
                if observer:
                    observer.on_parallel_track_complete(result['name'], result['elapsed'])
                if log_file:
                    log_file.write(ok_msg + "\n")
                    log_file.flush()
                log_lines.append(ok_msg)
            else:
                fail_msg = f"[FAILED] {result['name']} failed"
                if observer:
                    observer.on_log(fail_msg, is_error=True)
                if log_file:
                    log_file.write(fail_msg + "\n")
                    log_file.flush()
                log_lines.append(fail_msg)
                failed_phases += 1

                # CI/CD: Write to dedicated error.log
                try:
                    with open(error_log_path, 'a', encoding='utf-8') as ef:
                        ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [FAILED] {result['name']}\n")
                        if result.get('errors'):
                            ef.write(result['errors'] + "\n")
                        ef.write("-" * 40 + "\n")
                except Exception:
                    pass  # Ensure logging failure doesn't crash the pipeline

        # Print outputs from parallel tracks sequentially for clean logging
        if observer:
            observer.on_log("\n" + "="*60)
            observer.on_log("[STAGE 3 RESULTS] Parallel Track Outputs")
            observer.on_log("="*60)
        if log_file:
            log_file.write("\n" + "="*60 + "\n")
            log_file.write("[STAGE 3 RESULTS] Parallel Track Outputs\n")
            log_file.write("="*60 + "\n")
            log_file.flush()
        log_lines.append("\n" + "="*60)
        log_lines.append("[STAGE 3 RESULTS] Parallel Track Outputs")
        log_lines.append("="*60)

        for result in parallel_results:
            if isinstance(result, Exception):
                exc_msg = f"[EXCEPTION] {result}"
                if observer:
                    observer.on_log(exc_msg)
                if log_file:
                    log_file.write(exc_msg + "\n")
                    log_file.flush()
                log_lines.append(exc_msg)
            else:
                output = result.get("output", "")
                if observer:
                    observer.on_log(output)
                if log_file:
                    log_file.write(output + "\n")
                    log_file.flush()
                log_lines.append(output)

                if result.get("errors"):
                    err_hdr = "[ERRORS]:"
                    if observer:
                        observer.on_log(err_hdr)
                        observer.on_log(result["errors"])
                    if log_file:
                        log_file.write(err_hdr + "\n")
                        log_file.write(result["errors"] + "\n")
                        log_file.flush()
                    log_lines.append(err_hdr)
                    log_lines.append(result["errors"])
    
    # STAGE 4: Final Aggregation (Sequential) - skip in index_only mode
    if failed_phases == 0 and not index_only and final_commands:
        if observer:
            observer.on_stage_start("FINAL AGGREGATION - AsyncIO Sequential Execution", 4)
        if log_file:
            log_file.write("\n" + "="*60 + "\n")
            log_file.write("[STAGE 4] FINAL AGGREGATION - AsyncIO Sequential Execution\n")
            log_file.write("="*60 + "\n")
            log_file.flush()
        log_lines.append("\n" + "="*60)
        log_lines.append("[STAGE 4] FINAL AGGREGATION - AsyncIO Sequential Execution")
        log_lines.append("="*60)

        for phase_name, cmd in final_commands:
            current_phase += 1
            if observer:
                observer.on_phase_start(phase_name, current_phase, total_phases)
            if log_file:
                log_file.write(f"\n[Phase {current_phase}/{total_phases}] {phase_name}\n")
                log_file.flush()
            log_lines.append(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")

            # Record phase start in journal
            if journal:
                try:
                    journal.phase_start(phase_name, " ".join(cmd), current_phase)
                except Exception as e:
                    print(f"[WARN] Journal phase_start failed: {e}", file=sys.stderr)

            # Get timeout and run command async
            cmd_timeout = get_command_timeout(cmd)
            result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)

            # Check if FCE - write output to dedicated log file
            is_fce = "factual correlation" in phase_name.lower() or "fce" in " ".join(cmd)
            if is_fce:
                fce_log_path = Path(root) / ".pf" / "fce.log"
                fce_info_msg = f"[INFO] Writing FCE output to: {fce_log_path}"
                if observer:
                    observer.on_log(fce_info_msg)
                if log_file:
                    log_file.write(fce_info_msg + "\n")
                    log_file.flush()
                log_lines.append(fce_info_msg)

                with open(fce_log_path, 'w', encoding='utf-8') as fce_log:
                    fce_log.write(f"FCE Execution Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    fce_log.write("="*80 + "\n")
                    fce_log.write(result['stdout'])
                    if result['stderr']:
                        fce_log.write("\n--- STDERR ---\n")
                        fce_log.write(result['stderr'])
                # Replace stdout for main log
                result = dict(result)  # Make mutable copy
                result['stdout'] = "[FCE output written to .pf/fce.log]"

            # Handle special exit codes for findings commands
            cmd_str = " ".join(str(c) for c in cmd)
            is_findings_command = (
                "taint-analyze" in cmd_str or
                ("deps" in cmd_str and "--vuln-scan" in cmd_str) or
                "cdk" in cmd_str or
                "terraform" in cmd_str or
                "workflows" in cmd_str
            )

            if is_findings_command:
                success = result['returncode'] in [0, 1, 2]
            else:
                success = result['returncode'] == 0

            elapsed = result['elapsed']

            # Record phase end in journal
            if journal:
                try:
                    journal.phase_end(phase_name, success=success,
                                    elapsed=elapsed, exit_code=result['returncode'])
                except Exception as e:
                    print(f"[WARN] Journal phase_end failed: {e}", file=sys.stderr)

            if success:
                if result['returncode'] == 2 and is_findings_command:
                    ok_msg = f"[OK] {phase_name} completed in {elapsed:.1f}s - CRITICAL findings"
                elif result['returncode'] == 1 and is_findings_command:
                    ok_msg = f"[OK] {phase_name} completed in {elapsed:.1f}s - HIGH findings"
                else:
                    ok_msg = f"[OK] {phase_name} completed in {elapsed:.1f}s"

                if observer:
                    observer.on_phase_complete(phase_name, elapsed)
                if log_file:
                    log_file.write(ok_msg + "\n")
                    log_file.flush()
                log_lines.append(ok_msg)

                if result['stdout']:
                    lines = result['stdout'].strip().split('\n')
                    # Write FULL output to log file
                    if log_file and len(lines) > 3:
                        log_file.write("  [Full output below, truncated in terminal]\n")
                        for line in lines:
                            log_file.write(f"  {line}\n")
                        log_file.flush()

                    # Special handling for framework detection
                    if "Detect frameworks" in phase_name and len(lines) > 3:
                        has_table = any("---" in line for line in lines[:5])
                        if has_table:
                            for line in lines:
                                if observer:
                                    observer.on_log(f"  {line}")
                                log_lines.append(f"  {line}")
                        else:
                            for line in lines[:3]:
                                if observer:
                                    observer.on_log(f"  {line}")
                                log_lines.append(f"  {line}")
                            if len(lines) > 3:
                                truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                                if observer:
                                    observer.on_log(truncate_msg)
                                log_lines.append(truncate_msg)
                    else:
                        for line in lines[:3]:
                            if observer:
                                observer.on_log(f"  {line}")
                            log_lines.append(f"  {line}")
                        if len(lines) > 3:
                            truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                            if observer:
                                observer.on_log(truncate_msg)
                            log_lines.append(truncate_msg)
            else:
                failed_phases += 1
                if observer:
                    observer.on_phase_failed(phase_name, result['stderr'], result['returncode'])
                if log_file:
                    log_file.write(f"[FAILED] {phase_name} failed (exit code {result['returncode']})\n")
                    log_file.flush()
                log_lines.append(f"[FAILED] {phase_name} failed (exit code {result['returncode']})")

                # CI/CD: Write to dedicated error.log
                try:
                    with open(error_log_path, 'a', encoding='utf-8') as ef:
                        ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [FAILED] {phase_name} (Exit: {result['returncode']})\n")
                        if result['stderr']:
                            ef.write(result['stderr'] + "\n")
                        ef.write("-" * 40 + "\n")
                except Exception:
                    pass  # Ensure logging failure doesn't crash the pipeline

                if result['stderr']:
                    # Write FULL error to log file
                    if log_file:
                        log_file.write(f"  [Full error output]:\n")
                        log_file.write(f"  {result['stderr']}\n")
                        log_file.flush()
                    # Show truncated in terminal
                    error_msg = f"  Error: {result['stderr'][:200]}"
                    if len(result['stderr']) > 200:
                        error_msg += "... [see pipeline.log for full error]"
                    if observer:
                        observer.on_log(error_msg, is_error=True)
                    log_lines.append(error_msg)
    
    # After all commands complete, collect all created files
    pipeline_elapsed = time.time() - pipeline_start
    all_created_files = collect_created_files()
    
    # Create allfiles.md in .pf root (not in readthis which gets deleted/recreated)
    pf_dir = Path(root) / ".pf"
    allfiles_path = pf_dir / "allfiles.md"
    with open(allfiles_path, 'w', encoding='utf-8') as f:
        f.write("# All Files Created by `aud full` Command\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total files: {len(all_created_files)}\n\n")
        
        # Group files by directory
        files_by_dir = {}
        for file_path in all_created_files:
            dir_name = str(Path(file_path).parent)
            if dir_name not in files_by_dir:
                files_by_dir[dir_name] = []
            files_by_dir[dir_name].append(file_path)
        
        # Write files grouped by directory
        for dir_name in sorted(files_by_dir.keys()):
            f.write(f"\n## {dir_name}/\n\n")
            for file_path in sorted(files_by_dir[dir_name]):
                file_size = 0
                if Path(file_path).exists():
                    file_size = Path(file_path).stat().st_size
                f.write(f"- `{Path(file_path).name}` ({file_size:,} bytes)\n")
        
        f.write(f"\n---\n")
        f.write(f"Total execution time: {pipeline_elapsed:.1f} seconds ({pipeline_elapsed/60:.1f} minutes)\n")
        f.write(f"Commands executed: {total_phases}\n")
        f.write(f"Failed commands: {failed_phases}\n")
    
    # Display final summary
    def write_summary(msg):
        if observer:
            observer.on_log(msg)
        if log_file:
            log_file.write(msg + "\n")
            log_file.flush()
        log_lines.append(msg)

    write_summary("\n" + "="*60)
    if index_only:
        if failed_phases == 0:
            write_summary(f"[OK] INDEX COMPLETE - All {total_phases} phases successful")
            write_summary(f"[INFO] Database ready: .pf/repo_index.db + .pf/graphs.db")
            write_summary(f"[INFO] Run 'aud full' for complete analysis (taint, patterns, fce)")
        else:
            write_summary(f"[WARN] INDEX INCOMPLETE - {failed_phases} phases failed")
    elif failed_phases == 0 and phases_with_warnings == 0:
        write_summary(f"[OK] AUDIT COMPLETE - All {total_phases} phases successful")
    elif phases_with_warnings > 0 and failed_phases == 0:
        write_summary(f"[WARNING] AUDIT COMPLETE - {phases_with_warnings} phases completed with errors")
    else:
        write_summary(f"[WARN] AUDIT COMPLETE - {failed_phases} phases failed, {phases_with_warnings} phases with errors")
    write_summary(f"[TIME] Total time: {pipeline_elapsed:.1f}s ({pipeline_elapsed/60:.1f} minutes)")

    # Display all created files summary
    write_summary("\n" + "="*60)
    write_summary("[FILES] ALL CREATED FILES")
    write_summary("="*60)
    
    # Count files by category
    pf_files = [f for f in all_created_files if f.startswith(".pf/")]
    readthis_files = [f for f in all_created_files if f.startswith(".pf/readthis/")]
    docs_files = [f for f in all_created_files if f.startswith(".pf/docs/")]
    root_files = [f for f in all_created_files if "/" not in f]
    
    write_summary(f"\n[STATS] Summary:")
    write_summary(f"  Total files created: {len(all_created_files)}")
    write_summary(f"  .pf/ files: {len(pf_files)}")
    write_summary(f"  .pf/readthis/ files: {len(readthis_files)}")
    if docs_files:
        write_summary(f"  .pf/docs/ files: {len(docs_files)}")
    write_summary(f"  Root files: {len(root_files)}")

    write_summary(f"\n[SAVED] Complete file list saved to: .pf/allfiles.md")
    write_summary(f"\n[TIP] Key artifacts:")
    if index_only:
        write_summary(f"  * .pf/repo_index.db - Symbol database (queryable)")
        write_summary(f"  * .pf/graphs.db - Call/data flow graphs")
        write_summary(f"  * .pf/manifest.json - Project manifest")
        write_summary(f"  * .pf/pipeline.log - Execution log")
    else:
        write_summary(f"  * .pf/readthis/ - All AI-consumable chunks")
        write_summary(f"  * .pf/allfiles.md - Complete file list")
        write_summary(f"  * .pf/pipeline.log - Full execution log")
        write_summary(f"  * .pf/fce.log - FCE detailed output (if FCE was run)")
        write_summary(f"  * .pf/findings.json - Pattern detection results")
        write_summary(f"  * .pf/risk_scores.json - Risk analysis")

    write_summary("\n" + "="*60)
    if index_only:
        write_summary("[COMPLETE] INDEX EXECUTION COMPLETE")
    else:
        write_summary("[COMPLETE] AUDIT SUITE EXECUTION COMPLETE")
    write_summary("="*60)
    
    # Close the log file (already written throughout execution)
    if log_file:
        try:
            log_file.close()
            log_file = None
        except Exception as e:
            print(f"[CRITICAL] Failed to close log file: {e}", file=sys.stderr)
    
    # Move files from temp to readthis if needed
    temp_dir = Path(root) / ".pf" / "temp"
    readthis_final = Path(root) / ".pf" / "readthis"
    
    # Ensure readthis exists
    readthis_final.mkdir(parents=True, exist_ok=True)
    
    # Move pipeline.log if it's in temp
    temp_log = temp_dir / "pipeline.log"
    final_log = readthis_final / "pipeline.log"
    
    if temp_log.exists() and not final_log.exists():
        try:
            shutil.move(str(temp_log), str(final_log))
            log_file_path = final_log
        except Exception as e:
            print(f"[WARNING] Could not move log to final location: {e}", file=sys.stderr)
    
    # Move allfiles.md if it's in temp
    temp_allfiles = temp_dir / "allfiles.md"
    final_allfiles = readthis_final / "allfiles.md"
    
    if temp_allfiles.exists() and not final_allfiles.exists():
        try:
            shutil.move(str(temp_allfiles), str(final_allfiles))
            allfiles_path = final_allfiles
        except Exception as e:
            print(f"[WARNING] Could not move allfiles.md to final location: {e}", file=sys.stderr)
    
    print(f"\n[SAVED] Full pipeline log saved to: {log_file_path}")
    
    # Add allfiles.md and pipeline.log to the list of created files for completeness
    all_created_files.append(str(allfiles_path))
    all_created_files.append(str(log_file_path))
    
    # Note: No temp file cleanup needed - asyncio uses memory pipes
    
    # Clean up status files
    status_dir = Path(root) / ".pf" / "status"
    if status_dir.exists():
        try:
            for status_file in status_dir.glob("*.status"):
                status_file.unlink()
            # Remove directory if empty
            if not list(status_dir.iterdir()):
                status_dir.rmdir()
        except Exception as e:
            print(f"[WARNING] Could not clean status files: {e}", file=sys.stderr)
    
    # Collect findings summary from generated reports
    critical_findings = 0
    high_findings = 0
    medium_findings = 0
    low_findings = 0
    total_vulnerabilities = 0
    
    # Try to read taint analysis results
    taint_path = Path(root) / ".pf" / "raw" / "taint_analysis.json"
    if taint_path.exists():
        try:
            import json
            with open(taint_path, encoding='utf-8') as f:
                taint_data = json.load(f)
                if taint_data.get("success"):
                    summary = taint_data.get("summary", {})
                    critical_findings += summary.get("critical_count", 0)
                    high_findings += summary.get("high_count", 0)
                    medium_findings += summary.get("medium_count", 0)
                    low_findings += summary.get("low_count", 0)
                    total_vulnerabilities = taint_data.get("total_vulnerabilities", 0)
        except Exception as e:
            print(f"[WARNING] Could not read taint analysis results from {taint_path}: {e}", file=sys.stderr)
            # Non-critical - continue without taint stats
    
    # Try to read vulnerability scan results
    vuln_path = Path(root) / ".pf" / "raw" / "vulnerabilities.json"
    if vuln_path.exists():
        try:
            import json
            with open(vuln_path, encoding='utf-8') as f:
                vuln_data = json.load(f)
                if vuln_data.get("vulnerabilities"):
                    for vuln in vuln_data["vulnerabilities"]:
                        severity = vuln.get("severity", "").lower()
                        if severity == "critical":
                            critical_findings += 1
                        elif severity == "high":
                            high_findings += 1
                        elif severity == "medium":
                            medium_findings += 1
                        elif severity == "low":
                            low_findings += 1
        except Exception as e:
            print(f"[WARNING] Could not read vulnerability scan results from {vuln_path}: {e}", file=sys.stderr)
            # Non-critical - continue without vulnerability stats
    
    # Try to read pattern detection results
    # NO FALLBACK: Use canonical path only (findings.json is the standard output)
    patterns_path = Path(root) / ".pf" / "raw" / "findings.json"
    if patterns_path.exists():
        try:
            import json
            with open(patterns_path, encoding='utf-8') as f:
                patterns_data = json.load(f)
                # Aggregate findings by severity
                for finding in patterns_data.get("findings", []):
                    severity = finding.get("severity", "").lower()
                    if severity == "critical":
                        critical_findings += 1
                    elif severity == "high":
                        high_findings += 1
                    elif severity == "medium":
                        medium_findings += 1
                    elif severity == "low":
                        low_findings += 1
        except Exception as e:
            print(f"[WARNING] Could not read pattern results from {patterns_path}: {e}", file=sys.stderr)
            # Non-critical - continue without pattern stats

    # Close journal and copy to history for ML training
    if journal:
        try:
            journal.pipeline_summary(
                total_phases=total_phases,
                failed_phases=failed_phases,
                total_files=len(all_created_files),
                total_findings=total_vulnerabilities,
                elapsed=pipeline_elapsed,
                status='complete' if failed_phases == 0 else 'partial'
            )
            journal.close(copy_to_history=True)
            print("[INFO] Journal closed and copied to history for ML training", file=sys.stderr)
        except Exception as e:
            print(f"[WARNING] Journal close failed: {e}", file=sys.stderr)

    return {
        "success": failed_phases == 0 and phases_with_warnings == 0,
        "failed_phases": failed_phases,
        "phases_with_warnings": phases_with_warnings,
        "total_phases": total_phases,
        "elapsed_time": pipeline_elapsed,
        "created_files": all_created_files,
        "log_lines": log_lines,
        "findings": {
            "critical": critical_findings,
            "high": high_findings,
            "medium": medium_findings,
            "low": low_findings,
            "total_vulnerabilities": total_vulnerabilities,
        }
    }
