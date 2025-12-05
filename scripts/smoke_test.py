#!/usr/bin/env python
"""TheAuditor Smoke Test - Professional Grade CLI Health Check.

This script:
1. DYNAMICALLY discovers ALL commands via Click introspection (no stale lists)
2. Tests --help for every command (catches import errors)
3. Runs minimal invocations for safe commands (catches runtime crashes)
4. Captures structured logs via THEAUDITOR_LOG_FILE for each command
5. Generates an LLM-readable failure report

Usage:
    cd C:/Users/santa/Desktop/TheAuditor
    .venv/Scripts/python.exe scripts/smoke_test.py

    # Options:
    .venv/Scripts/python.exe scripts/smoke_test.py --help-only    # Skip invocations
    .venv/Scripts/python.exe scripts/smoke_test.py --verbose      # Show all output
    .venv/Scripts/python.exe scripts/smoke_test.py --clean        # Cleanup logs after
"""

import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# ANSI colors for terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False
    console = None


@dataclass
class TestResult:
    """Result of a single command test."""
    command: str
    phase: str  # "help" or "invoke"
    success: bool
    exit_code: int | str
    duration: float
    stdout: str = ""
    stderr: str = ""
    log_content: str = ""  # Content from THEAUDITOR_LOG_FILE
    error_summary: str = ""


@dataclass
class SmokeTestReport:
    """Aggregated smoke test results."""
    results: list[TestResult] = field(default_factory=list)
    total_time: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def failures(self) -> list[TestResult]:
        return [r for r in self.results if not r.success]


# =============================================================================
# DYNAMIC COMMAND DISCOVERY
# =============================================================================

def discover_all_commands() -> list[str]:
    """Dynamically find ALL registered commands via Click introspection.

    This prevents the test from becoming stale when new commands are added.
    """
    try:
        from theauditor.cli import cli
        import click

        ctx = click.Context(cli)
        commands = ["aud --help"]  # Always test root

        def recurse(group, parent_name: str, depth: int = 0):
            """Recursively discover commands and subcommands."""
            if depth > 3:  # Prevent infinite recursion
                return

            try:
                cmd_names = group.list_commands(ctx)
            except Exception:
                return

            for name in cmd_names:
                full_name = f"{parent_name} {name}"
                commands.append(f"{full_name} --help")

                try:
                    sub = group.get_command(ctx, name)
                    # Check if it's a group (has subcommands)
                    if hasattr(sub, "list_commands"):
                        recurse(sub, full_name, depth + 1)
                except Exception:
                    pass  # Some commands may fail to load - that's what we're testing

        recurse(cli, "aud")
        return sorted(set(commands))  # Dedupe and sort

    except Exception as e:
        print(f"[WARNING] Dynamic discovery failed: {e}")
        print("[WARNING] Falling back to hardcoded command list")
        return FALLBACK_COMMANDS


# Fallback if dynamic discovery fails (shouldn't happen, but safety net)
FALLBACK_COMMANDS = [
    "aud --help",
    "aud full --help",
    "aud setup-ai --help",
    "aud tools --help",
    "aud workset --help",
    "aud manual --help",
    "aud detect-patterns --help",
    "aud taint --help",
    "aud graph --help",
    "aud session --help",
    "aud learn --help",
    "aud suggest --help",
    "aud explain --help",
    "aud blueprint --help",
]


# 10 minute timeout for ALL commands - no arbitrary limits
DEFAULT_TIMEOUT = 600

# Commands for real minimal invocation - test EVERYTHING except setup-ai, full, detect-patterns
INVOCATION_TESTS = [
    # UTILITIES
    ("aud manual --list", "List manual topics"),
    ("aud tools", "Show tool versions"),
    ("aud tools list", "List all tools"),
    ("aud planning list", "List plans"),

    # DATABASE READERS
    ("aud blueprint --structure", "Show codebase structure"),
    ("aud detect-frameworks", "Show detected frameworks"),
    ("aud deadcode --format summary", "Dead code summary"),
    ("aud boundaries", "Security boundaries"),
    ("aud query --symbol main", "Query symbol"),
    ("aud explain theauditor/cli.py", "Explain file context"),

    # GRAPH COMMANDS
    ("aud graph analyze", "Analyze dependency graph"),
    ("aud graph query --uses theauditor.cli", "Query graph relationships"),
    ("aud graph build", "Build/rebuild graphs.db"),
    ("aud graph build-dfg", "Build DFG in graphs.db"),
    ("aud graph viz", "Graph viz DOT output"),

    # ML COMMANDS
    ("aud suggest --print-plan", "ML suggestions"),
    ("aud learn", "Train ML models"),

    # SESSION COMMANDS
    ("aud session list", "List Claude sessions"),
    ("aud session activity --limit 5", "Session activity"),
    ("aud session analyze", "Analyze sessions"),
    ("aud session report", "Session report"),

    # TAINT & PATTERNS
    ("aud taint", "Taint analysis"),
    ("aud fce", "FCE analysis"),

    # LINTING & DEPS
    ("aud lint", "Run linters"),
    ("aud deps", "Dependency analysis"),
    ("aud deps --offline", "Deps offline mode"),

    # DOCS & METADATA
    ("aud docs", "Generate docs"),
    ("aud metadata", "Git metadata"),

    # WORKSET COMMANDS
    ("aud workset show", "Show workset"),
    ("aud workset list", "List workset files"),

    # CFG (Control Flow Graph)
    ("aud cfg theauditor/cli.py", "CFG for cli.py"),
    ("aud cfg analyze theauditor/cli.py", "CFG analyze cli.py"),

    # IMPACT ANALYSIS
    ("aud impact theauditor/cli.py", "Impact analysis cli.py"),

    # REFACTOR
    ("aud refactor extract theauditor/cli.py --function main", "Refactor extract"),

    # DOCKER & GRAPHQL
    ("aud docker-analyze", "Docker analysis"),
    ("aud graphql", "GraphQL analysis"),

    # WORKFLOWS
    ("aud workflows analyze", "Analyze workflows"),
]


# Commands to SKIP (and why) - ONLY THESE THREE
SKIP_REASONS = {
    "aud full": "Heavy pipeline - runs 20+ phases, too slow for smoke test",
    "aud setup-ai": "Installs packages and creates venv - modifies environment",
    "aud detect-patterns": "Long running analysis (30+ seconds)",
}

# Commands that exit non-zero when they find issues (intentional CI behavior)
# These are NOT failures - they ran successfully and reported findings
EXPECTED_NONZERO_COMMANDS = {
    "aud boundaries",  # Exits 1 when input validation issues found
    "aud lint",        # Exits non-zero when lint errors found
    "aud suggest",     # May exit non-zero on model mismatch
}


# =============================================================================
# TEST EXECUTION
# =============================================================================

LOG_DIR = Path("logs/smoke_test")


def run_command(cmd: str, timeout: int = DEFAULT_TIMEOUT, cwd: Path | None = None) -> TestResult:
    """Run a command with isolated environment and log capture."""
    start = time.time()
    phase = "help" if "--help" in cmd else "invoke"

    # Generate unique log file for this command
    run_id = str(uuid.uuid4())[:8]
    safe_cmd_name = cmd.replace(" ", "_").replace("/", "_").replace("\\", "_")[:50]
    log_file = LOG_DIR / f"{safe_cmd_name}_{run_id}.log"
    log_file.parent.mkdir(exist_ok=True, parents=True)

    # Force consistent environment for maximum debuggability
    env = os.environ.copy()
    env["THEAUDITOR_LOG_JSON"] = "1"  # Force structured JSON logs
    env["THEAUDITOR_LOG_LEVEL"] = "DEBUG"  # Maximum verbosity on crash
    env["THEAUDITOR_LOG_FILE"] = str(log_file.resolve())
    env["PYTHONIOENCODING"] = "utf-8"  # Force UTF-8 for subprocess

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or Path.cwd(),
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.time() - start

        # Check if this command is expected to exit non-zero on findings
        is_expected_nonzero = any(cmd.startswith(ec) for ec in EXPECTED_NONZERO_COMMANDS)

        # Success if exit 0, OR if expected non-zero and produced stdout (ran successfully)
        if result.returncode == 0:
            success = True
        elif is_expected_nonzero and result.stdout and "error" not in result.stderr.lower():
            # Command ran and produced output - findings are expected, not errors
            success = True
        else:
            success = False

        error_summary = ""
        log_content = ""

        # Read log file if it exists (even on success, useful for debugging)
        if log_file.exists():
            try:
                log_content = log_file.read_text(encoding="utf-8", errors="replace")
                # Keep only last 2000 chars to avoid bloat
                if len(log_content) > 2000:
                    log_content = "...[truncated]...\n" + log_content[-2000:]
            except Exception:
                pass

        if not success:
            # Extract meaningful error from stderr
            stderr_lines = result.stderr.strip().split("\n")
            for line in reversed(stderr_lines):
                line_lower = line.lower()
                if any(x in line_lower for x in ["error:", "exception:", "traceback", "failed"]):
                    error_summary = line.strip()[:200]
                    break
            if not error_summary and stderr_lines:
                error_summary = stderr_lines[-1][:200]

            # If stderr is empty but we have log content, extract from there
            if not error_summary and log_content:
                for line in reversed(log_content.split("\n")):
                    if "ERROR" in line or "exception" in line.lower():
                        error_summary = line.strip()[:200]
                        break

        return TestResult(
            command=cmd,
            phase=phase,
            success=success,
            exit_code=result.returncode,
            duration=duration,
            stdout=result.stdout[:5000] if result.stdout else "",
            stderr=result.stderr[:5000] if result.stderr else "",
            log_content=log_content,
            error_summary=error_summary,
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            command=cmd,
            phase=phase,
            success=False,
            exit_code="TIMEOUT",
            duration=timeout,
            error_summary=f"Command timed out after {timeout}s",
        )
    except Exception as e:
        return TestResult(
            command=cmd,
            phase=phase,
            success=False,
            exit_code="EXCEPTION",
            duration=time.time() - start,
            error_summary=str(e)[:200],
        )


def print_progress(msg: str, status: str = "..."):
    """Print progress indicator."""
    if USE_RICH:
        style = "green" if status == "OK" else "red" if status == "FAIL" else "yellow"
        console.print(f"  [{style}]{status:4}[/{style}] {msg}")
    else:
        print(f"  [{status:4}] {msg}")


def run_smoke_tests(help_only: bool = False, verbose: bool = False) -> SmokeTestReport:
    """Run all smoke tests and return report."""
    report = SmokeTestReport()
    start_time = time.time()

    project_root = Path(__file__).parent.parent

    # Phase 1: Dynamically discover and test --help for all commands
    if USE_RICH:
        console.print("\n[bold cyan]PHASE 1:[/bold cyan] Discovering commands and testing --help...")
    else:
        print("\nPHASE 1: Discovering commands and testing --help...")

    all_commands = discover_all_commands()

    if USE_RICH:
        console.print(f"  [dim]Discovered {len(all_commands)} commands[/dim]")
    else:
        print(f"  Discovered {len(all_commands)} commands")

    for cmd in all_commands:
        result = run_command(cmd, timeout=DEFAULT_TIMEOUT, cwd=project_root)
        report.results.append(result)

        status = "OK" if result.success else "FAIL"
        if verbose or not result.success:
            print_progress(cmd, status)
            if not result.success and result.error_summary:
                print(f"         -> {result.error_summary}")

    help_passed = sum(1 for r in report.results if r.phase == "help" and r.success)
    help_total = sum(1 for r in report.results if r.phase == "help")

    if USE_RICH:
        console.print(f"  [dim]Help tests: {help_passed}/{help_total} passed[/dim]")
    else:
        print(f"  Help tests: {help_passed}/{help_total} passed")

    # Phase 2: Real invocations (if not help_only)
    if not help_only:
        if USE_RICH:
            console.print("\n[bold cyan]PHASE 2:[/bold cyan] Testing minimal invocations...")
        else:
            print("\nPHASE 2: Testing minimal invocations...")

        for cmd, description in INVOCATION_TESTS:
            result = run_command(cmd, timeout=DEFAULT_TIMEOUT, cwd=project_root)
            report.results.append(result)

            status = "OK" if result.success else "FAIL"
            print_progress(f"{description} ({cmd})", status)

            if not result.success:
                if result.error_summary:
                    print(f"         -> {result.error_summary}")
                if verbose and result.stderr:
                    # Show last 300 chars of stderr
                    print(f"         stderr: ...{result.stderr[-300:]}")

    report.total_time = time.time() - start_time
    return report


def generate_report(report: SmokeTestReport, output_path: Path | None = None) -> str:
    """Generate markdown failure report optimized for LLM consumption."""
    lines = [
        "# TheAuditor Smoke Test Report",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Tests:** {len(report.results)}",
        f"**Passed:** {report.passed}",
        f"**Failed:** {report.failed}",
        f"**Duration:** {report.total_time:.1f}s",
        "",
    ]

    if report.failed == 0:
        lines.extend([
            "## Result: ALL TESTS PASSED",
            "",
            "No runtime errors detected across the CLI surface.",
            "",
            "All commands loaded successfully and executed without crashes.",
        ])
    else:
        lines.extend([
            "## FAILURES DETECTED",
            "",
            "The following commands crashed or exited with non-zero codes.",
            "",
            "**Instructions for fixing:** Each failure below includes:",
            "- The exact command that failed",
            "- Exit code and duration",
            "- Error summary extracted from stderr/logs",
            "- Full stderr output (truncated)",
            "- Internal log content from THEAUDITOR_LOG_FILE",
            "",
        ])

        for i, fail in enumerate(report.failures, 1):
            lines.extend([
                f"### Failure {i}: `{fail.command}`",
                "",
                f"- **Phase:** {fail.phase}",
                f"- **Exit Code:** {fail.exit_code}",
                f"- **Duration:** {fail.duration:.2f}s",
                "",
            ])

            if fail.error_summary:
                lines.extend([
                    "**Error Summary:**",
                    "```",
                    fail.error_summary,
                    "```",
                    "",
                ])

            if fail.stderr:
                lines.extend([
                    "**Stderr (last 1500 chars):**",
                    "```python",
                    fail.stderr[-1500:],
                    "```",
                    "",
                ])

            if fail.log_content:
                lines.extend([
                    "**Internal Logs (THEAUDITOR_LOG_FILE):**",
                    "```json",
                    fail.log_content[-1000:],
                    "```",
                    "",
                ])

            lines.append("---")
            lines.append("")

    # Command coverage summary
    help_cmds = [r for r in report.results if r.phase == "help"]
    invoke_cmds = [r for r in report.results if r.phase == "invoke"]

    lines.extend([
        "",
        "## Test Coverage Summary",
        "",
        f"| Phase | Total | Passed | Failed |",
        f"|-------|-------|--------|--------|",
        f"| Help (--help) | {len(help_cmds)} | {sum(1 for r in help_cmds if r.success)} | {sum(1 for r in help_cmds if not r.success)} |",
        f"| Invocation | {len(invoke_cmds)} | {sum(1 for r in invoke_cmds if r.success)} | {sum(1 for r in invoke_cmds if not r.success)} |",
        "",
    ])

    # Skipped commands for reference
    lines.extend([
        "",
        "## Skipped Commands (By Design)",
        "",
        "These commands were not tested with real invocations:",
        "",
    ])
    for cmd, reason in sorted(SKIP_REASONS.items()):
        lines.append(f"- `{cmd}`: {reason}")

    content = "\n".join(lines)

    if output_path:
        output_path.write_text(content, encoding="utf-8")

    return content


def cleanup_logs():
    """Remove smoke test log files."""
    if LOG_DIR.exists():
        import shutil
        shutil.rmtree(LOG_DIR)
        print(f"Cleaned up {LOG_DIR}")


def print_summary(report: SmokeTestReport):
    """Print final summary."""
    if USE_RICH:
        if report.failed == 0:
            panel = Panel(
                f"[bold green]ALL {report.passed} TESTS PASSED[/bold green]\n"
                f"[dim]Duration: {report.total_time:.1f}s[/dim]",
                title="[bold]Smoke Test Complete[/bold]",
                border_style="green",
            )
        else:
            panel = Panel(
                f"[bold red]{report.failed} FAILURES[/bold red] / {report.passed} passed\n"
                f"[dim]Duration: {report.total_time:.1f}s[/dim]\n\n"
                f"[yellow]See execution_report.md for details[/yellow]",
                title="[bold]Smoke Test Complete[/bold]",
                border_style="red",
            )
        console.print()
        console.print(panel)
    else:
        print()
        if report.failed == 0:
            print(f"=== ALL {report.passed} TESTS PASSED ({report.total_time:.1f}s) ===")
        else:
            print(f"=== {report.failed} FAILURES / {report.passed} passed ({report.total_time:.1f}s) ===")
            print("See execution_report.md for details")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TheAuditor CLI Smoke Test")
    parser.add_argument("--help-only", action="store_true",
                        help="Only test --help commands, skip real invocations")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show all command output, not just failures")
    parser.add_argument("--output", "-o", type=Path, default=Path("execution_report.md"),
                        help="Output path for failure report (default: execution_report.md)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean up log files after test")
    args = parser.parse_args()

    if USE_RICH:
        console.print(Panel(
            "[bold]TheAuditor CLI Smoke Test[/bold]\n"
            "[dim]Professional-grade runtime health check[/dim]\n"
            "[dim]Dynamic discovery + isolated environment + log capture[/dim]",
            border_style="blue",
        ))
    else:
        print("=" * 60)
        print("TheAuditor CLI Smoke Test")
        print("Professional-grade runtime health check")
        print("=" * 60)

    # Run tests
    report = run_smoke_tests(help_only=args.help_only, verbose=args.verbose)

    # Generate report
    report_content = generate_report(report, args.output)

    # Print summary
    print_summary(report)

    if report.failed > 0:
        print(f"\nReport saved to: {args.output}")
        print(f"Log files in: {LOG_DIR}")

    # Cleanup if requested
    if args.clean:
        cleanup_logs()

    # Exit with failure count (capped at 125 for shell compatibility)
    sys.exit(min(report.failed, 125))


if __name__ == "__main__":
    main()
