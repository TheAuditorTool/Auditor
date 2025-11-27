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
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from typing import Literal

# Tool definitions: (command, version_flag, description)
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

        # Extract version pattern (x.y.z or x.y)
        match = re.search(r"(\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?)", output)
        if match:
            return match.group(1)

        # Fallback: find any version-like string
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

    # Python tools (always from system/venv)
    for name, (cmd, description) in PYTHON_TOOLS.items():
        version = detect_version(cmd)
        results["python"].append(ToolStatus(
            name=name,
            version=version,
            available=version is not None,
            description=description,
            source="system" if version else "missing",
        ))

    # Node tools (prefer sandbox, fallback to system)
    node_exe, npx_exe = get_sandbox_paths()
    sandbox_base = Path(".auditor_venv/.theauditor_tools")

    for name, (cmd, description) in NODE_TOOLS.items():
        version = None
        source: Literal["system", "sandbox", "missing"] = "missing"

        # Try sandbox first
        if npx_exe and name not in ("node", "npm"):
            sandbox_cmd = [str(npx_exe), "--prefix", str(sandbox_base)] + cmd[1:]
            version = detect_version(sandbox_cmd)
            if version:
                source = "sandbox"

        if node_exe and name == "node":
            version = detect_version([str(node_exe), "--version"])
            if version:
                source = "sandbox"

        # Fallback to system
        if not version:
            version = detect_version(cmd)
            if version:
                source = "system"

        results["node"].append(ToolStatus(
            name=name,
            version=version,
            available=version is not None,
            description=description,
            source=source,
        ))

    # Rust tools
    for name, (cmd, description) in RUST_TOOLS.items():
        version = detect_version(cmd)
        results["rust"].append(ToolStatus(
            name=name,
            version=version,
            available=version is not None,
            description=description,
            source="system" if version else "missing",
        ))

    return results


@click.group("tools", invoke_without_command=True)
@click.pass_context
def tools(ctx: click.Context) -> None:
    """Manage analysis tool dependencies.

    Detect, verify, and report on installed analysis tools including linters,
    security scanners, and language runtimes.

    \b
    SUBCOMMANDS:
      list    Show all tools and versions (default)
      check   Verify required tools are installed
      report  Generate version report files

    \b
    EXAMPLES:
      aud tools              # List all tools
      aud tools check        # Verify installation
      aud tools report       # Generate .pf/raw/tools.json
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(tools_list)


@tools.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--category", type=click.Choice(["python", "node", "rust", "all"]), default="all", help="Filter by category")
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
        click.echo(json.dumps(output, indent=2))
        return

    categories = [category] if category != "all" else ["python", "node", "rust"]

    for cat in categories:
        statuses = all_tools.get(cat, [])
        if not statuses:
            continue

        click.echo(f"\n{cat.upper()} TOOLS:")
        click.echo("-" * 50)

        for status in statuses:
            if status.available:
                icon = "[OK]"
                version_str = f"{status.version}"
                source_str = f"({status.source})" if status.source != "system" else ""
                click.echo(f"  {icon} {status.name:12} {version_str:12} {source_str}")
            else:
                click.echo(f"  [--] {status.name:12} not installed")

    click.echo()


@tools.command("check")
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

    # Default required tools
    core_required = {"python", "ruff", "node", "eslint"}
    if required:
        check_set = set(required)
    elif strict:
        check_set = {s.name for statuses in all_tools.values() for s in statuses}
    else:
        check_set = core_required

    # Flatten all tools
    all_statuses = {s.name: s for statuses in all_tools.values() for s in statuses}

    missing = []
    found = []

    for name in sorted(check_set):
        status = all_statuses.get(name)
        if status and status.available:
            found.append(name)
        else:
            missing.append(name)

    click.echo(f"Checking {len(check_set)} tools...\n")

    for name in found:
        status = all_statuses[name]
        click.echo(f"  [OK] {name}: {status.version}")

    for name in missing:
        click.echo(f"  [MISSING] {name}")

    click.echo()

    if missing:
        click.echo(f"FAILED: {len(missing)} required tool(s) missing")
        sys.exit(1)
    else:
        click.echo(f"PASSED: All {len(found)} required tools available")
        sys.exit(0)


@tools.command("report")
@click.option("--out-dir", default=".pf/raw", type=click.Path(), help="Output directory")
@click.option("--format", "fmt", type=click.Choice(["all", "json", "markdown"]), default="all", help="Output format")
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
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build JSON structure
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

    # Write JSON
    if fmt in ("all", "json"):
        json_path = out_path / "tools.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        click.echo(f"[OK] Written: {json_path}")

    # Write Markdown
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

        click.echo(f"[OK] Written: {md_path}")

    # Summary
    total = sum(len(s) for s in all_tools.values())
    available = sum(1 for statuses in all_tools.values() for s in statuses if s.available)
    click.echo(f"\nSummary: {available}/{total} tools available")
