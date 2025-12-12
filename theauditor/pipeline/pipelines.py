"""Pipeline execution module for TheAuditor."""

import asyncio
import os
import platform
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from .renderer import RichRenderer
from .structures import PhaseResult, TaskStatus

IS_WINDOWS = platform.system() == "Windows"


COMMAND_TIMEOUTS = {
    "index": 600,
    "detect-frameworks": 180,
    "deps": 1200,
    "docs": 600,
    "workset": 180,
    "lint": 600,
    "detect-patterns": 1800,
    "graph": 600,
    "terraform": 600,
    "taint": 1800,
    "fce": 900,
    "learn": 300,
}


DEFAULT_TIMEOUT = int(os.environ.get("THEAUDITOR_TIMEOUT_SECONDS", "900"))


SECURITY_TOOLS = frozenset(
    {
        "patterns",
        "taint",
        "terraform",
        "cdk",
        "github-actions-rules",
        "vulnerability_scanner",
        "indexer",  # Parse/syntax errors are real failures that should block deployment
    }
)


def _normalize_severity(raw_severity: str) -> str:
    """Normalize severity names to standard set: critical, high, medium, low.

    Different tools use different severity names:
    - OSV: "moderate" -> "medium"
    - Linters/indexer: "error" -> "high", "warning" -> "medium"
    """
    mapping = {
        "moderate": "medium",
        "error": "high",
        "warning": "medium",
    }
    return mapping.get(raw_severity, raw_severity)


def get_command_timeout(cmd: list[str]) -> int:
    """Determine appropriate timeout for a command based on its name."""

    cmd_str = " ".join(cmd)

    for cmd_name, timeout in COMMAND_TIMEOUTS.items():
        if cmd_name in cmd_str:
            env_key = f"THEAUDITOR_TIMEOUT_{cmd_name.upper().replace('-', '_')}_SECONDS"
            return int(os.environ.get(env_key, timeout))

    return DEFAULT_TIMEOUT


_LOGURU_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}\s*\|\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\|")


def _format_stderr_output(stderr: str, max_chars: int = 300) -> list[str]:
    """Format stderr for display, detecting loguru-formatted output.

    If stderr contains loguru-formatted lines (HH:MM:SS | LEVEL |),
    print them directly without "Error:" prefix since they're already formatted.
    Otherwise, use "Error:" prefix for raw error messages.

    Returns list of formatted lines ready for renderer.on_log().
    """
    if not stderr or not stderr.strip():
        return []

    lines = stderr.strip().split("\n")
    output: list[str] = []
    char_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        formatted = f"  {line}" if _LOGURU_PATTERN.match(line) else f"  Error: {line}"

        if char_count + len(formatted) > max_chars:
            remaining = max_chars - char_count
            if remaining > 20:
                output.append(formatted[:remaining] + "...")
            output.append("  [dim]... see .pf/pipeline.log for full error[/dim]")
            break

        output.append(formatted)
        char_count += len(formatted)

    return output


def _format_phase_output(stdout: str, phase_name: str, max_lines: int = 3) -> list[str]:
    """Extract and format key output from phase stdout.

    Returns list of formatted lines ready for renderer.on_log().
    Extracts metrics, suppresses noise, and keeps output clean.
    """
    if not stdout or not stdout.strip():
        return []

    lines = stdout.strip().split("\n")
    output: list[str] = []

    metric_patterns = [
        (r"(?:total|found|wrote|detected|analyzed|indexed)\s*[:\s]*(\d+)", None),
        (r"^[\s]*([A-Z][a-zA-Z\s]+):\s*(\d+)", lambda m: f"{m.group(1).strip()}: {m.group(2)}"),
        (
            r"(critical|high|medium|low|error|warning)s?\s*[:\s]*(\d+)",
            lambda m: f"{m.group(1).title()}: {m.group(2)}",
        ),
    ]

    is_table = any("---" in line or line.count("|") >= 2 for line in lines[:10])

    if is_table and len(lines) <= 30:
        return [f"  {line}" for line in lines]

    metrics_found: list[str] = []
    for line in lines:
        line_lower = line.lower().strip()

        if not line_lower or line_lower.startswith("=") or line_lower.startswith("-"):
            continue

        for pattern, formatter in metric_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                if formatter:
                    metrics_found.append(formatter(match))
                else:
                    clean_line = line.strip()
                    if len(clean_line) <= 60:
                        metrics_found.append(clean_line)
                break

    if metrics_found:
        seen = set()
        for metric in metrics_found[:5]:
            if metric not in seen:
                colored_metric = re.sub(r"(\d+)", r"[cyan]\1[/cyan]", metric)
                output.append(f"  [dim]{colored_metric}[/dim]")
                seen.add(metric)
        return output

    shown = 0
    for line in lines:
        if line.strip() and not line.strip().startswith("="):
            colored_line = re.sub(r"(\d+)", r"[cyan]\1[/cyan]", line.strip())
            output.append(f"  {colored_line}")
            shown += 1
            if shown >= max_lines:
                break

    remaining = len([line for line in lines if line.strip()]) - shown
    if remaining > 0:
        output.append(f"  [dim]... ([cyan]{remaining}[/cyan] more lines)[/dim]")

    return output


_stop_requested = False


def signal_handler(signum, frame):
    """Handle Ctrl+C by setting stop flag."""
    global _stop_requested

    logger.info("\n Interrupt received, stopping pipeline gracefully...")
    _stop_requested = True


def is_stop_requested() -> bool:
    """Check if stop was requested (asyncio-safe)."""
    return _stop_requested


def reset_stop_flag():
    """Reset stop flag for new pipeline run."""
    global _stop_requested
    _stop_requested = False


signal.signal(signal.SIGINT, signal_handler)
if not IS_WINDOWS:
    signal.signal(signal.SIGTERM, signal_handler)


async def run_command_async(cmd: list[str], cwd: str, timeout: int = 900) -> PhaseResult:
    """Execute subprocess using asyncio memory pipes (no temp files)."""
    start_time = time.time()
    cmd_name = cmd[0] if cmd else "unknown"

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:

            while True:
                if is_stop_requested():
                    process.kill()
                    await process.wait()
                    return PhaseResult(
                        name=cmd_name,
                        status=TaskStatus.FAILED,
                        elapsed=time.time() - start_time,
                        stdout="",
                        stderr="[INTERRUPTED] Process killed by user",
                        exit_code=-2,
                    )

                try:
                    stdout_data, stderr_data = await asyncio.wait_for(
                        process.communicate(), timeout=0.5
                    )
                    return PhaseResult(
                        name=cmd_name,
                        status=TaskStatus.SUCCESS if process.returncode == 0 else TaskStatus.FAILED,
                        elapsed=time.time() - start_time,
                        stdout=stdout_data.decode("utf-8", errors="replace"),
                        stderr=stderr_data.decode("utf-8", errors="replace"),
                        exit_code=process.returncode or 0,
                    )
                except TimeoutError:
                    if time.time() - start_time > timeout:
                        process.kill()
                        await process.wait()
                        return PhaseResult(
                            name=cmd_name,
                            status=TaskStatus.FAILED,
                            elapsed=time.time() - start_time,
                            stdout="",
                            stderr=f"Command timed out after {timeout}s",
                            exit_code=-1,
                        )

                    continue

        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            return PhaseResult(
                name=cmd_name,
                status=TaskStatus.FAILED,
                elapsed=time.time() - start_time,
                stdout="",
                stderr="[CANCELLED] Process killed",
                exit_code=-2,
            )

    except Exception as e:
        return PhaseResult(
            name=cmd_name,
            status=TaskStatus.FAILED,
            elapsed=time.time() - start_time,
            stdout="",
            stderr=f"Subprocess error: {str(e)}",
            exit_code=-1,
        )


async def run_chain_silent(
    commands: list[tuple[str, list[str]]],
    root: str,
    chain_name: str,
) -> list[PhaseResult]:
    """Execute a chain of commands silently (no console output)."""
    results: list[PhaseResult] = []

    for description, cmd in commands:
        if is_stop_requested():
            results.append(
                PhaseResult(
                    name=description,
                    status=TaskStatus.FAILED,
                    elapsed=0.0,
                    stdout="",
                    stderr="[INTERRUPTED] Pipeline stopped by user",
                    exit_code=-1,
                )
            )
            break

        cmd_timeout = get_command_timeout(cmd)
        result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)

        result = PhaseResult(
            name=description,
            status=result.status,
            elapsed=result.elapsed,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )

        cmd_str = " ".join(str(c) for c in cmd)
        is_findings_command = (
            "taint" in cmd_str
            or ("deps" in cmd_str and "--vuln-scan" in cmd_str)
            or "cdk" in cmd_str
            or "terraform" in cmd_str
            or "workflows" in cmd_str
        )

        if is_findings_command:
            if result.exit_code in [0, 1, 2]:
                result = PhaseResult(
                    name=result.name,
                    status=TaskStatus.SUCCESS,
                    elapsed=result.elapsed,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.exit_code,
                )

        results.append(result)

        if not result.success:
            break

    return results


def _get_findings_from_db(root: Path) -> dict:
    """Query findings_consolidated for severity counts, broken down by tool.

    Uses a single query with consistent severity normalization for both
    totals (SECURITY_TOOLS only) and by_tool breakdown (all tools).

    Returns:
        dict with:
            - critical/high/medium/low: total counts per severity (SECURITY_TOOLS only)
            - total_vulnerabilities: sum of all security tool findings
            - by_tool: dict mapping tool_name -> {critical, high, medium, low}
    """
    import sqlite3

    db_path = root / ".pf" / "repo_index.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Single query to get all findings by tool and severity
    cursor.execute(
        """
        SELECT tool, severity, COUNT(*) as cnt
        FROM findings_consolidated
        GROUP BY tool, severity
    """
    )

    # Initialize accumulators
    by_tool: dict[str, dict[str, int]] = {}
    totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for tool, raw_severity, count in cursor.fetchall():
        # Normalize severity ONCE using shared helper
        severity = _normalize_severity(raw_severity)

        # Skip unknown severities (e.g., "info", "note")
        if severity not in totals:
            continue

        # Accumulate by_tool (ALL tools for visibility)
        if tool not in by_tool:
            by_tool[tool] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_tool[tool][severity] += count

        # Accumulate totals (SECURITY_TOOLS only - these affect exit code)
        if tool in SECURITY_TOOLS:
            totals[severity] += count

    conn.close()

    return {
        "critical": totals["critical"],
        "high": totals["high"],
        "medium": totals["medium"],
        "low": totals["low"],
        "total_vulnerabilities": sum(totals.values()),
        "by_tool": by_tool,
    }


def _detect_iac_presence(db_path: Path) -> dict[str, bool]:
    """Check which IaC types have data in the database.

    Called after Stage 1 Foundation to determine which IaC-specific commands
    to run. Skips terraform/cdk/workflows commands if no data exists.

    Returns:
        dict with keys: terraform, cdk, github_workflows
        Values are True if that IaC type has indexed data.
    """
    import sqlite3

    if not db_path.exists():
        return {"terraform": False, "cdk": False, "github_workflows": False}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    result = {
        "terraform": False,
        "cdk": False,
        "github_workflows": False,
    }

    # Check terraform_files table
    cursor.execute("SELECT COUNT(*) FROM terraform_files")
    result["terraform"] = cursor.fetchone()[0] > 0

    # Check cdk_constructs table
    cursor.execute("SELECT COUNT(*) FROM cdk_constructs")
    result["cdk"] = cursor.fetchone()[0] > 0

    # Check github_workflows table
    cursor.execute("SELECT COUNT(*) FROM github_workflows")
    result["github_workflows"] = cursor.fetchone()[0] > 0

    conn.close()
    return result


async def run_full_pipeline(
    root: str = ".",
    quiet: bool = False,
    exclude_self: bool = False,
    offline: bool = False,
    use_subprocess_for_taint: bool = False,
    wipe_cache: bool = False,
    index_only: bool = False,
) -> dict[str, Any]:
    """Run complete audit pipeline in exact order specified in teamsop.md."""

    reset_stop_flag()

    root = str(Path(root).resolve())

    pf_dir = Path(root) / ".pf"
    pf_dir.mkdir(parents=True, exist_ok=True)

    archive_success = True
    try:
        from theauditor.commands._archive import _archive

        _archive.callback(run_type="full", diff_spec=None, wipe_cache=wipe_cache)
    except Exception as e:
        logger.warning(f"Archiving failed: {e}")
        archive_success = False

    log_file_path = pf_dir / "pipeline.log"
    error_log_path = pf_dir / "error.log"

    renderer = RichRenderer(quiet=quiet, log_file=log_file_path)
    renderer.start()

    log_lines: list[str] = []
    all_created_files: list[str] = []

    try:
        if archive_success:
            renderer.on_log("[dim]Previous run archived successfully[/dim]")

        from theauditor.pipeline.journal import get_journal_writer

        journal = get_journal_writer(run_type="full")
        renderer.on_log("[dim]Journal writer initialized for ML training[/dim]")

        raw_dir = Path(root) / ".pf" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        renderer.on_log("[bold]TheAuditor[/bold]  Full Pipeline Execution")
        renderer.on_log(
            f"[dim]Started:[/dim] {time.strftime('%Y-%m-%d %H:%M:%S')}  [dim]Directory:[/dim] {Path(root).resolve()}"
        )
        if index_only:
            renderer.on_log(
                "[dim]Mode: INDEX-ONLY (Stage 1 + 2 only, skipping heavy analysis)[/dim]"
            )

        log_lines.append("TheAuditor Full Pipeline Execution Log")
        log_lines.append(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log_lines.append(f"Working Directory: {Path(root).resolve()}")
        if index_only:
            log_lines.append("Mode: INDEX-ONLY (Stage 1 + 2 only, skipping heavy analysis)")
        log_lines.append("=" * 80)

        from theauditor.cli import cli

        available_commands = sorted(cli.commands.keys())

        command_order = [
            ("index", []),
            ("detect-frameworks", []),
            ("deps", ["--vuln-scan"]),
            ("deps", ["--check-latest"]),
            ("docs", ["fetch"]),
            ("workset", ["--all"]),
            ("lint", ["--workset"]),
            ("detect-patterns", []),
            ("graph", ["build"]),
            ("graph", ["build-dfg"]),
            ("terraform", ["provision"]),
            ("terraform", ["analyze"]),
            ("cdk", ["analyze"]),
            ("workflows", ["analyze"]),
            ("graph", ["analyze"]),
            ("graph", ["viz", "--view", "full", "--include-analysis", "--out-dir", ".pf/graphs/"]),
            ("graph", ["viz", "--view", "cycles", "--include-analysis", "--out-dir", ".pf/graphs/"]),
            ("graph", ["viz", "--view", "hotspots", "--include-analysis", "--out-dir", ".pf/graphs/"]),
            ("graph", ["viz", "--view", "layers", "--include-analysis", "--out-dir", ".pf/graphs/"]),
            ("cfg", ["analyze", "--complexity-threshold", "10"]),
            ("metadata", ["churn"]),
            ("taint", []),
            ("fce", []),
            ("session", ["analyze"]),
            ("learn", []),
        ]

        commands = []
        phase_num = 0

        for cmd_name, extra_args in command_order:
            if (
                cmd_name in available_commands
                or cmd_name == "index"
                or (cmd_name == "docs" and "docs" in available_commands)
                or (cmd_name == "graph" and "graph" in available_commands)
                or (cmd_name == "cfg" and "cfg" in available_commands)
                or (cmd_name == "terraform" and "terraform" in available_commands)
                or (cmd_name == "workflows" and "workflows" in available_commands)
                or (cmd_name == "session" and "session" in available_commands)
                or (cmd_name == "learn" and "learn" in available_commands)
            ):
                phase_num += 1

                if cmd_name == "index":
                    description = f"{phase_num}. Index repository"

                    if exclude_self and cmd_name == "index":
                        extra_args = extra_args + ["--exclude-self"]
                elif cmd_name == "detect-frameworks":
                    description = f"{phase_num}. Detect frameworks"
                elif (
                    cmd_name == "deps"
                    and "--vuln-scan" in extra_args
                    and "--check-latest" not in extra_args
                ):
                    description = f"{phase_num}. Scan dependencies for vulnerabilities (offline)"

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
                elif cmd_name == "taint":
                    description = f"{phase_num}. Taint analysis"
                elif cmd_name == "fce":
                    description = f"{phase_num}. Factual correlation engine"
                elif cmd_name == "session":
                    description = f"{phase_num}. Analyze AI agent sessions (Tier 5)"
                elif cmd_name == "learn":
                    description = f"{phase_num}. Train ML models from audit history"
                else:
                    description = f"{phase_num}. Run {cmd_name.replace('-', ' ')}"

                venv_dir = Path(root) / ".auditor_venv"
                if platform.system() == "Windows":
                    venv_aud = venv_dir / "Scripts" / "aud.exe"
                else:
                    venv_aud = venv_dir / "bin" / "aud"

                if venv_aud.exists():
                    command_array = [str(venv_aud), cmd_name] + extra_args
                else:
                    renderer.on_log(
                        f"[bold red]Error:[/bold red] Sandbox not found at [cyan]{venv_aud}[/cyan]",
                        is_error=True,
                    )
                    renderer.on_log(
                        "[bold red]Error:[/bold red] Run 'aud setup-ai --target .' to create sandbox",
                        is_error=True,
                    )
                    log_lines.append(f"[ERROR] Sandbox not found at {venv_aud}")
                    log_lines.append("[ERROR] Run 'aud setup-ai --target .' to create sandbox")

                    command_array = [sys.executable, "-m", "theauditor.cli", cmd_name] + extra_args

                commands.append((description, command_array))
            else:
                renderer.on_log(
                    f"[yellow]Warning:[/yellow] Command '{cmd_name}' not available, skipping"
                )
                log_lines.append(f"[WARNING] Command '{cmd_name}' not available, skipping")

        current_phase = 0
        failed_phases = 0
        failed_phase_names: list[str] = []
        phases_with_warnings = 0
        pipeline_start = time.time()

        def collect_created_files():
            """Collect all files created during execution."""
            files = []

            if (Path(root) / "repo_index.db").exists():
                files.append("repo_index.db")

            pf_dir = Path(root) / ".pf"
            if pf_dir.exists():
                for item in pf_dir.rglob("*"):
                    if item.is_file():
                        files.append(item.relative_to(Path(root)).as_posix())

            docs_dir = Path(root) / ".pf" / "docs"
            if docs_dir.exists():
                for item in docs_dir.rglob("*"):
                    if item.is_file():
                        files.append(item.relative_to(Path(root)).as_posix())

            return sorted(set(files))

        foundation_commands = []
        data_prep_commands = []
        track_a_commands = []
        track_b_commands = []
        track_c_commands = []
        final_commands = []

        for phase_name, cmd in commands:
            cmd_str = " ".join(cmd)

            if "index" in cmd_str or "detect-frameworks" in cmd_str:
                foundation_commands.append((phase_name, cmd))

            elif (
                "workset" in cmd_str
                or "graph build-dfg" in cmd_str
                or "graphql build" in cmd_str
                or "terraform provision" in cmd_str
            ):
                data_prep_commands.append((phase_name, cmd))
            elif "terraform analyze" in cmd_str:
                track_b_commands.append((phase_name, cmd))
            elif "graph build" in cmd_str or "cfg" in cmd_str or "metadata" in cmd_str:
                data_prep_commands.append((phase_name, cmd))

            elif "taint" in cmd_str:
                track_a_commands.append((phase_name, cmd))

            elif (
                "lint" in cmd_str
                or "detect-patterns" in cmd_str
                or "graph analyze" in cmd_str
                or "graph viz" in cmd_str
                or "cdk" in cmd_str
                or "workflows" in cmd_str
                or (
                    "deps" in cmd_str
                    and "--vuln-scan" in cmd_str
                    and "--check-latest" not in cmd_str
                )
            ):
                track_b_commands.append((phase_name, cmd))

            elif ("deps" in cmd_str and "--check-latest" in cmd_str) or "docs" in cmd_str:
                if not offline:
                    track_c_commands.append((phase_name, cmd))

            elif "fce" in cmd_str or "session" in cmd_str or "learn" in cmd_str:
                final_commands.append((phase_name, cmd))
            else:
                final_commands.append((phase_name, cmd))

        def renumber_phases(phase_list: list, start_num: int) -> int:
            """Renumber phase descriptions starting from start_num. Returns next available number."""
            for i, (phase_name, cmd) in enumerate(phase_list):
                if ". " in phase_name:
                    desc = phase_name.split(". ", 1)[1]
                    phase_list[i] = (f"{start_num}. {desc}", cmd)
                start_num += 1
            return start_num

        phase_num = 1
        phase_num = renumber_phases(foundation_commands, phase_num)
        phase_num = renumber_phases(data_prep_commands, phase_num)

        track_phase_numbers: dict[str, int] = {}
        if track_a_commands:
            track_phase_numbers["Track A (Taint Analysis)"] = phase_num
            phase_num += 1
        if track_b_commands:
            track_phase_numbers["Track B (Static & Graph)"] = phase_num
            phase_num += 1
        if track_c_commands or (offline and not track_c_commands):
            track_phase_numbers["Track C (Network I/O)"] = phase_num
            phase_num += 1

        phase_num = renumber_phases(final_commands, phase_num)

        total_phases = (
            len(foundation_commands)
            + len(data_prep_commands)
            + len(track_a_commands)
            + len(track_b_commands)
            + len(track_c_commands)
            + len(final_commands)
        )

        if index_only:
            total_phases = len(foundation_commands) + len(data_prep_commands)
            renderer.on_log("")
            renderer.on_log(
                f"[bold]Index-Only Mode[/bold]  Running {total_phases} phases (Stage 1 + 2)"
            )
            renderer.on_log(
                "[dim]Skipping: Track A (taint), Track B (patterns, lint), Track C (network), Stage 4 (fce, report)[/dim]"
            )
            log_lines.append(f"\n[INDEX-ONLY MODE] Running {total_phases} phases (Stage 1 + 2)")
            log_lines.append(
                "  Skipping: Track A (taint), Track B (patterns, lint), Track C (network), Stage 4 (fce, report)"
            )

        renderer.on_stage_start("FOUNDATION - Sequential Execution", 1)
        log_lines.append("\n" + "=" * 60)
        log_lines.append("[STAGE 1] FOUNDATION - Sequential Execution")
        log_lines.append("=" * 60)

        for phase_name, cmd in foundation_commands:
            if is_stop_requested():
                renderer.on_log("[bold yellow]Pipeline interrupted by user[/bold yellow]")
                log_lines.append("[INTERRUPTED] Pipeline stopped by user")
                failed_phases += 1
                break

            current_phase += 1
            renderer.on_phase_start(phase_name, current_phase, total_phases)
            log_lines.append(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")
            start_time = time.time()

            if journal:
                try:
                    journal.phase_start(phase_name, " ".join(cmd), current_phase)
                except Exception as e:
                    renderer.on_log(
                        f"[yellow]Warning:[/yellow] Journal phase_start failed: {e}", is_error=True
                    )

            try:
                if "index" in " ".join(cmd):
                    renderer.on_log("[dim]Running in-process via indexer.runner[/dim]")
                    log_lines.append("[INDEX] Running in-process via indexer.runner")

                    from theauditor.indexer.runner import run_repository_index
                    from theauditor.utils.helpers import get_self_exclusion_patterns

                    exclude_patterns = None
                    if exclude_self:
                        exclude_patterns = get_self_exclusion_patterns(True)
                        renderer.on_log(
                            f"[dim]Excluding {len(exclude_patterns)} TheAuditor patterns[/dim]"
                        )
                        log_lines.append(
                            f"[INDEX] Excluding {len(exclude_patterns)} TheAuditor patterns"
                        )

                    try:
                        idx_result = await asyncio.to_thread(
                            run_repository_index,
                            root_path=root,
                            db_path=".pf/repo_index.db",
                            exclude_patterns=exclude_patterns,
                            print_stats=True,
                        )

                        stats = idx_result.get("stats", {})
                        counts = idx_result.get("extract_counts", {})
                        result = PhaseResult(
                            name=phase_name,
                            status=TaskStatus.SUCCESS,
                            elapsed=time.time() - start_time,
                            stdout=f"Indexed {stats.get('text_files', 0)} files, {counts.get('symbols', 0)} symbols\n",
                            stderr="",
                            exit_code=0,
                        )
                    except Exception as e:
                        import traceback

                        tb = traceback.format_exc()
                        result = PhaseResult(
                            name=phase_name,
                            status=TaskStatus.FAILED,
                            elapsed=time.time() - start_time,
                            stdout="",
                            stderr=f"[INDEX ERROR] {str(e)}\n{tb}\n",
                            exit_code=1,
                        )
                else:
                    cmd_timeout = get_command_timeout(cmd)
                    result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)
                    result = PhaseResult(
                        name=phase_name,
                        status=result.status,
                        elapsed=result.elapsed,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        exit_code=result.exit_code,
                    )

                elapsed = result.elapsed

                if journal:
                    try:
                        journal.phase_end(
                            phase_name,
                            success=result.success,
                            elapsed=elapsed,
                            exit_code=result.exit_code,
                        )
                    except Exception as e:
                        renderer.on_log(
                            f"[yellow]Warning:[/yellow] Journal phase_end failed: {e}",
                            is_error=True,
                        )

                if result.success:
                    renderer.on_phase_complete(phase_name, elapsed)
                    log_lines.append(f"[OK] {phase_name} completed in {elapsed:.1f}s")

                    for line in _format_phase_output(result.stdout, phase_name):
                        renderer.on_log(line)

                        log_lines.append(re.sub(r"\[/?[a-z ]+\]", "", line))
                else:
                    failed_phases += 1
                    failed_phase_names.append(phase_name)
                    renderer.on_phase_failed(phase_name, result.stderr, result.exit_code)
                    log_lines.append(f"[FAILED] {phase_name} failed (exit code {result.exit_code})")

                    try:
                        with open(error_log_path, "a", encoding="utf-8") as ef:
                            ef.write(
                                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [FAILED] {phase_name} (Exit: {result.exit_code})\n"
                            )
                            if result.stderr:
                                ef.write(result.stderr + "\n")
                            ef.write("-" * 40 + "\n")
                    except Exception:
                        pass

                    if result.stderr:
                        for error_line in _format_stderr_output(result.stderr):
                            renderer.on_log(error_line, is_error=True)
                            log_lines.append(error_line)

                    renderer.on_log(
                        "[bold red]Foundation stage failed - stopping pipeline[/bold red]",
                        is_error=True,
                    )
                    log_lines.append("[CRITICAL] Foundation stage failed - stopping pipeline")
                    break

            except Exception as e:
                failed_phases += 1
                renderer.on_log(f"[bold red]FAILED[/bold red]  {phase_name}: {e}", is_error=True)
                log_lines.append(f"[FAILED] {phase_name} failed: {e}")

                try:
                    with open(error_log_path, "a", encoding="utf-8") as ef:
                        ef.write(
                            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [EXCEPTION] {phase_name}: {e}\n"
                        )
                        ef.write("-" * 40 + "\n")
                except Exception:
                    pass

                break

        # After Stage 1, detect which IaC types exist and filter commands
        if failed_phases == 0:
            db_path = Path(root) / ".pf" / "repo_index.db"
            iac_presence = _detect_iac_presence(db_path)

            # Log what was detected
            detected_iac = [k for k, v in iac_presence.items() if v]
            if detected_iac:
                renderer.on_log(f"[dim]IaC detected: {', '.join(detected_iac)}[/dim]")
                log_lines.append(f"[INFO] IaC detected: {', '.join(detected_iac)}")

            # Filter data_prep_commands - remove terraform provision if no terraform
            if not iac_presence["terraform"]:
                original_count = len(data_prep_commands)
                data_prep_commands = [
                    (name, cmd)
                    for name, cmd in data_prep_commands
                    if "terraform" not in " ".join(cmd)
                ]
                if len(data_prep_commands) < original_count:
                    renderer.on_log("[dim]Skipping Terraform provision (no .tf files)[/dim]")
                    log_lines.append("[SKIP] Terraform provision - no .tf files indexed")

            # Filter track_b_commands - remove IaC-specific commands if no data
            original_track_b = len(track_b_commands)
            filtered_track_b = []
            for name, cmd in track_b_commands:
                cmd_str = " ".join(cmd)
                if "terraform" in cmd_str and not iac_presence["terraform"]:
                    renderer.on_log("[dim]Skipping Terraform analyze (no .tf files)[/dim]")
                    log_lines.append("[SKIP] Terraform analyze - no .tf files indexed")
                    continue
                if "cdk" in cmd_str and not iac_presence["cdk"]:
                    renderer.on_log("[dim]Skipping CDK analyze (no CDK constructs)[/dim]")
                    log_lines.append("[SKIP] CDK analyze - no CDK constructs indexed")
                    continue
                if "workflows" in cmd_str and not iac_presence["github_workflows"]:
                    renderer.on_log("[dim]Skipping GitHub workflows analyze (no workflows)[/dim]")
                    log_lines.append("[SKIP] GitHub workflows - no workflows indexed")
                    continue
                filtered_track_b.append((name, cmd))
            track_b_commands = filtered_track_b

        if failed_phases == 0 and data_prep_commands:
            renderer.on_stage_start("DATA PREPARATION - Sequential Execution", 2)
            renderer.on_log("Preparing data structures for parallel analysis...")
            log_lines.append("\n" + "=" * 60)
            log_lines.append("[STAGE 2] DATA PREPARATION - Sequential Execution")
            log_lines.append("=" * 60)
            log_lines.append("Preparing data structures for parallel analysis...")

            for phase_name, cmd in data_prep_commands:
                if is_stop_requested():
                    renderer.on_log("[bold yellow]Pipeline interrupted by user[/bold yellow]")
                    log_lines.append("[INTERRUPTED] Pipeline stopped by user")
                    failed_phases += 1
                    break

                current_phase += 1
                renderer.on_phase_start(phase_name, current_phase, total_phases)
                log_lines.append(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")
                start_time = time.time()

                if journal:
                    try:
                        journal.phase_start(phase_name, " ".join(cmd), current_phase)
                    except Exception as e:
                        renderer.on_log(
                            f"[yellow]Warning:[/yellow] Journal phase_start failed: {e}",
                            is_error=True,
                        )

                try:
                    cmd_timeout = get_command_timeout(cmd)
                    result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)
                    result = PhaseResult(
                        name=phase_name,
                        status=result.status,
                        elapsed=result.elapsed,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        exit_code=result.exit_code,
                    )

                    elapsed = result.elapsed

                    if journal:
                        try:
                            journal.phase_end(
                                phase_name,
                                success=result.success,
                                elapsed=elapsed,
                                exit_code=result.exit_code,
                            )
                        except Exception as e:
                            renderer.on_log(
                                f"[yellow]Warning:[/yellow] Journal phase_end failed: {e}",
                                is_error=True,
                            )

                    if result.success:
                        renderer.on_phase_complete(phase_name, elapsed)
                        log_lines.append(f"[OK] {phase_name} completed in {elapsed:.1f}s")

                        for line in _format_phase_output(result.stdout, phase_name):
                            renderer.on_log(line)
                            log_lines.append(re.sub(r"\[/?[a-z ]+\]", "", line))
                    else:
                        failed_phases += 1
                        failed_phase_names.append(phase_name)
                        renderer.on_phase_failed(phase_name, result.stderr, result.exit_code)
                        log_lines.append(
                            f"[FAILED] {phase_name} failed (exit code {result.exit_code})"
                        )

                        if result.stderr:
                            for error_line in _format_stderr_output(result.stderr):
                                renderer.on_log(error_line, is_error=True)
                                log_lines.append(error_line)

                        renderer.on_log(
                            "[bold red]Data preparation stage failed - stopping pipeline[/bold red]",
                            is_error=True,
                        )
                        log_lines.append(
                            "[CRITICAL] Data preparation stage failed - stopping pipeline"
                        )
                        break

                except Exception as e:
                    failed_phases += 1
                    failed_phase_names.append(phase_name)
                    renderer.on_log(
                        f"[bold red]FAILED[/bold red]  {phase_name}: {e}", is_error=True
                    )
                    log_lines.append(f"[FAILED] {phase_name} failed: {e}")

                    try:
                        with open(error_log_path, "a", encoding="utf-8") as ef:
                            ef.write(
                                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [EXCEPTION] {phase_name}: {e}\n"
                            )
                            ef.write("-" * 40 + "\n")
                    except Exception:
                        pass

                    break

        if (
            failed_phases == 0
            and not index_only
            and (track_a_commands or track_b_commands or track_c_commands)
        ):
            renderer.on_stage_start("HEAVY PARALLEL ANALYSIS - Optimized Execution", 3)
            renderer.on_log("Launching rebalanced parallel tracks:")
            if track_a_commands:
                renderer.on_log(
                    "  [dim]Track A:[/dim] Taint Analysis [dim](isolated heavy task)[/dim]"
                )
            if track_b_commands:
                renderer.on_log(
                    "  [dim]Track B:[/dim] Static Analysis & Offline Security [dim](lint, patterns, graph, vuln-scan)[/dim]"
                )
            if track_c_commands and not offline:
                renderer.on_log(
                    "  [dim]Track C:[/dim] Network I/O [dim](version checks, docs)[/dim]"
                )
            elif offline:
                renderer.on_log("  [dim]Track C: Skipped (offline mode)[/dim]")

            log_lines.append("\n" + "=" * 60)
            log_lines.append("[STAGE 3] HEAVY PARALLEL ANALYSIS - Optimized Execution")
            log_lines.append("=" * 60)
            log_lines.append("Launching rebalanced parallel tracks:")
            if track_a_commands:
                log_lines.append("  Track A: Taint Analysis (isolated heavy task)")
            if track_b_commands:
                log_lines.append(
                    "  Track B: Static Analysis & Offline Security (lint, patterns, graph, vuln-scan)"
                )
            if track_c_commands and not offline:
                log_lines.append("  Track C: Network I/O (version checks, docs)")
            elif offline:
                log_lines.append("  [OFFLINE MODE] Track C skipped")

            tasks = []
            track_names = []

            if track_a_commands:
                if not use_subprocess_for_taint:

                    def run_taint_sync() -> PhaseResult:
                        """Run taint analysis synchronously with live progress output."""
                        from theauditor.rules.orchestrator import RulesOrchestrator
                        from theauditor.taint import TaintRegistry, trace_taint
                        from theauditor.utils.memory import get_recommended_memory_limit

                        start_time = time.time()

                        logger.info("Track A: Starting taint analysis...")

                        memory_limit = get_recommended_memory_limit()
                        db_path = Path(root) / ".pf" / "repo_index.db"

                        logger.info("Track A: Initializing security analysis infrastructure...")
                        registry = TaintRegistry()
                        orchestrator = RulesOrchestrator(project_path=Path(root), db_path=db_path)
                        orchestrator.collect_rule_patterns(registry)

                        all_findings = []

                        logger.info("Track A: Running infrastructure and configuration analysis...")
                        infra_findings = orchestrator.run_standalone_rules()
                        all_findings.extend(infra_findings)
                        logger.info(f"Track A: Found {len(infra_findings)} infrastructure issues")

                        logger.info("Track A: Discovering framework-specific patterns...")
                        discovery_findings = orchestrator.run_discovery_rules(registry)
                        all_findings.extend(discovery_findings)

                        stats = registry.get_stats()
                        logger.info(
                            f"Track A: Registry has {stats['total_sinks']} sinks, {stats['total_sources']} sources"
                        )

                        logger.info("Track A: Performing data-flow taint analysis (IFDS)...")
                        graph_db_path = Path(root) / ".pf" / "graphs.db"
                        result = trace_taint(
                            db_path=str(db_path),
                            max_depth=25,
                            registry=registry,
                            use_memory_cache=True,
                            memory_limit_mb=memory_limit,
                            graph_db_path=str(graph_db_path),
                            mode="complete",
                        )

                        taint_paths = result.get("taint_paths", result.get("paths", []))

                        if result.get("mode") == "complete":
                            logger.info("Track A: COMPLETE MODE RESULTS:")
                            logger.info(
                                f"Track A:   IFDS (backward): {len(taint_paths)} vulnerable paths"
                            )
                            logger.info(
                                f"Track A:   FlowResolver (forward): {result.get('total_flows_resolved', 0)} total flows"
                            )
                        else:
                            logger.info(
                                f"Track A: Found {len(taint_paths)} taint flow vulnerabilities"
                            )

                        logger.info("Track A: Running advanced security analysis...")

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
                        logger.info(
                            f"Track A: Found {len(advanced_findings)} advanced security issues"
                        )

                        logger.info(
                            f"Track A: Total vulnerabilities: {len(all_findings) + len(taint_paths)}"
                        )

                        result["infrastructure_issues"] = infra_findings
                        result["discovery_findings"] = discovery_findings
                        result["advanced_findings"] = advanced_findings
                        result["all_rule_findings"] = all_findings
                        result["total_vulnerabilities"] = len(taint_paths) + len(all_findings)

                        if db_path.exists():
                            from theauditor.indexer.database import DatabaseManager

                            db_manager = DatabaseManager(str(db_path))
                            findings_dicts = []

                            for taint_path in result.get("taint_paths", []):
                                sink = taint_path.get("sink", {})
                                source = taint_path.get("source", {})
                                vuln_type = taint_path.get("vulnerability_type", "Unknown")
                                message = f"{vuln_type}: {source.get('name', 'unknown')} -> {sink.get('name', 'unknown')}"

                                findings_dicts.append(
                                    {
                                        "file": sink.get("file", ""),
                                        "line": int(sink.get("line", 0)),
                                        "column": sink.get("column"),
                                        "rule": f"taint-{sink.get('category', 'unknown')}",
                                        "tool": "taint",
                                        "message": message,
                                        "severity": "high",
                                        "category": "injection",
                                        "code_snippet": None,
                                        "additional_info": taint_path,
                                    }
                                )

                            for finding in all_findings:
                                findings_dicts.append(
                                    {
                                        "file": finding.get("file", ""),
                                        "line": int(finding.get("line", 0)),
                                        "rule": finding.get("rule", "unknown"),
                                        "tool": "taint",
                                        "message": finding.get("message", ""),
                                        "severity": finding.get("severity", "medium"),
                                        "category": finding.get("category", "security"),
                                    }
                                )

                            if findings_dicts:
                                db_manager.write_findings_batch(findings_dicts, tool_name="taint")
                                db_manager.close()
                                logger.info(
                                    f"Track A: Wrote {len(findings_dicts)} findings to database"
                                )

                        logger.info("Track A: Taint analysis complete")

                        output_lines = [
                            "Taint analysis completed",
                            f"  Infrastructure issues: {len(infra_findings)}",
                            f"  Framework patterns: {len(discovery_findings)}",
                            f"  Taint sources: {result.get('sources_found', 0)}",
                            f"  Security sinks: {result.get('sinks_found', 0)}",
                            f"  Taint paths (IFDS): {len(taint_paths)}",
                            f"  Advanced security issues: {len(advanced_findings)}",
                            f"  Total vulnerabilities: {len(all_findings) + len(taint_paths)}",
                        ]

                        elapsed = time.time() - start_time
                        return PhaseResult(
                            name="Track A (Taint Analysis)",
                            status=TaskStatus.SUCCESS,
                            elapsed=elapsed,
                            stdout="\n".join(output_lines),
                            stderr="",
                            exit_code=0,
                            findings_count=len(all_findings) + len(taint_paths),
                        )

                    async def run_taint_async() -> PhaseResult:
                        try:
                            return await asyncio.to_thread(run_taint_sync)
                        except Exception as e:
                            error_msg = f"Direct taint analysis failed: {str(e)}"
                            return PhaseResult(
                                name="Track A (Taint Analysis)",
                                status=TaskStatus.FAILED,
                                elapsed=0.0,
                                stdout="",
                                stderr=error_msg,
                                exit_code=1,
                            )

                    track_a_num = track_phase_numbers.get("Track A (Taint Analysis)", 0)
                    track_a_display = f"{track_a_num}. Track A (Taint Analysis)"
                    renderer.on_parallel_track_start(track_a_display)
                    tasks.append(run_taint_async())
                    track_names.append(track_a_display)
                    current_phase += 1
                else:
                    track_a_num = track_phase_numbers.get("Track A (Taint Analysis)", 0)
                    track_a_display = f"{track_a_num}. Track A (Taint Analysis)"
                    renderer.on_parallel_track_start(track_a_display)
                    tasks.append(run_chain_silent(track_a_commands, root, track_a_display))
                    track_names.append(track_a_display)
                    current_phase += 1

            if track_b_commands:
                track_b_num = track_phase_numbers.get("Track B (Static & Graph)", 0)
                track_b_display = f"{track_b_num}. Track B (Static & Graph)"
                renderer.on_parallel_track_start(track_b_display)
                tasks.append(run_chain_silent(track_b_commands, root, track_b_display))
                track_names.append(track_b_display)
                current_phase += 1

            if track_c_commands:
                track_c_num = track_phase_numbers.get("Track C (Network I/O)", 0)
                track_c_display = f"{track_c_num}. Track C (Network I/O)"
                renderer.on_parallel_track_start(track_c_display)
                tasks.append(run_chain_silent(track_c_commands, root, track_c_display))
                track_names.append(track_c_display)
                current_phase += 1

            log_lines.append("\n[SYNC] Launching parallel tracks with asyncio.gather()...")

            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

            track_summaries: list[dict] = []

            if offline and not track_c_commands:
                track_c_num = track_phase_numbers.get("Track C (Network I/O)", 0)
                track_summaries.append(
                    {
                        "name": f"{track_c_num}. Track C (Network I/O)",
                        "success": True,
                        "elapsed": 0.0,
                        "phases": [],
                        "findings": 0,
                        "skipped": True,
                        "skip_reason": "offline mode",
                    }
                )

            for i, result in enumerate(parallel_results):
                track_name = track_names[i] if i < len(track_names) else f"Track {i}"
                summary: dict = {
                    "name": track_name,
                    "success": True,
                    "elapsed": 0.0,
                    "phases": [],
                    "findings": 0,
                }

                if isinstance(result, Exception):
                    log_lines.append(f"[ERROR] {track_name} failed with exception: {result}")
                    summary["success"] = False
                    summary["error"] = str(result)
                    failed_phases += 1

                    try:
                        with open(error_log_path, "a", encoding="utf-8") as ef:
                            ef.write(
                                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] {track_name} exception: {result}\n"
                            )
                    except Exception:
                        pass

                elif isinstance(result, list):
                    total_elapsed = sum(r.elapsed for r in result)
                    all_success = all(r.success for r in result)
                    summary["elapsed"] = total_elapsed
                    summary["success"] = all_success
                    aggregated_stderr: list[str] = []

                    for phase_result in result:
                        phase_info = {
                            "name": phase_result.name,
                            "success": phase_result.success,
                            "elapsed": phase_result.elapsed,
                            "findings": 0,
                            "stderr": phase_result.stderr if not phase_result.success else "",
                        }

                        if phase_result.stdout:
                            stdout_lower = phase_result.stdout.lower()

                            patterns = [
                                r"total findings[:\s]*(\d+)",
                                r"found\s+(\d+)\s+(?:issue|finding|vulnerabilit|security)",
                                r"(\d+)\s+(?:issue|finding|vulnerabilit|security)",
                                r"wrote\s+(\d+)\s+findings",
                                r"critical[:\s]*(\d+)",
                                r"high[:\s]*(\d+)",
                            ]
                            for pattern in patterns:
                                findings_match = re.search(pattern, stdout_lower)
                                if findings_match:
                                    count = int(findings_match.group(1))
                                    if count > phase_info["findings"]:
                                        phase_info["findings"] = count
                            summary["findings"] += phase_info["findings"]

                        summary["phases"].append(phase_info)
                        log_lines.append(
                            f"{'[OK]' if phase_result.success else '[FAILED]'} {phase_result.name} ({phase_result.elapsed:.1f}s)"
                        )

                        # Log stderr immediately for failed subphases
                        if not phase_result.success and phase_result.stderr:
                            short_name = (
                                phase_result.name.split(". ", 1)[-1]
                                if ". " in phase_result.name
                                else phase_result.name
                            )
                            renderer.on_log(f"  [red]{short_name} error:[/red]")
                            for error_line in _format_stderr_output(phase_result.stderr):
                                renderer.on_log(error_line, is_error=True)
                                log_lines.append(error_line)
                            aggregated_stderr.append(f"[{short_name}] {phase_result.stderr}")

                        short_name = (
                            phase_result.name.split(". ", 1)[-1]
                            if ". " in phase_result.name
                            else phase_result.name
                        )
                        subphase_display = f"    - {short_name}"
                        renderer._phases[subphase_display] = {
                            "status": "success" if phase_result.success else "FAILED",
                            "elapsed": phase_result.elapsed,
                        }

                    # Store aggregated stderr for summary display
                    if aggregated_stderr:
                        summary["stderr"] = "\n".join(aggregated_stderr)

                    if not all_success:
                        failed_phases += 1

                elif isinstance(result, PhaseResult):
                    summary["elapsed"] = result.elapsed
                    summary["success"] = result.success
                    summary["findings"] = result.findings_count
                    summary["stdout"] = result.stdout
                    summary["stderr"] = result.stderr if not result.success else ""

                    log_lines.append(
                        f"{'[OK]' if result.success else '[FAILED]'} {result.name} ({result.elapsed:.1f}s)"
                    )

                    if not result.success:
                        failed_phases += 1

                track_summaries.append(summary)
                renderer.on_parallel_track_complete(track_name, summary["elapsed"])

            renderer.on_log("")
            renderer.on_log("[bold magenta]Stage 3[/bold magenta]  [bold cyan]Results[/bold cyan]")
            for summary in track_summaries:
                track_name = summary["name"]
                elapsed = summary["elapsed"]
                findings = summary["findings"]

                if summary["success"]:
                    status = "[green]OK[/green]"
                else:
                    status = "[bold red]FAILED[/bold red]"

                if summary.get("skipped"):
                    renderer.on_log(
                        f"[dim]SKIP[/dim]  {track_name}  [dim]({summary.get('skip_reason', 'skipped')})[/dim]"
                    )
                    continue

                findings_str = (
                    f"  [dim]([cyan]{findings}[/cyan] findings)[/dim]" if findings > 0 else ""
                )
                renderer.on_log(f"{status}  {track_name}  [dim]{elapsed:.1f}s[/dim]{findings_str}")

                if summary["phases"]:
                    for phase in summary["phases"]:
                        phase_status = (
                            "[green]OK[/green]" if phase["success"] else "[red]FAIL[/red]"
                        )
                        phase_findings = (
                            f" ([cyan]{phase['findings']}[/cyan])" if phase["findings"] > 0 else ""
                        )

                        short_name = (
                            phase["name"].split(". ", 1)[-1]
                            if ". " in phase["name"]
                            else phase["name"]
                        )
                        renderer.on_log(
                            f"    {phase_status}  {short_name}  [dim]{phase['elapsed']:.1f}s[/dim]{phase_findings}"
                        )

                elif summary.get("stdout"):
                    for line in summary["stdout"].strip().split("\n"):
                        text = line.strip()
                        if not text:
                            continue

                        if ":" in text:
                            label, value = text.split(":", 1)

                            colored_value = re.sub(r"(\d+)", r"[cyan]\1[/cyan]", value)
                            renderer.on_log(f"    [dim]{label}:[/dim]{colored_value}")
                        else:
                            renderer.on_log(f"    [dim]{text}[/dim]")

                if not summary["success"] and summary.get("stderr"):
                    error_preview = summary["stderr"][:150]
                    if len(summary["stderr"]) > 150:
                        error_preview += "..."
                    renderer.on_log(f"    [red]Error: {error_preview}[/red]")

        if failed_phases == 0 and not index_only and final_commands:
            renderer.on_stage_start("FINAL AGGREGATION - AsyncIO Sequential Execution", 4)
            log_lines.append("\n" + "=" * 60)
            log_lines.append("[STAGE 4] FINAL AGGREGATION - AsyncIO Sequential Execution")
            log_lines.append("=" * 60)

            for phase_name, cmd in final_commands:
                if is_stop_requested():
                    renderer.on_log("[bold yellow]Pipeline interrupted by user[/bold yellow]")
                    log_lines.append("[INTERRUPTED] Pipeline stopped by user")
                    failed_phases += 1
                    break

                current_phase += 1
                renderer.on_phase_start(phase_name, current_phase, total_phases)
                log_lines.append(f"\n[Phase {current_phase}/{total_phases}] {phase_name}")

                if journal:
                    try:
                        journal.phase_start(phase_name, " ".join(cmd), current_phase)
                    except Exception as e:
                        renderer.on_log(
                            f"[yellow]Warning:[/yellow] Journal phase_start failed: {e}",
                            is_error=True,
                        )

                cmd_timeout = get_command_timeout(cmd)
                result = await run_command_async(cmd, cwd=root, timeout=cmd_timeout)

                is_fce = "factual correlation" in phase_name.lower() or "fce" in " ".join(cmd)
                if is_fce:
                    fce_log_path = Path(root) / ".pf" / "fce.log"
                    renderer.on_log(f"[dim]Writing FCE output to[/dim] [cyan]{fce_log_path}[/cyan]")
                    log_lines.append(f"[INFO] Writing FCE output to: {fce_log_path}")

                    with open(fce_log_path, "w", encoding="utf-8") as fce_log:
                        fce_log.write(f"FCE Execution Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        fce_log.write("=" * 80 + "\n")
                        fce_log.write(result.stdout)
                        if result.stderr:
                            fce_log.write("\n--- STDERR ---\n")
                            fce_log.write(result.stderr)

                    result = PhaseResult(
                        name=result.name,
                        status=result.status,
                        elapsed=result.elapsed,
                        stdout="FCE output written to [cyan].pf/fce.log[/cyan]",
                        stderr=result.stderr,
                        exit_code=result.exit_code,
                    )

                cmd_str = " ".join(str(c) for c in cmd)
                is_findings_command = (
                    "taint" in cmd_str
                    or ("deps" in cmd_str and "--vuln-scan" in cmd_str)
                    or "cdk" in cmd_str
                    or "terraform" in cmd_str
                    or "workflows" in cmd_str
                )

                if is_findings_command:
                    success = result.exit_code in [0, 1, 2]
                else:
                    success = result.exit_code == 0

                elapsed = result.elapsed

                if journal:
                    try:
                        journal.phase_end(
                            phase_name, success=success, elapsed=elapsed, exit_code=result.exit_code
                        )
                    except Exception as e:
                        renderer.on_log(
                            f"[yellow]Warning:[/yellow] Journal phase_end failed: {e}",
                            is_error=True,
                        )

                if success:
                    if result.exit_code == 2 and is_findings_command:
                        ok_msg = (
                            f"[OK] {phase_name} completed in {elapsed:.1f}s - CRITICAL findings"
                        )
                    elif result.exit_code == 1 and is_findings_command:
                        ok_msg = f"[OK] {phase_name} completed in {elapsed:.1f}s - HIGH findings"
                    else:
                        ok_msg = f"[OK] {phase_name} completed in {elapsed:.1f}s"

                    renderer.on_phase_complete(phase_name, elapsed)
                    log_lines.append(ok_msg)

                    for line in _format_phase_output(result.stdout, phase_name):
                        renderer.on_log(line)
                        log_lines.append(re.sub(r"\[/?[a-z ]+\]", "", line))
                else:
                    failed_phases += 1
                    failed_phase_names.append(phase_name)
                    renderer.on_phase_failed(phase_name, result.stderr, result.exit_code)
                    log_lines.append(f"[FAILED] {phase_name} failed (exit code {result.exit_code})")

                    try:
                        with open(error_log_path, "a", encoding="utf-8") as ef:
                            ef.write(
                                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [FAILED] {phase_name} (Exit: {result.exit_code})\n"
                            )
                            if result.stderr:
                                ef.write(result.stderr + "\n")
                            ef.write("-" * 40 + "\n")
                    except Exception:
                        pass

                    if result.stderr:
                        for error_line in _format_stderr_output(result.stderr):
                            renderer.on_log(error_line, is_error=True)
                            log_lines.append(error_line)

        pipeline_elapsed = time.time() - pipeline_start
        all_created_files = collect_created_files()

        pf_dir = Path(root) / ".pf"
        allfiles_path = pf_dir / "allfiles.md"
        with open(allfiles_path, "w", encoding="utf-8") as f:
            f.write("# All Files Created by `aud full` Command\n\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total files: {len(all_created_files)}\n\n")

            files_by_dir = {}
            for file_path in all_created_files:
                dir_name = str(Path(file_path).parent)
                if dir_name not in files_by_dir:
                    files_by_dir[dir_name] = []
                files_by_dir[dir_name].append(file_path)

            for dir_name in sorted(files_by_dir.keys()):
                f.write(f"\n## {dir_name}/\n\n")
                for file_path in sorted(files_by_dir[dir_name]):
                    file_size = 0
                    if Path(file_path).exists():
                        file_size = Path(file_path).stat().st_size
                    f.write(f"- `{Path(file_path).name}` ({file_size:,} bytes)\n")

            f.write("\n---\n")
            f.write(
                f"Total execution time: {pipeline_elapsed:.1f} seconds ({pipeline_elapsed / 60:.1f} minutes)\n"
            )
            f.write(f"Commands executed: {total_phases}\n")
            f.write(f"Failed commands: {failed_phases}\n")

        all_created_files.append(str(allfiles_path))
        all_created_files.append(str(log_file_path))

        status_dir = Path(root) / ".pf" / "status"
        if status_dir.exists():
            try:
                for status_file in status_dir.glob("*.status"):
                    status_file.unlink()

                if not list(status_dir.iterdir()):
                    status_dir.rmdir()
            except Exception as e:
                renderer.on_log(
                    f"[yellow]Warning:[/yellow] Could not clean status files: {e}", is_error=True
                )

        findings_data = _get_findings_from_db(Path(root))
        critical_findings = findings_data["critical"]
        high_findings = findings_data["high"]
        medium_findings = findings_data["medium"]
        low_findings = findings_data["low"]
        total_vulnerabilities = findings_data["total_vulnerabilities"]

        if journal:
            try:
                journal.pipeline_summary(
                    total_phases=total_phases,
                    failed_phases=failed_phases,
                    total_files=len(all_created_files),
                    total_findings=total_vulnerabilities,
                    elapsed=pipeline_elapsed,
                    status="complete" if failed_phases == 0 else "partial",
                )
                journal.close()
                renderer.on_log("[dim]Journal closed (persistent in .pf/ml/)[/dim]")
            except Exception as e:
                renderer.on_log(
                    f"[yellow]Warning:[/yellow] Journal close failed: {e}", is_error=True
                )

        return {
            "success": failed_phases == 0 and phases_with_warnings == 0,
            "failed_phases": failed_phases,
            "failed_phase_names": failed_phase_names,
            "phases_with_warnings": phases_with_warnings,
            "total_phases": total_phases,
            "elapsed_time": pipeline_elapsed,
            "created_files": all_created_files,
            "log_lines": log_lines,
            "log_file_path": str(log_file_path),
            "index_only": index_only,
            "findings": {
                "critical": critical_findings,
                "high": high_findings,
                "medium": medium_findings,
                "low": low_findings,
                "total_vulnerabilities": total_vulnerabilities,
                "by_tool": findings_data.get("by_tool", {}),
            },
        }

    finally:
        renderer.stop()
