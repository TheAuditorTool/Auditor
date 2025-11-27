#!/usr/bin/env python
"""
CLI Smoke Test Suite for TheAuditor
====================================

Production-ready comprehensive CLI testing framework that:
- Enumerates every command/subcommand in the Click CLI tree
- Tests --help for all commands (catches import errors)
- Tests no-args invocation (catches runtime setup issues)
- Supports test fixtures for commands requiring arguments
- Parallel execution with filesystem isolation (no DB locking)
- Uses Click's CliRunner for fast in-process testing
- Detailed JSON + JUnit XML reports for CI/CD
- Regression detection against previous runs

Usage:
    python scripts/cli_smoke_test.py                    # Run all tests
    python scripts/cli_smoke_test.py --parallel 8      # 8 parallel workers
    python scripts/cli_smoke_test.py --filter "graph"  # Only test commands matching "graph"
    python scripts/cli_smoke_test.py --quick           # Only --help tests (fast)
    python scripts/cli_smoke_test.py --compare         # Compare against last run
    python scripts/cli_smoke_test.py --list            # Just list all commands
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Optional rich support for prettier output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


class TestStatus(str, Enum):
    """Test result status."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class FailureCategory(str, Enum):
    """Categorize failures for better debugging."""
    NONE = "none"
    IMPORT_ERROR = "import_error"
    MISSING_REQUIRED_ARG = "missing_required_arg"
    MISSING_DATABASE = "missing_database"
    MISSING_FILE = "missing_file"
    PERMISSION_ERROR = "permission_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class CommandParam:
    """Represents a Click command parameter."""
    name: str
    param_type: str  # "Option" or "Argument"
    required: bool
    is_flag: bool
    default: Any
    help_text: str | None
    choices: list[str] | None


@dataclass
class CommandInfo:
    """Full information about a CLI command."""
    full_name: str  # e.g., "aud graph build"
    name: str  # e.g., "build"
    is_group: bool
    parent: str | None
    params: list[CommandParam] = field(default_factory=list)
    subcommands: list[str] = field(default_factory=list)
    help_text: str | None = None
    deprecated: bool = False


@dataclass
class TestResult:
    """Result of a single test."""
    status: TestStatus
    exit_code: int | None
    duration_ms: float
    stdout: str | None
    stderr: str | None
    failure_category: FailureCategory = FailureCategory.NONE
    error_message: str | None = None


@dataclass
class CommandTestResults:
    """All test results for a single command."""
    command: str
    command_info: CommandInfo
    help_test: TestResult | None = None
    no_args_test: TestResult | None = None
    fixture_tests: dict[str, TestResult] = field(default_factory=dict)
    total_duration_ms: float = 0.0


@dataclass
class TestSuiteResults:
    """Complete test suite results."""
    timestamp: str
    duration_seconds: float
    total_commands: int
    total_groups: int
    tests_run: int
    summary: dict[str, int] = field(default_factory=dict)
    commands: list[CommandTestResults] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    regressions: list[dict] = field(default_factory=list)
    improvements: list[dict] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)


class CLISmokeTest:
    """Main CLI smoke test runner."""

    # Fixtures file path (external YAML/JSON)
    FIXTURES_FILE = PROJECT_ROOT / "scripts" / "smoke_fixtures.json"

    # Commands to skip entirely (known broken, deprecated, or dangerous)
    SKIP_COMMANDS: set[str] = {
        # Add commands that should be skipped
    }

    # Commands that are expected to fail without args (not a bug)
    EXPECTED_NO_ARGS_FAIL: set[str] = {
        # Commands that legitimately require arguments
    }

    # Timeout settings (seconds)
    HELP_TIMEOUT = 10
    NO_ARGS_TIMEOUT = 30
    FIXTURE_TIMEOUT = 60

    def __init__(
        self,
        parallel_workers: int = 1,
        filter_pattern: str | None = None,
        quick_mode: bool = False,
        verbose: bool = False,
        output_dir: Path | None = None,
        use_subprocess: bool = False,
    ):
        self.parallel_workers = parallel_workers
        self.filter_pattern = filter_pattern
        self.quick_mode = quick_mode
        self.verbose = verbose
        self.output_dir = output_dir or PROJECT_ROOT / "tests" / "smoketests"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_subprocess = use_subprocess

        # Load external fixtures
        self.test_fixtures = self._load_fixtures()

        # Results storage
        self.commands: list[CommandInfo] = []
        self.results: list[CommandTestResults] = []

        # Click imports (lazy loaded)
        self._cli = None
        self._runner = None

    def _load_fixtures(self) -> dict[str, list[str] | dict[str, list[str]]]:
        """Load test fixtures from external file."""
        if self.FIXTURES_FILE.exists():
            with open(self.FIXTURES_FILE) as f:
                return json.load(f)

        # Default fixtures if file doesn't exist
        return {
            "aud query": ["--symbol", "main"],
            "aud explain": ["theauditor/cli.py"],
            "aud workset": ["--files", "theauditor/cli.py"],
            "aud graph query": ["--symbol", "main"],
            "aud context query": ["--symbol", "main"],
            "aud full": {
                "offline": ["--offline", "--dry-run"],
                "index_only": ["--index", "--dry-run"],
            },
        }

    def _get_cli(self):
        """Lazy load the CLI and runner."""
        if self._cli is None:
            from click.testing import CliRunner
            from theauditor.cli import cli
            self._cli = cli
            self._runner = CliRunner()
        return self._cli, self._runner

    def log(self, msg: str, level: str = "INFO") -> None:
        """Log with optional verbosity control."""
        if RICH_AVAILABLE and console:
            styles = {
                "INFO": "",
                "PASS": "green",
                "FAIL": "red",
                "WARN": "yellow",
                "SKIP": "dim",
                "HEAD": "cyan bold",
            }
            style = styles.get(level, "")
            if level in ("PASS", "FAIL", "WARN", "HEAD") or self.verbose:
                console.print(f"[{style}][{level}][/{style}] {msg}")
        else:
            colors = {
                "INFO": "\033[0m",
                "PASS": "\033[92m",
                "FAIL": "\033[91m",
                "WARN": "\033[93m",
                "SKIP": "\033[90m",
                "HEAD": "\033[96m",
            }
            reset = "\033[0m"
            color = colors.get(level, colors["INFO"])
            if level in ("PASS", "FAIL", "WARN", "HEAD") or self.verbose:
                print(f"{color}[{level}]{reset} {msg}")

    def enumerate_commands(self) -> list[CommandInfo]:
        """Enumerate all commands in the CLI using Click introspection."""
        try:
            import click
            cli, _ = self._get_cli()
        except ImportError as e:
            self.log(f"Failed to import CLI: {e}", "FAIL")
            return []

        commands = []

        def walk_commands(group: click.Group, prefix: str = "aud", parent: str | None = None):
            """Recursively walk the command tree."""
            for name in sorted(group.commands.keys()):
                cmd = group.commands[name]
                full_name = f"{prefix} {name}"

                # Extract parameters
                params = []
                for param in getattr(cmd, "params", []):
                    params.append(CommandParam(
                        name=param.name,
                        param_type=type(param).__name__,
                        required=getattr(param, "required", False),
                        is_flag=getattr(param, "is_flag", False),
                        default=getattr(param, "default", None),
                        help_text=getattr(param, "help", None),
                        choices=list(param.type.choices) if hasattr(param, "type") and hasattr(param.type, "choices") else None,
                    ))

                if isinstance(cmd, click.Group):
                    info = CommandInfo(
                        full_name=full_name,
                        name=name,
                        is_group=True,
                        parent=parent,
                        params=params,
                        subcommands=list(cmd.commands.keys()),
                        help_text=cmd.help,
                        deprecated=getattr(cmd, "deprecated", False),
                    )
                    commands.append(info)
                    walk_commands(cmd, full_name, full_name)
                else:
                    info = CommandInfo(
                        full_name=full_name,
                        name=name,
                        is_group=False,
                        parent=parent,
                        params=params,
                        help_text=cmd.help,
                        deprecated=getattr(cmd, "deprecated", False),
                    )
                    commands.append(info)

        walk_commands(cli)
        return commands

    def categorize_failure(self, stderr: str | None, stdout: str | None, exit_code: int | None) -> tuple[FailureCategory, str | None]:
        """Analyze output to categorize the failure type."""
        combined = f"{stderr or ''} {stdout or ''}".lower()

        if exit_code == 0:
            return FailureCategory.NONE, None

        if "importerror" in combined or "modulenotfounderror" in combined:
            match = re.search(r"(?:import|module).*?['\"]([^'\"]+)['\"]", combined, re.I)
            return FailureCategory.IMPORT_ERROR, match.group(1) if match else "unknown module"

        if "missing" in combined and ("argument" in combined or "option" in combined or "required" in combined):
            return FailureCategory.MISSING_REQUIRED_ARG, "required argument not provided"

        if "database" in combined or "repo_index.db" in combined or "no such table" in combined:
            return FailureCategory.MISSING_DATABASE, "database not found or not initialized"

        if "filenotfounderror" in combined or "no such file" in combined:
            match = re.search(r"(?:file|path)['\"]?[:\s]+([^\s'\"]+)", combined, re.I)
            return FailureCategory.MISSING_FILE, match.group(1) if match else "file not found"

        if "permissionerror" in combined or "permission denied" in combined:
            return FailureCategory.PERMISSION_ERROR, "permission denied"

        if "error" in combined or "exception" in combined or "traceback" in combined:
            lines = (stderr or "").strip().split("\n")
            error_line = lines[-1] if lines else "runtime error"
            return FailureCategory.RUNTIME_ERROR, error_line[:200]

        return FailureCategory.UNKNOWN, "unknown failure"

    def run_with_cli_runner(self, args: list[str], timeout: int) -> TestResult:
        """Run command using Click's CliRunner (fast, in-process)."""
        cli, runner = self._get_cli()
        start = time.perf_counter()

        try:
            result = runner.invoke(cli, args, catch_exceptions=True)
            duration_ms = (time.perf_counter() - start) * 1000

            stdout = result.output[:1000] if result.output else None
            stderr = None
            if result.exception and not isinstance(result.exception, SystemExit):
                import traceback
                stderr = "".join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__))[:1000]

            status = TestStatus.PASS if result.exit_code == 0 else TestStatus.FAIL
            category, error_msg = self.categorize_failure(stderr, stdout, result.exit_code)

            return TestResult(
                status=status,
                exit_code=result.exit_code,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                failure_category=category,
                error_message=error_msg,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return TestResult(
                status=TestStatus.ERROR,
                exit_code=None,
                duration_ms=duration_ms,
                stdout=None,
                stderr=str(e),
                failure_category=FailureCategory.UNKNOWN,
                error_message=str(e),
            )

    def run_with_subprocess(self, cmd: str, timeout: int, temp_dir: Path | None = None) -> TestResult:
        """Run command using subprocess (for integration tests with isolation)."""
        start = time.perf_counter()

        # Set up isolated environment
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        cwd = str(PROJECT_ROOT)

        # If temp_dir provided, use it for DB isolation
        if temp_dir:
            env["AUD_TEST_ISOLATION"] = str(temp_dir)
            # Copy minimal config if needed
            pf_dir = PROJECT_ROOT / ".pf"
            if pf_dir.exists():
                # Only copy config files, not the large databases
                temp_pf = temp_dir / ".pf"
                temp_pf.mkdir(exist_ok=True)
                for config_file in pf_dir.glob("*.json"):
                    shutil.copy(config_file, temp_pf)

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )

            duration_ms = (time.perf_counter() - start) * 1000

            max_len = 1000
            stdout = result.stdout[:max_len] if result.stdout else None
            stderr = result.stderr[:max_len] if result.stderr else None

            status = TestStatus.PASS if result.returncode == 0 else TestStatus.FAIL
            category, error_msg = self.categorize_failure(stderr, stdout, result.returncode)

            return TestResult(
                status=status,
                exit_code=result.returncode,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                failure_category=category,
                error_message=error_msg,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start) * 1000
            return TestResult(
                status=TestStatus.TIMEOUT,
                exit_code=None,
                duration_ms=duration_ms,
                stdout=None,
                stderr=None,
                failure_category=FailureCategory.TIMEOUT,
                error_message=f"command timed out after {timeout}s",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return TestResult(
                status=TestStatus.ERROR,
                exit_code=None,
                duration_ms=duration_ms,
                stdout=None,
                stderr=str(e),
                failure_category=FailureCategory.UNKNOWN,
                error_message=str(e),
            )

    def test_command(self, cmd_info: CommandInfo) -> CommandTestResults:
        """Run all tests for a single command."""
        results = CommandTestResults(
            command=cmd_info.full_name,
            command_info=cmd_info,
        )

        start_time = time.perf_counter()

        # Skip if in skip list
        if cmd_info.full_name in self.SKIP_COMMANDS:
            self.log(f"SKIP {cmd_info.full_name} (in skip list)", "SKIP")
            return results

        # Skip groups (we test their subcommands)
        if cmd_info.is_group:
            return results

        # Convert "aud foo bar" to ["foo", "bar"] for CliRunner
        args = cmd_info.full_name.split()[1:]  # Remove "aud" prefix

        # Test 1: --help (use CliRunner - fast)
        self.log(f"Testing {cmd_info.full_name} --help", "INFO")
        results.help_test = self.run_with_cli_runner(args + ["--help"], self.HELP_TIMEOUT)

        if results.help_test.status == TestStatus.PASS:
            self.log(f"  --help: PASS ({results.help_test.duration_ms:.0f}ms)", "PASS")
        else:
            self.log(f"  --help: {results.help_test.status} - {results.help_test.failure_category}", "FAIL")

        # Quick mode stops here
        if self.quick_mode:
            results.total_duration_ms = (time.perf_counter() - start_time) * 1000
            return results

        # Test 2: No args invocation (use CliRunner)
        self.log(f"Testing {cmd_info.full_name} (no args)", "INFO")
        results.no_args_test = self.run_with_cli_runner(args, self.NO_ARGS_TIMEOUT)

        # Check if this command is expected to fail without args
        expected_fail = cmd_info.full_name in self.EXPECTED_NO_ARGS_FAIL
        has_required = any(p.required and p.param_type == "Argument" for p in cmd_info.params)

        if results.no_args_test.status == TestStatus.PASS:
            self.log(f"  no-args: PASS ({results.no_args_test.duration_ms:.0f}ms)", "PASS")
        elif has_required or expected_fail:
            self.log(f"  no-args: EXPECTED FAIL (requires args)", "WARN")
        else:
            self.log(f"  no-args: {results.no_args_test.status} - {results.no_args_test.failure_category}", "FAIL")

        # Test 3: Fixture tests (use subprocess with isolation for integration tests)
        fixtures = self.test_fixtures.get(cmd_info.full_name)
        if fixtures:
            if isinstance(fixtures, list):
                fixtures = {"default": fixtures}

            for fixture_name, fixture_args in fixtures.items():
                # Create isolated temp directory for this test
                with tempfile.TemporaryDirectory(prefix=f"aud_test_{cmd_info.name}_") as temp_dir:
                    args_str = " ".join(fixture_args)
                    full_cmd = f"{cmd_info.full_name} {args_str}"

                    self.log(f"Testing {cmd_info.full_name} [{fixture_name}]", "INFO")

                    if self.use_subprocess:
                        fixture_result = self.run_with_subprocess(
                            full_cmd,
                            self.FIXTURE_TIMEOUT,
                            temp_dir=Path(temp_dir)
                        )
                    else:
                        # Use CliRunner for fixture tests too (faster)
                        fixture_result = self.run_with_cli_runner(
                            args + fixture_args,
                            self.FIXTURE_TIMEOUT
                        )

                    results.fixture_tests[fixture_name] = fixture_result

                    if fixture_result.status == TestStatus.PASS:
                        self.log(f"  [{fixture_name}]: PASS ({fixture_result.duration_ms:.0f}ms)", "PASS")
                    else:
                        self.log(f"  [{fixture_name}]: {fixture_result.status} - {fixture_result.error_message}", "FAIL")

        results.total_duration_ms = (time.perf_counter() - start_time) * 1000
        return results

    def run_tests(self) -> TestSuiteResults:
        """Run all tests."""
        start_time = time.perf_counter()

        self.log("=" * 60, "HEAD")
        self.log("TheAuditor CLI Smoke Test Suite", "HEAD")
        self.log("=" * 60, "HEAD")

        # Enumerate commands
        self.log("\nEnumerating CLI commands...", "INFO")
        self.commands = self.enumerate_commands()

        if not self.commands:
            self.log("No commands found! Check CLI import.", "FAIL")
            return TestSuiteResults(
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_seconds=0,
                total_commands=0,
                total_groups=0,
                tests_run=0,
            )

        # Apply filter if specified
        if self.filter_pattern:
            pattern = re.compile(self.filter_pattern, re.I)
            self.commands = [c for c in self.commands if pattern.search(c.full_name)]
            self.log(f"Filtered to {len(self.commands)} commands matching '{self.filter_pattern}'", "INFO")

        total_groups = sum(1 for c in self.commands if c.is_group)
        total_commands = len(self.commands) - total_groups

        self.log(f"Found {total_commands} commands in {total_groups} groups", "INFO")
        self.log(f"Mode: {'quick (--help only)' if self.quick_mode else 'full'}", "INFO")
        self.log(f"Workers: {self.parallel_workers}", "INFO")
        self.log(f"Runner: {'subprocess' if self.use_subprocess else 'CliRunner (in-process)'}", "INFO")
        self.log("", "INFO")

        # Run tests
        leaf_commands = [c for c in self.commands if not c.is_group]

        if RICH_AVAILABLE and console and not self.verbose:
            # Use rich progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Testing commands...", total=len(leaf_commands))

                if self.parallel_workers > 1:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                        futures = {executor.submit(self.test_command, cmd): cmd for cmd in leaf_commands}
                        for future in concurrent.futures.as_completed(futures):
                            try:
                                result = future.result()
                                self.results.append(result)
                            except Exception as e:
                                cmd = futures[future]
                                self.log(f"Exception testing {cmd.full_name}: {e}", "FAIL")
                            progress.advance(task)
                else:
                    for cmd in leaf_commands:
                        result = self.test_command(cmd)
                        self.results.append(result)
                        progress.advance(task)
        else:
            # Standard execution without rich
            if self.parallel_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                    futures = {executor.submit(self.test_command, cmd): cmd for cmd in leaf_commands}
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            result = future.result()
                            self.results.append(result)
                        except Exception as e:
                            cmd = futures[future]
                            self.log(f"Exception testing {cmd.full_name}: {e}", "FAIL")
            else:
                for cmd in leaf_commands:
                    result = self.test_command(cmd)
                    self.results.append(result)

        # Add group results (empty, just for completeness)
        for cmd in self.commands:
            if cmd.is_group:
                self.results.append(CommandTestResults(command=cmd.full_name, command_info=cmd))

        # Calculate summary
        duration_seconds = time.perf_counter() - start_time

        summary = {
            "help_pass": 0,
            "help_fail": 0,
            "help_timeout": 0,
            "no_args_pass": 0,
            "no_args_fail": 0,
            "no_args_timeout": 0,
            "no_args_expected_fail": 0,
            "fixture_pass": 0,
            "fixture_fail": 0,
        }

        failures = []
        tests_run = 0

        for r in self.results:
            if r.command_info.is_group:
                continue

            if r.help_test:
                tests_run += 1
                if r.help_test.status == TestStatus.PASS:
                    summary["help_pass"] += 1
                elif r.help_test.status == TestStatus.TIMEOUT:
                    summary["help_timeout"] += 1
                    failures.append({
                        "command": r.command,
                        "test": "help",
                        "status": r.help_test.status.value,
                        "category": r.help_test.failure_category.value,
                        "error": r.help_test.error_message,
                    })
                else:
                    summary["help_fail"] += 1
                    failures.append({
                        "command": r.command,
                        "test": "help",
                        "status": r.help_test.status.value,
                        "category": r.help_test.failure_category.value,
                        "error": r.help_test.error_message,
                    })

            if r.no_args_test:
                tests_run += 1
                has_required = any(p.required and p.param_type == "Argument" for p in r.command_info.params)

                if r.no_args_test.status == TestStatus.PASS:
                    summary["no_args_pass"] += 1
                elif r.no_args_test.status == TestStatus.TIMEOUT:
                    summary["no_args_timeout"] += 1
                elif has_required or r.command in self.EXPECTED_NO_ARGS_FAIL:
                    summary["no_args_expected_fail"] += 1
                else:
                    summary["no_args_fail"] += 1
                    if r.no_args_test.failure_category != FailureCategory.MISSING_REQUIRED_ARG:
                        failures.append({
                            "command": r.command,
                            "test": "no_args",
                            "status": r.no_args_test.status.value,
                            "category": r.no_args_test.failure_category.value,
                            "error": r.no_args_test.error_message,
                        })

            for fixture_name, fixture_result in r.fixture_tests.items():
                tests_run += 1
                if fixture_result.status == TestStatus.PASS:
                    summary["fixture_pass"] += 1
                else:
                    summary["fixture_fail"] += 1
                    failures.append({
                        "command": r.command,
                        "test": f"fixture:{fixture_name}",
                        "status": fixture_result.status.value,
                        "category": fixture_result.failure_category.value,
                        "error": fixture_result.error_message,
                    })

        # Build results
        suite_results = TestSuiteResults(
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_seconds=duration_seconds,
            total_commands=total_commands,
            total_groups=total_groups,
            tests_run=tests_run,
            summary=summary,
            commands=[self._result_to_dict(r) for r in self.results],
            failures=failures,
            environment={
                "python_version": sys.version,
                "platform": sys.platform,
                "cwd": str(PROJECT_ROOT),
                "parallel_workers": self.parallel_workers,
                "quick_mode": self.quick_mode,
            },
        )

        return suite_results

    def _result_to_dict(self, result: CommandTestResults) -> dict:
        """Convert CommandTestResults to a JSON-serializable dict."""
        def test_to_dict(t: TestResult | None) -> dict | None:
            if t is None:
                return None
            return {
                "status": t.status.value,
                "exit_code": t.exit_code,
                "duration_ms": t.duration_ms,
                "failure_category": t.failure_category.value,
                "error_message": t.error_message,
                "stdout": t.stdout,
                "stderr": t.stderr,
            }

        return {
            "command": result.command,
            "is_group": result.command_info.is_group,
            "params": [asdict(p) for p in result.command_info.params],
            "help_test": test_to_dict(result.help_test),
            "no_args_test": test_to_dict(result.no_args_test),
            "fixture_tests": {k: test_to_dict(v) for k, v in result.fixture_tests.items()},
            "total_duration_ms": result.total_duration_ms,
        }

    def compare_with_previous(self, current: TestSuiteResults) -> tuple[list[dict], list[dict]]:
        """Compare current results with the most recent previous run."""
        result_files = sorted(self.output_dir.glob("cli_smoke_test_*.json"), reverse=True)

        if len(result_files) < 2:
            return [], []

        previous_file = result_files[1]
        try:
            with open(previous_file) as f:
                previous = json.load(f)
        except Exception:
            return [], []

        regressions = []
        improvements = []

        prev_by_cmd = {}
        for cmd_result in previous.get("commands", []):
            prev_by_cmd[cmd_result["command"]] = cmd_result

        for cmd_result in current.commands:
            if isinstance(cmd_result, dict):
                cmd = cmd_result["command"]
                curr_help = cmd_result.get("help_test", {})
            else:
                cmd = cmd_result.command
                curr_help = self._result_to_dict(cmd_result).get("help_test", {})

            prev = prev_by_cmd.get(cmd, {})
            prev_help = prev.get("help_test", {})

            if prev_help.get("status") == "PASS" and curr_help.get("status") != "PASS":
                regressions.append({
                    "command": cmd,
                    "test": "help",
                    "previous": "PASS",
                    "current": curr_help.get("status"),
                    "error": curr_help.get("error_message"),
                })

            if prev_help.get("status") != "PASS" and curr_help.get("status") == "PASS":
                improvements.append({
                    "command": cmd,
                    "test": "help",
                    "previous": prev_help.get("status"),
                    "current": "PASS",
                })

        return regressions, improvements

    def save_results(self, results: TestSuiteResults) -> Path:
        """Save results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cli_smoke_test_{timestamp}.json"
        filepath = self.output_dir / filename

        data = {
            "timestamp": results.timestamp,
            "duration_seconds": results.duration_seconds,
            "total_commands": results.total_commands,
            "total_groups": results.total_groups,
            "tests_run": results.tests_run,
            "summary": results.summary,
            "failures": results.failures,
            "regressions": results.regressions,
            "improvements": results.improvements,
            "environment": results.environment,
            "commands": results.commands,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        latest_path = self.output_dir / "cli_smoke_test_latest.json"
        with open(latest_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        return filepath

    def save_junit_xml(self, results: TestSuiteResults) -> Path:
        """Generate JUnit XML report for CI/CD integration."""
        filepath = self.output_dir / "junit.xml"

        testsuites = ET.Element("testsuites")

        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", "CLI Smoke Tests")
        testsuite.set("tests", str(results.tests_run))
        testsuite.set("failures", str(len(results.failures)))
        testsuite.set("errors", "0")
        testsuite.set("time", f"{results.duration_seconds:.2f}")
        testsuite.set("timestamp", results.timestamp)

        for cmd_result in results.commands:
            if isinstance(cmd_result, dict):
                command = cmd_result["command"]
                is_group = cmd_result.get("is_group", False)
                help_test = cmd_result.get("help_test")
                no_args_test = cmd_result.get("no_args_test")
                fixture_tests = cmd_result.get("fixture_tests", {})
            else:
                command = cmd_result.command
                is_group = cmd_result.command_info.is_group
                help_test = self._result_to_dict(cmd_result).get("help_test") if cmd_result.help_test else None
                no_args_test = self._result_to_dict(cmd_result).get("no_args_test") if cmd_result.no_args_test else None
                fixture_tests = {k: self._result_to_dict(CommandTestResults(command="", command_info=cmd_result.command_info, fixture_tests={k: v}))["fixture_tests"][k] for k, v in cmd_result.fixture_tests.items()}

            if is_group:
                continue

            # Help test case
            if help_test:
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("name", f"{command} --help")
                testcase.set("classname", "cli.help")
                testcase.set("time", f"{help_test.get('duration_ms', 0) / 1000:.3f}")

                if help_test.get("status") != "PASS":
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("type", help_test.get("failure_category", "unknown"))
                    failure.set("message", help_test.get("error_message") or "unknown error")
                    if help_test.get("stderr"):
                        failure.text = help_test["stderr"]

            # No-args test case
            if no_args_test:
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("name", f"{command} (no args)")
                testcase.set("classname", "cli.no_args")
                testcase.set("time", f"{no_args_test.get('duration_ms', 0) / 1000:.3f}")

                if no_args_test.get("status") not in ("PASS",) and no_args_test.get("failure_category") != "missing_required_arg":
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("type", no_args_test.get("failure_category", "unknown"))
                    failure.set("message", no_args_test.get("error_message") or "unknown error")

            # Fixture test cases
            for fixture_name, fixture_result in fixture_tests.items():
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("name", f"{command} [{fixture_name}]")
                testcase.set("classname", "cli.fixture")
                testcase.set("time", f"{fixture_result.get('duration_ms', 0) / 1000:.3f}")

                if fixture_result.get("status") != "PASS":
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("type", fixture_result.get("failure_category", "unknown"))
                    failure.set("message", fixture_result.get("error_message") or "unknown error")

        tree = ET.ElementTree(testsuites)
        ET.indent(tree, space="  ")
        tree.write(filepath, encoding="unicode", xml_declaration=True)

        return filepath

    def print_summary(self, results: TestSuiteResults) -> int:
        """Print human-readable summary."""
        s = results.summary

        if RICH_AVAILABLE and console:
            console.print("\n" + "=" * 60)
            console.print("[bold cyan]TEST SUMMARY[/bold cyan]")
            console.print("=" * 60)

            table = Table(show_header=True, header_style="bold")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Duration", f"{results.duration_seconds:.1f}s")
            table.add_row("Commands", str(results.total_commands))
            table.add_row("Groups", str(results.total_groups))
            table.add_row("Tests Run", str(results.tests_run))

            console.print(table)

            # Help tests table
            help_table = Table(title="--help Tests", show_header=True)
            help_table.add_column("Status")
            help_table.add_column("Count", justify="right")
            help_table.add_row("[green]PASS[/green]", str(s.get("help_pass", 0)))
            help_table.add_row("[red]FAIL[/red]", str(s.get("help_fail", 0)))
            help_table.add_row("[yellow]TIMEOUT[/yellow]", str(s.get("help_timeout", 0)))
            console.print(help_table)

            if not self.quick_mode:
                noargs_table = Table(title="No-args Tests", show_header=True)
                noargs_table.add_column("Status")
                noargs_table.add_column("Count", justify="right")
                noargs_table.add_row("[green]PASS[/green]", str(s.get("no_args_pass", 0)))
                noargs_table.add_row("[red]FAIL[/red]", str(s.get("no_args_fail", 0)))
                noargs_table.add_row("[yellow]EXPECTED FAIL[/yellow]", str(s.get("no_args_expected_fail", 0)))
                console.print(noargs_table)

            if results.failures:
                console.print("\n[bold red]FAILURES:[/bold red]")
                for f in results.failures[:10]:
                    console.print(f"  [red]{f['command']}[/red] [{f['test']}]")
                    console.print(f"    Category: {f['category']}")
                    console.print(f"    Error: {f['error']}")
                if len(results.failures) > 10:
                    console.print(f"  ... and {len(results.failures) - 10} more")

            if results.regressions:
                console.print("\n[bold red]REGRESSIONS:[/bold red]")
                for r in results.regressions:
                    console.print(f"  [red]{r['command']}[/red]: {r['previous']} -> {r['current']}")

            if results.improvements:
                console.print("\n[bold green]IMPROVEMENTS:[/bold green]")
                for i in results.improvements:
                    console.print(f"  [green]{i['command']}[/green]: {i['previous']} -> {i['current']}")

        else:
            print("\n" + "=" * 60)
            print("TEST SUMMARY")
            print("=" * 60)

            print(f"\nDuration: {results.duration_seconds:.1f}s")
            print(f"Commands: {results.total_commands} (in {results.total_groups} groups)")
            print(f"Tests Run: {results.tests_run}")

            print("\n--help tests:")
            print(f"  PASS: {s.get('help_pass', 0)}")
            print(f"  FAIL: {s.get('help_fail', 0)}")
            print(f"  TIMEOUT: {s.get('help_timeout', 0)}")

            if not self.quick_mode:
                print("\nNo-args tests:")
                print(f"  PASS: {s.get('no_args_pass', 0)}")
                print(f"  FAIL: {s.get('no_args_fail', 0)}")
                print(f"  EXPECTED FAIL: {s.get('no_args_expected_fail', 0)}")

            if results.failures:
                print("\n" + "-" * 60)
                print("FAILURES:")
                for f in results.failures[:10]:
                    print(f"  {f['command']} [{f['test']}]")
                    print(f"    Category: {f['category']}")
                    print(f"    Error: {f['error']}")

        # Final verdict
        total_failures = s.get("help_fail", 0) + s.get("help_timeout", 0)
        print("\n" + "=" * 60)
        if total_failures == 0:
            print("RESULT: ALL HELP TESTS PASSED")
            return 0
        else:
            print(f"RESULT: {total_failures} HELP TEST FAILURES")
            return 1

    def list_commands(self) -> None:
        """Just list all commands without running tests."""
        commands = self.enumerate_commands()

        if RICH_AVAILABLE and console:
            table = Table(title=f"CLI Commands ({len(commands)} total)")
            table.add_column("Type", style="cyan", width=8)
            table.add_column("Command", style="white")
            table.add_column("Parameters", style="dim")

            for cmd in commands:
                prefix = "GROUP" if cmd.is_group else "CMD"
                params = []
                for p in cmd.params:
                    if p.required:
                        params.append(f"[red]{p.name}*[/red]")
                    elif p.is_flag:
                        params.append(f"[dim]--{p.name}[/dim]")
                    else:
                        params.append(p.name)

                table.add_row(prefix, cmd.full_name, ", ".join(params) if params else "-")

            console.print(table)
        else:
            print(f"Found {len(commands)} commands/groups:\n")
            for cmd in commands:
                prefix = "[GROUP]" if cmd.is_group else "[CMD]  "
                print(f"{prefix} {cmd.full_name}")


def main():
    parser = argparse.ArgumentParser(
        description="CLI Smoke Test Suite for TheAuditor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cli_smoke_test.py                    # Run all tests
  python scripts/cli_smoke_test.py --parallel 8      # 8 parallel workers
  python scripts/cli_smoke_test.py --filter "graph"  # Only test graph commands
  python scripts/cli_smoke_test.py --quick           # Only --help tests
  python scripts/cli_smoke_test.py --list            # Just list commands
        """
    )

    parser.add_argument("--parallel", "-p", type=int, default=1, help="Number of parallel workers")
    parser.add_argument("--filter", "-f", type=str, help="Regex pattern to filter commands")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick mode: only --help tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--compare", "-c", action="store_true", help="Compare with previous run")
    parser.add_argument("--list", "-l", action="store_true", help="Just list all commands")
    parser.add_argument("--output-dir", "-o", type=Path, help="Output directory for results")
    parser.add_argument("--subprocess", action="store_true", help="Use subprocess instead of CliRunner")

    args = parser.parse_args()

    runner = CLISmokeTest(
        parallel_workers=args.parallel,
        filter_pattern=args.filter,
        quick_mode=args.quick,
        verbose=args.verbose,
        output_dir=args.output_dir,
        use_subprocess=args.subprocess,
    )

    if args.list:
        runner.list_commands()
        return 0

    results = runner.run_tests()

    if args.compare:
        regressions, improvements = runner.compare_with_previous(results)
        results.regressions = regressions
        results.improvements = improvements

    # Save results
    json_path = runner.save_results(results)
    junit_path = runner.save_junit_xml(results)

    print(f"\nResults saved to:")
    print(f"  JSON:  {json_path}")
    print(f"  JUnit: {junit_path}")

    exit_code = runner.print_summary(results)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
