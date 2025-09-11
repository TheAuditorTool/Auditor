"""Pipeline execution module for TheAuditor."""

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Tuple

# Import our custom temp manager to avoid WSL2/Windows issues
try:
    from theauditor.utils.temp_manager import TempManager
except ImportError:
    # Fallback if not available yet
    TempManager = None

# Windows compatibility
IS_WINDOWS = platform.system() == "Windows"

# Command-specific timeout configuration (in seconds)
# Based on empirical testing and user reports of 10-60 minute analysis times
COMMAND_TIMEOUTS = {
    "index": 600,               # 10 minutes - AST parsing can be slow on large codebases
    "detect-frameworks": 300,   # 5 minutes - Quick scan of config files
    "deps": 300,                # 5 minutes - Network I/O but usually fast
    "docs": 300,                # 5 minutes - Network I/O for fetching docs
    "workset": 300,             # 5 minutes - File system traversal
    "lint": 900,                # 15 minutes - ESLint/ruff on large codebases
    "detect-patterns": 36000,   # 10 hours - 100+ security patterns on enterprise codebases (140K+ symbols)
    "graph": 600,               # 10 minutes - Building dependency graphs
    "taint-analyze": 36000,     # 10 hours - Data flow analysis on enterprise codebases (140K+ symbols)
    "taint": 36000,             # 10 hours - Alias for taint-analyze
    "fce": 1800,                # 30 minutes - Correlation analysis
    "report": 600,              # 10 minutes - Report generation
    "summary": 300,             # 5 minutes - Quick summary generation
}

# Allow environment variable override for all timeouts
DEFAULT_TIMEOUT = int(os.environ.get('THEAUDITOR_TIMEOUT_SECONDS', '1800'))  # Default 30 minutes

def get_command_timeout(cmd: List[str]) -> int:
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

# Global stop event for interrupt handling
stop_event = threading.Event()

def signal_handler(signum, frame):
    """Handle Ctrl+C by setting stop event."""
    print("\n[INFO] Interrupt received, stopping pipeline gracefully...", file=sys.stderr)
    stop_event.set()

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
if not IS_WINDOWS:
    signal.signal(signal.SIGTERM, signal_handler)

def run_subprocess_with_interrupt(cmd, stdout_fp, stderr_fp, cwd, shell=False, timeout=300):
    """
    Run subprocess with interrupt checking every 100ms.
    
    Args:
        cmd: Command to execute
        stdout_fp: File handle for stdout
        stderr_fp: File handle for stderr
        cwd: Working directory
        shell: Whether to use shell execution
        timeout: Maximum time to wait (seconds)
    
    Returns:
        subprocess.CompletedProcess-like object with returncode, stdout, stderr
    """
    process = subprocess.Popen(
        cmd,
        stdout=stdout_fp,
        stderr=stderr_fp,
        text=True,
        cwd=cwd,
        shell=shell
    )
    
    # Poll process every 100ms to check for completion or interruption
    start_time = time.time()
    while process.poll() is None:
        if stop_event.is_set():
            # User interrupted - terminate subprocess
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise KeyboardInterrupt("Pipeline interrupted by user")
        
        # Check timeout
        if time.time() - start_time > timeout:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise subprocess.TimeoutExpired(cmd, timeout)
        
        # Sleep briefly to avoid busy-waiting
        time.sleep(0.1)
    
    # Create result object similar to subprocess.run
    class Result:
        def __init__(self, returncode):
            self.returncode = returncode
            self.stdout = None
            self.stderr = None
    
    result = Result(process.returncode)
    return result


def run_command_chain(commands: List[Tuple[str, List[str]]], root: str, chain_name: str) -> dict:
    """
    Execute a chain of commands sequentially and capture their output.
    Used for parallel execution of independent command tracks.
    
    Args:
        commands: List of (description, command_array) tuples
        root: Working directory
        chain_name: Name of this chain for logging
        
    Returns:
        Dict with chain results including success, output, and timing
    """
    chain_start = time.time()
    chain_output = []
    chain_errors = []
    failed = False
    
    # Write progress to a status file for monitoring
    status_dir = Path(root) / ".pf" / "status"
    try:
        status_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[WARNING] Could not create status dir {status_dir}: {e}", file=sys.stderr)
    status_file = status_dir / f"{chain_name.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')}.status"
    
    def write_status(message: str, completed: int = 0, total: int = 0):
        """Write current status to file for external monitoring."""
        try:
            with open(status_file, 'w', encoding='utf-8') as f:
                status_data = {
                    "track": chain_name,
                    "current": message,
                    "completed": completed,
                    "total": total,
                    "timestamp": time.time(),
                    "elapsed": time.time() - chain_start
                }
                f.write(json.dumps(status_data) + "\n")
                f.flush()  # Force write to disk
                # Debug output to stderr (visible in subprocess)
                print(f"[STATUS] {chain_name}: {message} [{completed}/{total}]", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Could not write status to {status_file}: {e}", file=sys.stderr)
    
    # Write initial status
    write_status("Starting", 0, len(commands))
    
    completed_count = 0
    for description, cmd in commands:
        # Update status before starting command
        write_status(f"Running: {description}", completed_count, len(commands))
        
        start_time = time.time()
        chain_output.append(f"\n{'='*60}")
        chain_output.append(f"[{chain_name}] {description}")
        chain_output.append('='*60)
        
        try:
            # Use temp files to capture output
            if TempManager:
                # Sanitize chain name and description for Windows paths
                safe_chain = chain_name.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
                safe_desc = description[:20].replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
                stdout_file, stderr_file = TempManager.create_temp_files_for_subprocess(
                    root, f"chain_{safe_chain}_{safe_desc}"
                )
            else:
                # Fallback to regular tempfile
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt') as out_tmp, \
                     tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt') as err_tmp:
                    stdout_file = out_tmp.name
                    stderr_file = err_tmp.name
            
            with open(stdout_file, 'w+', encoding='utf-8') as out_fp, \
                 open(stderr_file, 'w+', encoding='utf-8') as err_fp:
                
                # Determine appropriate timeout for this command
                cmd_timeout = get_command_timeout(cmd)
                
                result = run_subprocess_with_interrupt(
                    cmd,
                    stdout_fp=out_fp,
                    stderr_fp=err_fp,
                    cwd=root,
                    shell=IS_WINDOWS,  # Windows compatibility fix
                    timeout=cmd_timeout  # Adaptive timeout based on command type
                )
            
            # Read outputs
            with open(stdout_file, 'r', encoding='utf-8') as f:
                stdout = f.read()
            with open(stderr_file, 'r', encoding='utf-8') as f:
                stderr = f.read()
            
            # Clean up temp files
            try:
                os.unlink(stdout_file)
                os.unlink(stderr_file)
            except (OSError, PermissionError):
                pass  # Windows file locking
            
            elapsed = time.time() - start_time
            
            # Check for special exit codes (findings commands)
            is_findings_command = "taint-analyze" in cmd or ("deps" in cmd and "--vuln-scan" in cmd)
            if is_findings_command:
                success = result.returncode in [0, 1, 2]
            else:
                success = result.returncode == 0
            
            if success:
                completed_count += 1
                write_status(f"Completed: {description}", completed_count, len(commands))
                chain_output.append(f"[OK] {description} completed in {elapsed:.1f}s")
                if stdout:
                    lines = stdout.strip().split('\n')
                    # For parallel tracks, include all output (chains collect their own output)
                    if len(lines) <= 5:
                        for line in lines:
                            chain_output.append(f"  {line}")
                    else:
                        # Show first 5 lines and indicate more in chain output
                        for line in lines[:5]:
                            chain_output.append(f"  {line}")
                        chain_output.append(f"  ... ({len(lines) - 5} more lines)")
                        # Add full output marker for later processing
                        chain_output.append("  [Full output available in pipeline.log]")
            else:
                failed = True
                write_status(f"FAILED: {description}", completed_count, len(commands))
                chain_output.append(f"[FAILED] {description} failed (exit code {result.returncode})")
                if stderr:
                    chain_errors.append(f"Error in {description}: {stderr}")
                break  # Stop chain on failure
                
        except KeyboardInterrupt:
            # User interrupted - clean up and exit
            failed = True
            write_status(f"INTERRUPTED: {description}", completed_count, len(commands))
            chain_output.append(f"[INTERRUPTED] Pipeline stopped by user")
            raise  # Re-raise to propagate up
        except Exception as e:
            failed = True
            write_status(f"ERROR: {description}", completed_count, len(commands))
            chain_output.append(f"[FAILED] {description} failed: {e}")
            chain_errors.append(f"Exception in {description}: {str(e)}")
            break
    
    # Final status
    if not failed:
        write_status(f"Completed all {len(commands)} tasks", len(commands), len(commands))
    
    chain_elapsed = time.time() - chain_start
    return {
        "success": not failed,
        "output": "\n".join(chain_output),
        "errors": "\n".join(chain_errors) if chain_errors else "",
        "elapsed": chain_elapsed,
        "name": chain_name
    }


def run_full_pipeline(
    root: str = ".",
    quiet: bool = False,
    exclude_self: bool = False,
    offline: bool = False,
    log_callback: Callable[[str, bool], None] = None
) -> dict[str, Any]:
    """
    Run complete audit pipeline in exact order specified in teamsop.md.
    
    Args:
        root: Root directory to analyze
        quiet: Whether to run in quiet mode (minimal output)
        log_callback: Optional callback function for logging messages (message, is_error)
        
    Returns:
        Dict containing:
            - success: Whether all phases succeeded
            - failed_phases: Number of failed phases
            - total_phases: Total number of phases
            - elapsed_time: Total execution time in seconds
            - created_files: List of all created files
            - log_lines: List of all log lines
    """
    # CRITICAL: Archive previous run BEFORE any new artifacts are created
    # Import and call _archive function directly to avoid subprocess issues
    try:
        from theauditor.commands._archive import _archive
        # Call the function directly with appropriate parameters
        # Note: Click commands can be invoked as regular functions
        _archive.callback(run_type="full", diff_spec=None)
        print("[INFO] Previous run archived successfully", file=sys.stderr)
    except ImportError as e:
        print(f"[WARNING] Could not import archive command: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[WARNING] Archive operation failed: {e}", file=sys.stderr)
    
    # Track all created files throughout execution
    all_created_files = []
    
    # CRITICAL FIX: Open log file immediately for real-time writing
    # This ensures we don't lose logs if the pipeline crashes
    # Write directly to .pf root, not in readthis (which gets recreated by extraction)
    pf_dir = Path(root) / ".pf"
    pf_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = pf_dir / "pipeline.log"
    log_lines = []  # Keep for return value
    
    # Open log file in write mode with line buffering for immediate writes
    log_file = None
    try:
        log_file = open(log_file_path, 'w', encoding='utf-8', buffering=1)
    except Exception as e:
        print(f"[CRITICAL] Failed to open log file {log_file_path}: {e}", file=sys.stderr)
        # Fall back to memory-only logging if file can't be opened
        log_file = None
    
    # CRITICAL: Create the .pf/raw/ directory for ground truth preservation
    # This directory will store immutable copies of all analysis artifacts
    raw_dir = Path(root) / ".pf" / "raw"
    try:
        raw_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[CRITICAL] Failed to create raw directory {raw_dir}: {e}", file=sys.stderr)
        # Continue execution - we'll handle missing directory during file moves
    
    # Ensure readthis directory exists for fresh chunks
    # Archive has already moved old content to history
    readthis_dir = Path(root) / ".pf" / "readthis"
    readthis_dir.mkdir(parents=True, exist_ok=True)
    
    def log_output(message, is_error=False):
        """Log message to callback, file (real-time), and memory."""
        if log_callback and not quiet:
            log_callback(message, is_error)
        # Always add to log list for return value
        log_lines.append(message)
        # CRITICAL: Write immediately to file and flush (if file is open)
        if log_file:
            try:
                log_file.write(message + '\n')
                log_file.flush()  # Force write to disk immediately
            except Exception as e:
                print(f"[CRITICAL] Failed to write to log file: {e}", file=sys.stderr)
                # Continue execution - logging failure shouldn't stop pipeline
    
    # Log header
    log_output(f"TheAuditor Full Pipeline Execution Log")
    log_output(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_output(f"Working Directory: {Path(root).resolve()}")
    log_output("=" * 80)
    
    # Dynamically discover available commands from CLI registration (Courier principle)
    from theauditor.cli import cli
    
    # Get all registered commands, excluding internal (_) and special commands
    available_commands = sorted(cli.commands.keys())
    
    # Define execution order and arguments for known commands
    # This provides the order and arguments, but dynamically adapts to available commands
    command_order = [
        ("index", []),
        ("detect-frameworks", []),
        ("deps", ["--check-latest"]),
        ("docs", ["fetch", "--deps", "./.pf/raw/deps.json"]),
        ("docs", ["summarize"]),
        ("workset", ["--all"]),
        ("lint", ["--workset"]),
        ("detect-patterns", []),
        ("graph", ["build"]),
        ("graph", ["analyze"]),
        ("graph", ["viz", "--view", "full", "--include-analysis"]),
        ("graph", ["viz", "--view", "cycles", "--include-analysis"]),
        ("graph", ["viz", "--view", "hotspots", "--include-analysis"]),
        ("graph", ["viz", "--view", "layers", "--include-analysis"]),
        ("cfg", ["analyze", "--complexity-threshold", "10"]),
        ("metadata", ["churn"]),  # Collect git history (temporal dimension)
        ("taint-analyze", []),
        ("fce", []),
        ("report", []),
        ("summary", []),
    ]
    
    # Build command list from available commands in the defined order
    commands = []
    phase_num = 0
    
    for cmd_name, extra_args in command_order:
        # Check if command exists (dynamic discovery)
        if cmd_name in available_commands or (cmd_name == "docs" and "docs" in available_commands) or (cmd_name == "graph" and "graph" in available_commands) or (cmd_name == "cfg" and "cfg" in available_commands):
            phase_num += 1
            # Generate human-readable description from command name
            if cmd_name == "index":
                description = f"{phase_num}. Index repository"
                # Add --exclude-self flag if requested
                if exclude_self and cmd_name == "index":
                    extra_args = extra_args + ["--exclude-self"]
            elif cmd_name == "detect-frameworks":
                description = f"{phase_num}. Detect frameworks"
            elif cmd_name == "deps" and "--check-latest" in extra_args:
                description = f"{phase_num}. Check dependencies"
            elif cmd_name == "docs" and "fetch" in extra_args:
                description = f"{phase_num}. Fetch documentation"
            elif cmd_name == "docs" and "summarize" in extra_args:
                description = f"{phase_num}. Summarize documentation"
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
            elif cmd_name == "report":
                description = f"{phase_num}. Generate report"
            elif cmd_name == "summary":
                description = f"{phase_num}. Generate audit summary"
            else:
                # Generic description for any new commands
                description = f"{phase_num}. Run {cmd_name.replace('-', ' ')}"
            
            # Build command array - use python module directly
            command_array = [sys.executable, "-m", "theauditor.cli", cmd_name] + extra_args
            commands.append((description, command_array))
        else:
            # Command not available, log warning but continue (resilient)
            log_output(f"[WARNING] Command '{cmd_name}' not available, skipping")
    
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
        
        # Track C: Network I/O
        elif "deps" in cmd_str:
            if not offline:  # Skip deps if offline mode
                track_c_commands.append((phase_name, cmd))
        elif "docs" in cmd_str:
            if not offline:  # Skip docs if offline mode
                track_c_commands.append((phase_name, cmd))
        
        # Stage 4: Final aggregation (must run last)
        elif "fce" in cmd_str:
            final_commands.append((phase_name, cmd))
        elif "report" in cmd_str:
            final_commands.append((phase_name, cmd))
        elif "summary" in cmd_str:
            final_commands.append((phase_name, cmd))
        else:
            # Default to final commands for safety
            final_commands.append((phase_name, cmd))
    
    # STAGE 1: Foundation (Sequential)
    log_output("\n" + "="*60)
    log_output("[STAGE 1] FOUNDATION - Sequential Execution")
    log_output("="*60)
    
    for phase_name, cmd in foundation_commands:
        current_phase += 1
        log_output(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")
        start_time = time.time()
        
        try:
            # Execute foundation command
            if TempManager:
                stdout_file, stderr_file = TempManager.create_temp_files_for_subprocess(
                    root, f"foundation_{phase_name.replace(' ', '_')}"
                )
            else:
                # Fallback to regular tempfile
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt') as out_tmp, \
                     tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt') as err_tmp:
                    stdout_file = out_tmp.name
                    stderr_file = err_tmp.name
            
            with open(stdout_file, 'w+', encoding='utf-8') as out_fp, \
                 open(stderr_file, 'w+', encoding='utf-8') as err_fp:
                
                # Determine appropriate timeout for this command
                cmd_timeout = get_command_timeout(cmd)
                
                result = run_subprocess_with_interrupt(
                    cmd,
                    stdout_fp=out_fp,
                    stderr_fp=err_fp,
                    cwd=root,
                    shell=IS_WINDOWS,  # Windows compatibility fix
                    timeout=cmd_timeout  # Adaptive timeout based on command type
                )
            
            # Read outputs
            with open(stdout_file, 'r', encoding='utf-8') as f:
                result.stdout = f.read()
            with open(stderr_file, 'r', encoding='utf-8') as f:
                result.stderr = f.read()
            
            # Clean up temp files
            try:
                os.unlink(stdout_file)
                os.unlink(stderr_file)
            except (OSError, PermissionError):
                pass
            
            elapsed = time.time() - start_time
            
            if result.returncode == 0:
                log_output(f"[OK] {phase_name} completed in {elapsed:.1f}s")
                if result.stdout:
                    lines = result.stdout.strip().split('\n')
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
                            # Show more lines for table output to include actual data
                            display_lines = []
                            for i, line in enumerate(lines):
                                if i < 6 or (i == 0):  # Show first line (path info) + table header + first few data rows
                                    display_lines.append(line)
                                    if log_callback and not quiet:
                                        log_callback(f"  {line}", False)
                                    log_lines.append(f"  {line}")
                            if len(lines) > 6:
                                truncate_msg = f"  ... ({len(lines) - 6} more lines)"
                                if log_callback and not quiet:
                                    log_callback(truncate_msg, False)
                                log_lines.append(truncate_msg)
                        else:
                            # Regular truncation for non-table output
                            for line in lines[:3]:
                                if log_callback and not quiet:
                                    log_callback(f"  {line}", False)
                                log_lines.append(f"  {line}")
                            if len(lines) > 3:
                                truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                                if log_callback and not quiet:
                                    log_callback(truncate_msg, False)
                                log_lines.append(truncate_msg)
                    else:
                        # Regular truncation for other commands
                        for line in lines[:3]:
                            if log_callback and not quiet:
                                log_callback(f"  {line}", False)
                            log_lines.append(f"  {line}")
                        if len(lines) > 3:
                            truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                            if log_callback and not quiet:
                                log_callback(truncate_msg, False)
                            log_lines.append(truncate_msg)
            else:
                failed_phases += 1
                log_output(f"[FAILED] {phase_name} failed (exit code {result.returncode})", is_error=True)
                if result.stderr:
                    # Write FULL error to log file
                    if log_file:
                        log_file.write(f"  [Full error output]:\n")
                        log_file.write(f"  {result.stderr}\n")
                        log_file.flush()
                    # Show truncated in terminal
                    error_msg = f"  Error: {result.stderr[:200]}"
                    if len(result.stderr) > 200:
                        error_msg += "... [see pipeline.log for full error]"
                    if log_callback and not quiet:
                        log_callback(error_msg, True)
                    log_lines.append(error_msg)
                # Foundation failure stops pipeline
                log_output("[CRITICAL] Foundation stage failed - stopping pipeline", is_error=True)
                break
                
        except Exception as e:
            failed_phases += 1
            log_output(f"[FAILED] {phase_name} failed: {e}", is_error=True)
            break
    
    # STAGE 2: Data Preparation (Sequential) - Only if foundation succeeded
    if failed_phases == 0 and data_prep_commands:
        log_output("\n" + "="*60)
        log_output("[STAGE 2] DATA PREPARATION - Sequential Execution")
        log_output("="*60)
        log_output("Preparing data structures for parallel analysis...")
        
        for phase_name, cmd in data_prep_commands:
            current_phase += 1
            log_output(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")
            start_time = time.time()
            
            try:
                # Execute data preparation command
                if TempManager:
                    stdout_file, stderr_file = TempManager.create_temp_files_for_subprocess(
                        root, f"dataprep_{phase_name.replace(' ', '_')}"
                    )
                else:
                    # Fallback to regular tempfile
                    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt') as out_tmp, \
                         tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt') as err_tmp:
                        stdout_file = out_tmp.name
                        stderr_file = err_tmp.name
                
                with open(stdout_file, 'w+', encoding='utf-8') as out_fp, \
                     open(stderr_file, 'w+', encoding='utf-8') as err_fp:
                    
                    # Determine appropriate timeout for this command
                    cmd_timeout = get_command_timeout(cmd)
                    
                    result = run_subprocess_with_interrupt(
                        cmd,
                        stdout_fp=out_fp,
                        stderr_fp=err_fp,
                        cwd=root,
                        shell=IS_WINDOWS,  # Windows compatibility fix
                        timeout=cmd_timeout  # Adaptive timeout based on command type
                    )
                
                # Read outputs
                with open(stdout_file, 'r', encoding='utf-8') as f:
                    result.stdout = f.read()
                with open(stderr_file, 'r', encoding='utf-8') as f:
                    result.stderr = f.read()
                
                # Clean up temp files
                try:
                    os.unlink(stdout_file)
                    os.unlink(stderr_file)
                except (OSError, PermissionError):
                    pass
                
                elapsed = time.time() - start_time
                
                if result.returncode == 0:
                    log_output(f"[OK] {phase_name} completed in {elapsed:.1f}s")
                    if result.stdout:
                        lines = result.stdout.strip().split('\n')
                        # Write FULL output to log file
                        if log_file and len(lines) > 3:
                            log_file.write("  [Full output below, truncated in terminal]\n")
                            for line in lines:
                                log_file.write(f"  {line}\n")
                            log_file.flush()
                        
                        # Show first few lines in terminal
                        for line in lines[:3]:
                            if log_callback and not quiet:
                                log_callback(f"  {line}", False)
                            log_lines.append(f"  {line}")
                        if len(lines) > 3:
                            truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                            if log_callback and not quiet:
                                log_callback(truncate_msg, False)
                            log_lines.append(truncate_msg)
                else:
                    failed_phases += 1
                    log_output(f"[FAILED] {phase_name} failed (exit code {result.returncode})", is_error=True)
                    if result.stderr:
                        # Write FULL error to log file
                        if log_file:
                            log_file.write(f"  [Full error output]:\n")
                            log_file.write(f"  {result.stderr}\n")
                            log_file.flush()
                        # Show truncated in terminal
                        error_msg = f"  Error: {result.stderr[:200]}"
                        if len(result.stderr) > 200:
                            error_msg += "... [see pipeline.log for full error]"
                        if log_callback and not quiet:
                            log_callback(error_msg, True)
                        log_lines.append(error_msg)
                    # Data prep failure stops pipeline
                    log_output("[CRITICAL] Data preparation stage failed - stopping pipeline", is_error=True)
                    break
                    
            except Exception as e:
                failed_phases += 1
                log_output(f"[FAILED] {phase_name} failed: {e}", is_error=True)
                break
    
    # Only proceed to parallel stage if foundation and data prep succeeded
    if failed_phases == 0 and (track_a_commands or track_b_commands or track_c_commands):
        # STAGE 3: Heavy Parallel Analysis (Rebalanced)
        log_output("\n" + "="*60)
        log_output("[STAGE 3] HEAVY PARALLEL ANALYSIS - Optimized Execution")
        log_output("="*60)
        log_output("Launching rebalanced parallel tracks:")
        if track_a_commands:
            log_output("  Track A: Taint Analysis (isolated heavy task)")
        if track_b_commands:
            log_output("  Track B: Static & Graph Analysis (lint, patterns, graph)")
        if track_c_commands and not offline:
            log_output("  Track C: Network I/O (deps, docs)")
        elif offline:
            log_output("  [OFFLINE MODE] Track C skipped")
        
        # Execute parallel tracks using ThreadPoolExecutor (Windows-safe)
        parallel_results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            # Submit Track A if it has commands (Taint Analysis)
            if track_a_commands:
                future_a = executor.submit(run_command_chain, track_a_commands, root, "Track A (Taint Analysis)")
                futures.append(future_a)
                current_phase += len(track_a_commands)
            
            # Submit Track B if it has commands (Static & Graph)
            if track_b_commands:
                future_b = executor.submit(run_command_chain, track_b_commands, root, "Track B (Static & Graph)")
                futures.append(future_b)
                current_phase += len(track_b_commands)
            
            # Submit Track C if it has commands (Network I/O)
            if track_c_commands:
                future_c = executor.submit(run_command_chain, track_c_commands, root, "Track C (Network I/O)")
                futures.append(future_c)
                current_phase += len(track_c_commands)
            
            # STAGE 3: Synchronization Point - Wait for all parallel tracks
            log_output("\n[SYNC] Waiting for parallel tracks to complete...")
            
            # Monitor progress while waiting
            status_dir = Path(root) / ".pf" / "status"
            last_status_check = 0
            status_check_interval = 2  # Check every 2 seconds
            
            # Process futures as they complete, but also check status periodically
            pending_futures = list(futures)
            while pending_futures:
                # Check for completed futures immediately (0 timeout) to avoid delays
                # Only wait with timeout if nothing is done yet
                done, still_pending = wait(pending_futures, timeout=0)
                
                if done:
                    # Process completed futures immediately
                    for future in done:
                        try:
                            result = future.result()
                            parallel_results.append(result)
                            if result["success"]:
                                log_output(f"[OK] {result['name']} completed in {result['elapsed']:.1f}s")
                            else:
                                log_output(f"[FAILED] {result['name']} failed", is_error=True)
                                failed_phases += 1
                        except KeyboardInterrupt:
                            log_output(f"[INTERRUPTED] Pipeline stopped by user", is_error=True)
                            # Cancel remaining futures
                            for f in still_pending:
                                f.cancel()
                            raise  # Re-raise to exit
                        except Exception as e:
                            log_output(f"[ERROR] Parallel track failed with exception: {e}", is_error=True)
                            failed_phases += 1
                    
                    # Update pending list
                    pending_futures = list(still_pending)
                    continue  # Check again immediately for more completed futures
                
                # No futures completed, wait a bit and show status
                done, pending_futures = wait(pending_futures, timeout=status_check_interval)
                
                # Read and display status if enough time has passed
                current_time = time.time()
                if current_time - last_status_check >= status_check_interval:
                    last_status_check = current_time
                    
                    # Read all status files
                    if status_dir.exists():
                        status_summary = []
                        status_files = list(status_dir.glob("*.status"))
                        # Debug: show if we found any status files
                        if not status_files and not quiet:
                            log_output(f"[DEBUG] No status files found in {status_dir}")
                        for status_file in status_files:
                            try:
                                with open(status_file, 'r', encoding='utf-8') as f:
                                    status_data = json.loads(f.read().strip())
                                    track = status_data.get("track", "Unknown")
                                    completed = status_data.get("completed", 0)
                                    total = status_data.get("total", 0)
                                    current = status_data.get("current", "")
                                    
                                    # Format progress
                                    if total > 0:
                                        progress = f"[{completed}/{total}]"
                                    else:
                                        progress = ""
                                    
                                    status_summary.append(f"  {track}: {progress} {current[:50]}")
                            except Exception:
                                pass  # Ignore status read errors
                        
                        if status_summary:
                            log_output("[PROGRESS] Track Status:")
                            for status_line in status_summary:
                                log_output(status_line)
                
                # Process any futures that completed during the wait
                for future in done:
                    try:
                        result = future.result()
                        parallel_results.append(result)
                        if result["success"]:
                            log_output(f"[OK] {result['name']} completed in {result['elapsed']:.1f}s")
                        else:
                            log_output(f"[FAILED] {result['name']} failed", is_error=True)
                            failed_phases += 1
                    except KeyboardInterrupt:
                        log_output(f"[INTERRUPTED] Pipeline stopped by user", is_error=True)
                        # Cancel remaining futures
                        for f in pending_futures:
                            f.cancel()
                        raise  # Re-raise to exit
                    except Exception as e:
                        log_output(f"[ERROR] Parallel track failed with exception: {e}", is_error=True)
                        failed_phases += 1
        
        # Print outputs from parallel tracks sequentially for clean logging
        log_output("\n" + "="*60)
        log_output("[STAGE 3 RESULTS] Parallel Track Outputs")
        log_output("="*60)
        
        for result in parallel_results:
            log_output(result["output"])
            if result["errors"]:
                log_output("[ERRORS]:")
                log_output(result["errors"])
    
    # STAGE 4: Final Aggregation (Sequential) 
    if failed_phases == 0 and final_commands:
        log_output("\n" + "="*60)
        log_output("[STAGE 4] FINAL AGGREGATION - Sequential Execution")
        log_output("="*60)
        
        for phase_name, cmd in final_commands:
            current_phase += 1
            log_output(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")
            start_time = time.time()
            
            try:
                # Execute final aggregation command
                if TempManager:
                    stdout_file, stderr_file = TempManager.create_temp_files_for_subprocess(
                        root, f"final_{phase_name.replace(' ', '_')}"
                    )
                else:
                    # Fallback to regular tempfile
                    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt') as out_tmp, \
                         tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt') as err_tmp:
                        stdout_file = out_tmp.name
                        stderr_file = err_tmp.name
                
                with open(stdout_file, 'w+', encoding='utf-8') as out_fp, \
                     open(stderr_file, 'w+', encoding='utf-8') as err_fp:
                    
                    # Determine appropriate timeout for this command
                    cmd_timeout = get_command_timeout(cmd)
                    
                    result = run_subprocess_with_interrupt(
                        cmd,
                        stdout_fp=out_fp,
                        stderr_fp=err_fp,
                        cwd=root,
                        shell=IS_WINDOWS,  # Windows compatibility fix
                        timeout=cmd_timeout  # Adaptive timeout based on command type
                    )
                
                # Read outputs
                with open(stdout_file, 'r', encoding='utf-8') as f:
                    result.stdout = f.read()
                with open(stderr_file, 'r', encoding='utf-8') as f:
                    result.stderr = f.read()
                
                # Clean up temp files
                try:
                    os.unlink(stdout_file)
                    os.unlink(stderr_file)
                except (OSError, PermissionError):
                    pass
                
                elapsed = time.time() - start_time
                
                # Handle special exit codes for findings commands
                is_findings_command = "taint-analyze" in cmd or ("deps" in cmd and "--vuln-scan" in cmd)
                if is_findings_command:
                    success = result.returncode in [0, 1, 2]
                else:
                    success = result.returncode == 0
                
                if success:
                    if result.returncode == 2 and is_findings_command:
                        log_output(f"[OK] {phase_name} completed in {elapsed:.1f}s - CRITICAL findings")
                    elif result.returncode == 1 and is_findings_command:
                        log_output(f"[OK] {phase_name} completed in {elapsed:.1f}s - HIGH findings")
                    else:
                        log_output(f"[OK] {phase_name} completed in {elapsed:.1f}s")
                    
                    if result.stdout:
                        lines = result.stdout.strip().split('\n')
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
                                # Show more lines for table output to include actual data
                                display_lines = []
                                for i, line in enumerate(lines):
                                    if i < 6 or (i == 0):  # Show first line (path info) + table header + first few data rows
                                        display_lines.append(line)
                                        if log_callback and not quiet:
                                            log_callback(f"  {line}", False)
                                        log_lines.append(f"  {line}")
                                if len(lines) > 6:
                                    truncate_msg = f"  ... ({len(lines) - 6} more lines)"
                                    if log_callback and not quiet:
                                        log_callback(truncate_msg, False)
                                    log_lines.append(truncate_msg)
                            else:
                                # Regular truncation for non-table output
                                for line in lines[:3]:
                                    if log_callback and not quiet:
                                        log_callback(f"  {line}", False)
                                    log_lines.append(f"  {line}")
                                if len(lines) > 3:
                                    truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                                    if log_callback and not quiet:
                                        log_callback(truncate_msg, False)
                                    log_lines.append(truncate_msg)
                        else:
                            # Regular truncation for other commands
                            for line in lines[:3]:
                                if log_callback and not quiet:
                                    log_callback(f"  {line}", False)
                                log_lines.append(f"  {line}")
                            if len(lines) > 3:
                                truncate_msg = f"  ... ({len(lines) - 3} more lines)"
                                if log_callback and not quiet:
                                    log_callback(truncate_msg, False)
                                log_lines.append(truncate_msg)
                else:
                    failed_phases += 1
                    log_output(f"[FAILED] {phase_name} failed (exit code {result.returncode})", is_error=True)
                    if result.stderr:
                        # Write FULL error to log file
                        if log_file:
                            log_file.write(f"  [Full error output]:\n")
                            log_file.write(f"  {result.stderr}\n")
                            log_file.flush()
                        # Show truncated in terminal
                        error_msg = f"  Error: {result.stderr[:200]}"
                        if len(result.stderr) > 200:
                            error_msg += "... [see pipeline.log for full error]"
                        if log_callback and not quiet:
                            log_callback(error_msg, True)
                        log_lines.append(error_msg)
                
                # CRITICAL: Run extraction AFTER FCE and BEFORE report
                if "factual correlation" in phase_name.lower():
                    try:
                        from theauditor.extraction import extract_all_to_readthis
                        
                        log_output("\n" + "="*60)
                        log_output("[EXTRACTION] Creating AI-consumable chunks from raw data")
                        log_output("="*60)
                        
                        extraction_start = time.time()
                        extraction_success = extract_all_to_readthis(root)
                        extraction_elapsed = time.time() - extraction_start
                        
                        if extraction_success:
                            log_output(f"[OK] Chunk extraction completed in {extraction_elapsed:.1f}s")
                            log_output("[INFO] AI-readable chunks available in .pf/readthis/")
                        else:
                            log_output(f"[WARNING] Chunk extraction completed with errors in {extraction_elapsed:.1f}s", is_error=True)
                            log_output("[WARNING] Some chunks may be incomplete", is_error=True)
                            
                    except ImportError as e:
                        log_output(f"[ERROR] Could not import extraction module: {e}", is_error=True)
                        log_output("[ERROR] Chunks will not be generated", is_error=True)
                    except Exception as e:
                        log_output(f"[ERROR] Ticket extraction failed: {e}", is_error=True)
                        log_output("[ERROR] Raw data preserved in .pf/raw/ but no chunks created", is_error=True)
                
            except Exception as e:
                failed_phases += 1
                log_output(f"[FAILED] {phase_name} failed: {e}", is_error=True)
    
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
    log_output("\n" + "="*60)
    if failed_phases == 0 and phases_with_warnings == 0:
        log_output(f"[OK] AUDIT COMPLETE - All {total_phases} phases successful")
    elif phases_with_warnings > 0 and failed_phases == 0:
        log_output(f"[WARNING] AUDIT COMPLETE - {phases_with_warnings} phases completed with errors")
    else:
        log_output(f"[WARN] AUDIT COMPLETE - {failed_phases} phases failed, {phases_with_warnings} phases with errors")
    log_output(f"[TIME] Total time: {pipeline_elapsed:.1f}s ({pipeline_elapsed/60:.1f} minutes)")
    
    # Display all created files summary
    log_output("\n" + "="*60)
    log_output("[FILES] ALL CREATED FILES")
    log_output("="*60)
    
    # Count files by category
    pf_files = [f for f in all_created_files if f.startswith(".pf/")]
    readthis_files = [f for f in all_created_files if f.startswith(".pf/readthis/")]
    docs_files = [f for f in all_created_files if f.startswith(".pf/docs/")]
    root_files = [f for f in all_created_files if "/" not in f]
    
    log_output(f"\n[STATS] Summary:")
    log_output(f"  Total files created: {len(all_created_files)}")
    log_output(f"  .pf/ files: {len(pf_files)}")
    log_output(f"  .pf/readthis/ files: {len(readthis_files)}")
    if docs_files:
        log_output(f"  .pf/docs/ files: {len(docs_files)}")
    log_output(f"  Root files: {len(root_files)}")
    
    log_output(f"\n[SAVED] Complete file list saved to: .pf/allfiles.md")
    log_output(f"\n[TIP] Key artifacts:")
    log_output(f"  * .pf/readthis/ - All AI-consumable chunks")
    log_output(f"  * .pf/allfiles.md - Complete file list")
    log_output(f"  * .pf/pipeline.log - Full execution log")
    log_output(f"  * .pf/findings.json - Pattern detection results")
    log_output(f"  * .pf/risk_scores.json - Risk analysis")
    
    log_output("\n" + "="*60)
    log_output("[COMPLETE] AUDIT SUITE EXECUTION COMPLETE")
    log_output("="*60)
    
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
    
    # Clean up temporary files created during pipeline execution
    if TempManager:
        try:
            TempManager.cleanup_temp_dir(root)
            print("[INFO] Temporary files cleaned up", file=sys.stderr)
        except Exception as e:
            print(f"[WARNING] Could not clean temp files: {e}", file=sys.stderr)
    
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
    patterns_path = Path(root) / ".pf" / "raw" / "patterns.json"
    if not patterns_path.exists():
        # Fallback to findings.json (alternate name)
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