#!/usr/bin/env python
"""TheAuditor Pre-Flight Check - Complete Systems Verification.

This is THE ONE test. No gloves. Tests everything including setup, indexing,
and all commands with correct syntax.

Phases:
  1. ENVIRONMENT - Python version, dependencies, paths
  2. SETUP - Build JS extractor if missing
  3. INDEX - Run aud full --index --offline to populate database
  4. COMMANDS - Test every single command with correct invocation

Usage:
    cd C:/Users/santa/Desktop/TheAuditor
    .venv/Scripts/python.exe scripts/smoke_test.py

    # Options:
    --skip-index     Skip the aud full indexing phase (use existing .pf/)
    --skip-setup     Skip environment setup checks
    --verbose        Show all output including stdout
    --timeout N      Override default timeout (default: 300s for commands)
"""

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False
    console = None


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    command: str
    phase: str
    success: bool
    exit_code: int | str
    duration: float
    stdout: str = ""
    stderr: str = ""
    error_summary: str = ""


@dataclass
class PreFlightReport:
    """Complete pre-flight check report."""
    results: list[TestResult] = field(default_factory=list)
    total_time: float = 0.0
    index_time: float = 0.0
    setup_time: float = 0.0

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
# PROJECT CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
PF_DIR = PROJECT_ROOT / ".pf"
JS_EXTRACTOR = PROJECT_ROOT / "theauditor" / "ast_extractors" / "javascript"
JS_BUNDLE = JS_EXTRACTOR / "dist" / "extractor.cjs"

# Default timeouts
SETUP_TIMEOUT = 120      # 2 min for npm install/build
INDEX_TIMEOUT = 600      # 10 min for aud full --index
COMMAND_TIMEOUT = 300    # 5 min per command (taint can be slow)
HELP_TIMEOUT = 30        # 30s for --help commands


# =============================================================================
# COMMAND DEFINITIONS - ALL COMMANDS WITH CORRECT SYNTAX
# =============================================================================

# Phase 1: Help tests for ALL commands (catches import errors)
HELP_TESTS = [
    "aud --help",
    "aud full --help",
    "aud setup-ai --help",
    "aud tools --help",
    "aud workset --help",
    "aud manual --help",
    "aud detect-patterns --help",
    "aud detect-frameworks --help",
    "aud taint --help",
    "aud boundaries --help",
    "aud graph --help",
    "aud graph build --help",
    "aud graph build-dfg --help",
    "aud graph analyze --help",
    "aud graph query --help",
    "aud graph viz --help",
    "aud cfg --help",
    "aud cfg analyze --help",
    "aud cfg viz --help",
    "aud graphql --help",
    "aud graphql build --help",
    "aud graphql query --help",
    "aud graphql viz --help",
    "aud metadata --help",
    "aud metadata churn --help",
    "aud metadata coverage --help",
    "aud metadata analyze --help",
    "aud session --help",
    "aud session list --help",
    "aud session activity --help",
    "aud session analyze --help",
    "aud session report --help",
    "aud learn --help",
    "aud suggest --help",
    "aud explain --help",
    "aud query --help",
    "aud impact --help",
    "aud refactor --help",
    "aud blueprint --help",
    "aud deadcode --help",
    "aud deps --help",
    "aud docs --help",
    "aud lint --help",
    "aud fce --help",
    "aud planning --help",
    "aud workflows --help",
    "aud workflows analyze --help",
    "aud docker-analyze --help",
    "aud terraform --help",
    "aud cdk --help",
    "aud context --help",
    "aud context query --help",
    "aud rules --help",
]

# Phase 2: Minimal invocation tests (database readers, utilities)
# Format: (command, description, expected_to_pass)
# expected_to_pass=False means command runs but may exit non-zero (e.g., findings detected)
INVOCATION_TESTS = [
    # UTILITIES - always work
    ("aud tools", "Show tool versions", True),
    ("aud tools list", "List all tools", True),
    ("aud manual --list", "List manual topics", True),
    ("aud planning list", "List plans", True),

    # DATABASE READERS - require .pf/repo_index.db
    ("aud blueprint --structure", "Codebase structure", True),
    ("aud detect-frameworks", "Detected frameworks", True),
    ("aud deadcode --format summary", "Dead code summary", True),
    ("aud boundaries", "Security boundaries", False),  # exits 1 if issues found
    ("aud query --symbol main", "Query symbol", True),
    ("aud explain theauditor/cli.py", "Explain file context", True),

    # GRAPH COMMANDS - require graphs.db
    ("aud graph analyze", "Analyze dependency graph", True),
    ("aud graph query --uses theauditor.cli", "Query graph relationships", True),
    ("aud graph build", "Build/rebuild graphs.db", True),
    ("aud graph build-dfg", "Build DFG in graphs.db", True),
    ("aud graph viz", "Graph viz DOT output", True),

    # ML COMMANDS
    ("aud learn", "Train ML models", True),
    ("aud suggest --print-plan", "ML suggestions", True),

    # SESSION COMMANDS
    ("aud session list", "List Claude sessions", True),
    ("aud session activity --limit 5", "Session activity", True),
    ("aud session analyze", "Analyze sessions", True),
    ("aud session report", "Session report", True),

    # ANALYSIS COMMANDS
    ("aud fce", "FCE analysis", True),
    ("aud lint", "Run linters", False),  # exits non-zero if issues found
    ("aud deps --offline", "Dependency analysis (offline)", True),
    ("aud docs", "Generate docs", True),

    # METADATA - GROUP with subcommands (NOT: aud metadata alone)
    ("aud metadata churn", "Git churn metadata", True),

    # WORKSET - single command with options (NOT: aud workset show/list)
    ("aud workset --all --print-stats", "Workset all files", True),

    # CFG - GROUP with subcommands, requires --file option
    ("aud cfg analyze", "CFG analyze (no file)", True),

    # IMPACT - requires --file or --symbol option (NOT positional)
    ("aud impact --file theauditor/cli.py", "Impact analysis by file", True),

    # REFACTOR - single command, analyzes migrations (no extract subcommand)
    ("aud refactor", "Refactor migration analysis", True),

    # GRAPHQL - GROUP with subcommands
    ("aud graphql build", "GraphQL resolver build", True),

    # WORKFLOWS
    ("aud workflows analyze", "Analyze workflows", True),

    # DOCKER - deprecated but should still work
    ("aud docker-analyze", "Docker analysis (deprecated)", True),

    # TAINT - known slow, but include it (no gloves)
    ("aud taint", "Taint analysis", True),
]


# Commands that exit non-zero when they find issues (not failures)
EXPECTED_NONZERO = {
    "aud boundaries",
    "aud lint",
    "aud suggest",
}


# =============================================================================
# TEST EXECUTION
# =============================================================================

def run_command(cmd: str, timeout: int, cwd: Path, description: str = "") -> TestResult:
    """Run a command and capture results."""
    start = time.time()
    phase = "help" if "--help" in cmd else "invoke"
    name = description or cmd

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.time() - start

        # Determine success
        is_expected_nonzero = any(cmd.startswith(ec) for ec in EXPECTED_NONZERO)

        if result.returncode == 0:
            success = True
        elif is_expected_nonzero and result.stdout:
            # Command ran successfully, just reported findings
            success = True
        else:
            success = False

        error_summary = ""
        if not success:
            stderr_lines = result.stderr.strip().split("\n")
            for line in reversed(stderr_lines):
                if any(x in line.lower() for x in ["error:", "exception:", "traceback"]):
                    error_summary = line.strip()[:200]
                    break
            if not error_summary and stderr_lines:
                error_summary = stderr_lines[-1][:200]

        return TestResult(
            name=name,
            command=cmd,
            phase=phase,
            success=success,
            exit_code=result.returncode,
            duration=duration,
            stdout=result.stdout[:3000] if result.stdout else "",
            stderr=result.stderr[:3000] if result.stderr else "",
            error_summary=error_summary,
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            name=name,
            command=cmd,
            phase=phase,
            success=False,
            exit_code="TIMEOUT",
            duration=timeout,
            error_summary=f"Command timed out after {timeout}s",
        )
    except Exception as e:
        return TestResult(
            name=name,
            command=cmd,
            phase=phase,
            success=False,
            exit_code="EXCEPTION",
            duration=time.time() - start,
            error_summary=str(e)[:200],
        )


def print_status(msg: str, status: str = "...", duration: float = 0):
    """Print status line."""
    dur_str = f" ({duration:.1f}s)" if duration > 0 else ""
    if USE_RICH:
        style = {
            "OK": "green", "PASS": "green",
            "FAIL": "red", "TIMEOUT": "red",
            "SKIP": "yellow", "...": "dim",
        }.get(status, "white")
        console.print(f"  [{style}]{status:7}[/{style}] {msg}{dur_str}")
    else:
        print(f"  [{status:7}] {msg}{dur_str}")


def print_header(text: str):
    """Print section header."""
    if USE_RICH:
        console.print(f"\n[bold cyan]{text}[/bold cyan]")
        console.print("-" * 60)
    else:
        print(f"\n{text}")
        print("-" * 60)


# =============================================================================
# MAIN TEST PHASES
# =============================================================================

def check_environment() -> list[TestResult]:
    """Phase 1: Check environment is ready."""
    results = []

    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    results.append(TestResult(
        name="Python version",
        command=f"python --version",
        phase="setup",
        success=py_ok,
        exit_code=0 if py_ok else 1,
        duration=0,
        stdout=py_version,
        error_summary="" if py_ok else f"Python 3.11+ required, got {py_version}",
    ))
    print_status(f"Python {py_version}", "OK" if py_ok else "FAIL")

    # Check aud command exists
    aud_result = run_command("aud --version", HELP_TIMEOUT, PROJECT_ROOT, "aud command")
    results.append(aud_result)
    print_status("aud command", "OK" if aud_result.success else "FAIL", aud_result.duration)

    # Check .pf directory
    pf_exists = PF_DIR.exists()
    results.append(TestResult(
        name=".pf directory",
        command="check .pf/",
        phase="setup",
        success=True,  # Not a failure if missing, will be created
        exit_code=0,
        duration=0,
        stdout="exists" if pf_exists else "will be created",
    ))
    print_status(f".pf directory", "OK" if pf_exists else "SKIP")

    return results


def setup_js_extractor() -> list[TestResult]:
    """Phase 2: Build JS extractor if missing."""
    results = []

    if JS_BUNDLE.exists():
        print_status("JS extractor bundle", "OK")
        results.append(TestResult(
            name="JS extractor",
            command="check dist/extractor.cjs",
            phase="setup",
            success=True,
            exit_code=0,
            duration=0,
            stdout="bundle exists",
        ))
        return results

    print_status("JS extractor bundle missing, building...", "...")

    # npm install
    npm_install = run_command(
        "npm install",
        SETUP_TIMEOUT,
        JS_EXTRACTOR,
        "npm install"
    )
    results.append(npm_install)
    if not npm_install.success:
        print_status("npm install", "FAIL", npm_install.duration)
        return results
    print_status("npm install", "OK", npm_install.duration)

    # npm run build
    npm_build = run_command(
        "npm run build",
        SETUP_TIMEOUT,
        JS_EXTRACTOR,
        "npm run build"
    )
    results.append(npm_build)
    status = "OK" if npm_build.success else "FAIL"
    print_status("npm run build", status, npm_build.duration)

    return results


def run_indexing() -> list[TestResult]:
    """Phase 3: Run aud full --index --offline to build database."""
    results = []

    print_status("Running aud full --index --offline...", "...")

    index_result = run_command(
        "aud full --index --offline",
        INDEX_TIMEOUT,
        PROJECT_ROOT,
        "aud full --index --offline"
    )
    results.append(index_result)

    status = "OK" if index_result.success else "FAIL"
    print_status("aud full --index --offline", status, index_result.duration)

    if not index_result.success:
        print(f"         -> {index_result.error_summary}")

    return results


def run_help_tests() -> list[TestResult]:
    """Phase 4a: Test --help for all commands."""
    results = []

    for cmd in HELP_TESTS:
        result = run_command(cmd, HELP_TIMEOUT, PROJECT_ROOT, cmd)
        results.append(result)

        status = "OK" if result.success else "FAIL"
        print_status(cmd, status, result.duration)

        if not result.success:
            print(f"         -> {result.error_summary}")

    return results


def run_invocation_tests(command_timeout: int) -> list[TestResult]:
    """Phase 4b: Test minimal invocations."""
    results = []

    for cmd, description, expected_pass in INVOCATION_TESTS:
        result = run_command(cmd, command_timeout, PROJECT_ROOT, description)
        results.append(result)

        # Adjust success based on expectation
        if not expected_pass and result.exit_code != 0 and result.stdout:
            # Command ran but found issues - that's expected
            result.success = True

        status = "OK" if result.success else "FAIL"
        print_status(f"{description} ({cmd})", status, result.duration)

        if not result.success:
            print(f"         -> {result.error_summary}")

    return results


# =============================================================================
# REPORTING
# =============================================================================

def generate_report(report: PreFlightReport, output_path: Path) -> str:
    """Generate markdown report."""
    lines = [
        "# TheAuditor Pre-Flight Check Report",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Duration:** {report.total_time:.1f}s",
        f"**Index Duration:** {report.index_time:.1f}s",
        "",
        f"**Total Tests:** {len(report.results)}",
        f"**Passed:** {report.passed}",
        f"**Failed:** {report.failed}",
        "",
    ]

    if report.failed == 0:
        lines.extend([
            "## Result: ALL TESTS PASSED",
            "",
            "Pre-flight check complete. All systems operational.",
        ])
    else:
        lines.extend([
            "## FAILURES DETECTED",
            "",
        ])

        for i, fail in enumerate(report.failures, 1):
            lines.extend([
                f"### Failure {i}: {fail.name}",
                "",
                f"- **Command:** `{fail.command}`",
                f"- **Phase:** {fail.phase}",
                f"- **Exit Code:** {fail.exit_code}",
                f"- **Duration:** {fail.duration:.2f}s",
                "",
            ])

            if fail.error_summary:
                lines.extend([
                    "**Error:**",
                    "```",
                    fail.error_summary,
                    "```",
                    "",
                ])

            if fail.stderr:
                lines.extend([
                    "**Stderr:**",
                    "```",
                    fail.stderr[-1000:],
                    "```",
                    "",
                ])

            lines.append("---")
            lines.append("")

    # Summary table
    lines.extend([
        "",
        "## Test Summary by Phase",
        "",
        "| Phase | Total | Passed | Failed |",
        "|-------|-------|--------|--------|",
    ])

    phases = {}
    for r in report.results:
        if r.phase not in phases:
            phases[r.phase] = {"total": 0, "passed": 0, "failed": 0}
        phases[r.phase]["total"] += 1
        if r.success:
            phases[r.phase]["passed"] += 1
        else:
            phases[r.phase]["failed"] += 1

    for phase, counts in phases.items():
        lines.append(f"| {phase} | {counts['total']} | {counts['passed']} | {counts['failed']} |")

    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    return content


def print_summary(report: PreFlightReport):
    """Print final summary."""
    if USE_RICH:
        if report.failed == 0:
            panel = Panel(
                f"[bold green]ALL {report.passed} TESTS PASSED[/bold green]\n\n"
                f"[dim]Total: {report.total_time:.1f}s | Index: {report.index_time:.1f}s[/dim]",
                title="[bold]Pre-Flight Check Complete[/bold]",
                border_style="green",
            )
        else:
            panel = Panel(
                f"[bold red]{report.failed} FAILURES[/bold red] / {report.passed} passed\n\n"
                f"[dim]Total: {report.total_time:.1f}s[/dim]\n\n"
                f"[yellow]See execution_report.md for details[/yellow]",
                title="[bold]Pre-Flight Check Complete[/bold]",
                border_style="red",
            )
        console.print()
        console.print(panel)
    else:
        print()
        print("=" * 60)
        if report.failed == 0:
            print(f"ALL {report.passed} TESTS PASSED ({report.total_time:.1f}s)")
        else:
            print(f"{report.failed} FAILURES / {report.passed} passed ({report.total_time:.1f}s)")
            print("See execution_report.md for details")
        print("=" * 60)


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="TheAuditor Pre-Flight Check")
    parser.add_argument("--skip-index", action="store_true",
                        help="Skip aud full indexing (use existing .pf/)")
    parser.add_argument("--skip-setup", action="store_true",
                        help="Skip environment and JS extractor setup")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show all output")
    parser.add_argument("--timeout", type=int, default=COMMAND_TIMEOUT,
                        help=f"Command timeout in seconds (default: {COMMAND_TIMEOUT})")
    parser.add_argument("--output", "-o", type=Path, default=Path("execution_report.md"),
                        help="Output path for report")
    args = parser.parse_args()

    # Banner
    if USE_RICH:
        console.print(Panel(
            "[bold]TheAuditor Pre-Flight Check[/bold]\n"
            "[dim]Complete systems verification - no gloves[/dim]",
            border_style="blue",
        ))
    else:
        print("=" * 60)
        print("TheAuditor Pre-Flight Check")
        print("Complete systems verification - no gloves")
        print("=" * 60)

    report = PreFlightReport()
    start_time = time.time()

    # Phase 1: Environment
    if not args.skip_setup:
        print_header("PHASE 1: ENVIRONMENT CHECK")
        env_results = check_environment()
        report.results.extend(env_results)

        # Phase 2: JS Extractor
        print_header("PHASE 2: JS EXTRACTOR SETUP")
        setup_start = time.time()
        setup_results = setup_js_extractor()
        report.results.extend(setup_results)
        report.setup_time = time.time() - setup_start

    # Phase 3: Indexing
    if not args.skip_index:
        print_header("PHASE 3: DATABASE INDEXING")
        index_start = time.time()
        index_results = run_indexing()
        report.results.extend(index_results)
        report.index_time = time.time() - index_start

        # Check if indexing failed - abort if so
        if index_results and not index_results[0].success:
            print("\n[ABORT] Indexing failed - cannot proceed with command tests")
            report.total_time = time.time() - start_time
            generate_report(report, args.output)
            print_summary(report)
            return min(report.failed, 125)

    # Phase 4a: Help tests
    print_header("PHASE 4a: COMMAND HELP TESTS")
    help_results = run_help_tests()
    report.results.extend(help_results)

    # Phase 4b: Invocation tests
    print_header("PHASE 4b: COMMAND INVOCATION TESTS")
    invoke_results = run_invocation_tests(args.timeout)
    report.results.extend(invoke_results)

    # Finalize
    report.total_time = time.time() - start_time

    # Generate report
    generate_report(report, args.output)
    print(f"\nReport saved to: {args.output}")

    # Print summary
    print_summary(report)

    return min(report.failed, 125)


if __name__ == "__main__":
    sys.exit(main())
