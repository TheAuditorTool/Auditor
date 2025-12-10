"""Tool detection, verification, and reporting.

Provides `aud tools` command group for managing analysis tool dependencies.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console

if TYPE_CHECKING:
    from typing import Literal


PYTHON_TOOLS: dict[str, tuple[list[str], str]] = {
    "python": (["python", "--version"], "Python interpreter"),
    "ruff": (["ruff", "--version"], "Fast Python linter"),
    "mypy": (["mypy", "--version"], "Static type checker"),
    "pytest": (["pytest", "--version"], "Test framework"),
    "bandit": (["bandit", "--version"], "Security linter"),
    "semgrep": (["semgrep", "--version"], "Semantic code analysis"),
}

NODE_TOOLS: dict[str, tuple[list[str], str]] = {
    "node": (["node", "--version"], "Node.js runtime"),
    "npm": (["npm", "--version"], "Package manager"),
    "eslint": (["npx", "eslint", "--version"], "JavaScript linter"),
    "typescript": (["npx", "tsc", "--version"], "TypeScript compiler"),
    "prettier": (["npx", "prettier", "--version"], "Code formatter"),
}

RUST_TOOLS: dict[str, tuple[list[str], str]] = {
    "cargo": (["cargo", "--version"], "Rust package manager"),
    "tree-sitter": (["tree-sitter", "--version"], "Parser generator"),
}


@dataclass
class ToolStatus:
    """Status of a single tool."""

    name: str
    version: str | None
    available: bool
    description: str
    source: Literal["system", "sandbox", "missing"]

    @property
    def display_version(self) -> str:
        """Version string for display."""
        if not self.available:
            return "not installed"
        return self.version or "unknown"


def detect_version(cmd: list[str], timeout: int = 5) -> str | None:
    """Run a version command and extract the version number."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            return None

        output = result.stdout.strip() or result.stderr.strip()
        if not output:
            return None

        match = re.search(r"(\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?)", output)
        if match:
            return match.group(1)

        for part in output.split():
            part = part.strip("(),v")
            if re.match(r"\d+\.\d+", part):
                return part

        return output.split()[0] if output else None

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def get_sandbox_paths() -> tuple[Path | None, Path | None]:
    """Get paths to sandboxed Node.js tools if available."""
    sandbox_base = Path(".auditor_venv/.theauditor_tools")
    if not sandbox_base.exists():
        return None, None

    if os.name == "nt":
        node_exe = sandbox_base / "node-runtime" / "node.exe"
        npx_exe = sandbox_base / "node-runtime" / "npx.cmd"
    else:
        node_exe = sandbox_base / "node-runtime" / "bin" / "node"
        npx_exe = sandbox_base / "node-runtime" / "bin" / "npx"

    if node_exe.exists() and npx_exe.exists():
        return node_exe, npx_exe
    return None, None


def detect_all_tools() -> dict[str, list[ToolStatus]]:
    """Detect all tools and their versions."""
    results: dict[str, list[ToolStatus]] = {
        "python": [],
        "node": [],
        "rust": [],
    }

    for name, (cmd, description) in PYTHON_TOOLS.items():
        version = detect_version(cmd)
        results["python"].append(
            ToolStatus(
                name=name,
                version=version,
                available=version is not None,
                description=description,
                source="system" if version else "missing",
            )
        )

    node_exe, npx_exe = get_sandbox_paths()
    sandbox_base = Path(".auditor_venv/.theauditor_tools")

    for name, (cmd, description) in NODE_TOOLS.items():
        version = None
        source: Literal["system", "sandbox", "missing"] = "missing"

        if npx_exe and name not in ("node", "npm"):
            sandbox_cmd = [str(npx_exe), "--prefix", str(sandbox_base)] + cmd[1:]
            version = detect_version(sandbox_cmd)
            if version:
                source = "sandbox"

        if node_exe and name == "node":
            version = detect_version([str(node_exe), "--version"])
            if version:
                source = "sandbox"

        if not version:
            version = detect_version(cmd)
            if version:
                source = "system"

        results["node"].append(
            ToolStatus(
                name=name,
                version=version,
                available=version is not None,
                description=description,
                source=source,
            )
        )

    for name, (cmd, description) in RUST_TOOLS.items():
        version = detect_version(cmd)
        results["rust"].append(
            ToolStatus(
                name=name,
                version=version,
                available=version is not None,
                description=description,
                source="system" if version else "missing",
            )
        )

    return results


@click.group("tools", cls=RichGroup, invoke_without_command=True)
@click.pass_context
def tools(ctx: click.Context) -> None:
    """Manage analysis tool dependencies.

    Detect, verify, and report on installed analysis tools including linters,
    security scanners, and language runtimes.

    AI ASSISTANT CONTEXT:
      Purpose: Detect and verify installed analysis tools (linters, runtimes, scanners)
      Input: System PATH, .auditor_venv sandbox
      Output: Console (table) or JSON (--json flag)
      Prerequisites: None (reads system state directly)
      Integration: Run before aud full to verify toolchain, or after setup-ai

    \b
    SUBCOMMANDS:
      list    Show all tools and versions (default)
      check   Verify required tools are installed
      report  Generate version report files

    \b
    EXAMPLES:
      aud tools              # List all tools
      aud tools check        # Verify installation
      aud tools report --json # JSON version report to stdout

    SEE ALSO:
      aud manual tools   Learn about analysis tool dependencies
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(tools_list)


@tools.command("list", cls=RichCommand)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option(
    "--category",
    type=click.Choice(["python", "node", "rust", "all"]),
    default="all",
    help="Filter by category",
)
def tools_list(as_json: bool, category: str) -> None:
    """Show all tools and their versions.

    Displays installed analysis tools with version information and
    installation source (system or sandbox).
    """
    all_tools = detect_all_tools()

    if as_json:
        output = {}
        for cat, statuses in all_tools.items():
            if category != "all" and cat != category:
                continue
            output[cat] = {s.name: {"version": s.version, "source": s.source} for s in statuses}
        console.print(json.dumps(output, indent=2), markup=False)
        return

    categories = [category] if category != "all" else ["python", "node", "rust"]

    for cat in categories:
        statuses = all_tools.get(cat, [])
        if not statuses:
            continue

        console.print(f"\n{cat.upper()} TOOLS:", highlight=False)
        console.rule()

        for status in statuses:
            if status.available:
                icon = "[OK]"
                version_str = f"{status.version}"
                source_str = f"({status.source})" if status.source != "system" else ""
                console.print(
                    f"  {icon} {status.name:12} {version_str:12} {source_str}", highlight=False
                )
            else:
                console.print(f"  \\[--] {status.name:12} not installed", highlight=False)

    console.print()


@tools.command("check", cls=RichCommand)
@click.option("--strict", is_flag=True, help="Fail if any tool is missing")
@click.option("--required", multiple=True, help="Specific tools to require (can be repeated)")
def tools_check(strict: bool, required: tuple[str, ...]) -> None:
    """Verify required tools are installed.

    Returns exit code 0 if all required tools are available, 1 otherwise.
    By default, only checks core tools (python, ruff, node, eslint).

    \b
    EXAMPLES:
      aud tools check                    # Check core tools
      aud tools check --strict           # Fail if ANY tool missing
      aud tools check --required semgrep # Require specific tool
    """
    all_tools = detect_all_tools()

    core_required = {"python", "ruff", "node", "eslint"}
    if required:
        check_set = set(required)
    elif strict:
        check_set = {s.name for statuses in all_tools.values() for s in statuses}
    else:
        check_set = core_required

    all_statuses = {s.name: s for statuses in all_tools.values() for s in statuses}

    missing = []
    found = []

    for name in sorted(check_set):
        status = all_statuses.get(name)
        if status and status.available:
            found.append(name)
        else:
            missing.append(name)

    console.print(f"Checking {len(check_set)} tools...\n", highlight=False)

    for name in found:
        status = all_statuses[name]
        console.print(f"  \\[OK] {name}: {status.version}")

    for name in missing:
        console.print(f"  \\[MISSING] {name}", highlight=False)

    console.print()

    if missing:
        console.print(f"FAILED: {len(missing)} required tool(s) missing", highlight=False)
        sys.exit(1)
    else:
        console.print(f"PASSED: All {len(found)} required tools available", highlight=False)
        sys.exit(0)


@tools.command("report", cls=RichCommand)
@click.option("--out-dir", required=True, type=click.Path(), help="Output directory (required)")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["all", "json", "markdown"]),
    default="all",
    help="Output format",
)
def tools_report(out_dir: str, fmt: str) -> None:
    """Generate tool version report files.

    Creates machine-readable (JSON) and human-readable (Markdown) reports
    of all detected tool versions.

    \b
    OUTPUT FILES:
      {out_dir}/tools.json   Machine-readable version data
      {out_dir}/TOOLS.md     Human-readable report
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    all_tools = detect_all_tools()
    timestamp = datetime.now(UTC).isoformat()

    json_data = {
        "generated_at": timestamp,
        "tools": {},
    }

    for category, statuses in all_tools.items():
        json_data["tools"][category] = {}
        for status in statuses:
            json_data["tools"][category][status.name] = {
                "version": status.version,
                "available": status.available,
                "source": status.source,
            }

    if fmt in ("all", "json"):
        json_path = out_path / "tools.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        console.print(f"[success]Written: {json_path}[/success]")

    if fmt in ("all", "markdown"):
        md_path = out_path / "TOOLS.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Tool Versions Report\n\n")
            f.write(f"Generated: {timestamp}\n\n")

            for category, statuses in all_tools.items():
                f.write(f"## {category.title()} Tools\n\n")
                f.write("| Tool | Version | Status | Source |\n")
                f.write("|------|---------|--------|--------|\n")

                for status in statuses:
                    icon = "OK" if status.available else "MISSING"
                    version = status.version or "-"
                    f.write(f"| {status.name} | {version} | {icon} | {status.source} |\n")

                f.write("\n")

            f.write("---\n")
            f.write("*Generated by TheAuditor*\n")

        console.print(f"[success]Written: {md_path}[/success]")

    total = sum(len(s) for s in all_tools.values())
    available = sum(1 for statuses in all_tools.values() for s in statuses if s.available)
    console.print(f"\nSummary: {available}/{total} tools available", highlight=False)
