"""Tool version detection and reporting."""
from __future__ import annotations


import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def detect_tool_version(cmd: list[str]) -> str:
    """
    Detect tool version by running command.

    Returns version string or "missing" if not found.
    """
    try:
        # Use temp files to avoid buffer overflow
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt', encoding='utf-8') as stdout_fp, \
             tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt', encoding='utf-8') as stderr_fp:
            
            stdout_path = stdout_fp.name
            stderr_path = stderr_fp.name
            
            result = subprocess.run(cmd, stdout=stdout_fp, stderr=stderr_fp, text=True, timeout=5, check=False)
        
        # Read the outputs back
        with open(stdout_path, encoding='utf-8') as f:
            result.stdout = f.read()
        with open(stderr_path, encoding='utf-8') as f:
            result.stderr = f.read()
        
        # Clean up temp files
        os.unlink(stdout_path)
        os.unlink(stderr_path)

        if result.returncode == 0:
            output = result.stdout.strip()
            # Extract version from common patterns
            # Handle formats like "ruff 0.1.0", "black, 23.1.0", "mypy 1.0.0", "Version 5.0.0"
            import re

            # Look for version patterns like x.y.z
            version_pattern = r"(\d+\.\d+(?:\.\d+)?)"
            match = re.search(version_pattern, output)
            if match:
                return match.group(1)

            # Fallback to simple version extraction
            parts = output.split()
            for part in parts:
                if any(c.isdigit() for c in part):
                    # Found version-like string
                    version = part.strip(",").strip()
                    # Clean up common prefixes
                    if version.startswith("v"):
                        version = version[1:]
                    return version

            return output.split()[0] if output else "unknown"
        return "missing"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "missing"


def write_tools_report(out_dir: str) -> dict[str, Any]:
    """
    Detect all tool versions and write reports.

    Writes:
    - {out_dir}/TOOLS.md - Human-readable markdown
    - {out_dir}/tools.json - Machine-readable JSON

    Returns the tools dictionary.
    """
    # Ensure output directory exists
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Detect Python tools
    python_tools = {
        "ruff": detect_tool_version(["ruff", "--version"]),
        "black": detect_tool_version(["black", "--version"]),
        "pytest": detect_tool_version(["pytest", "--version"]),
        "mypy": detect_tool_version(["mypy", "--version"]),
    }

    # Detect Node tools from TheAuditor's sandboxed environment
    # Check in .auditor_venv/.theauditor_tools/ for our bundled tools
    sandbox_base = Path(".auditor_venv/.theauditor_tools")
    
    # Try sandboxed tools first, fallback to system
    if sandbox_base.exists():
        # Use our sandboxed Node.js and tools
        node_exe = sandbox_base / "node-runtime" / ("node.exe" if os.name == "nt" else "bin/node")
        npx_exe = sandbox_base / "node-runtime" / ("npx.cmd" if os.name == "nt" else "bin/npx")
        
        if node_exe.exists() and npx_exe.exists():
            # Run npx from sandbox with proper paths
            node_tools = {
                "eslint": detect_tool_version([str(npx_exe), "--prefix", str(sandbox_base), "eslint", "--version"]),
                "typescript": detect_tool_version([str(npx_exe), "--prefix", str(sandbox_base), "tsc", "--version"]),
                "prettier": detect_tool_version([str(npx_exe), "--prefix", str(sandbox_base), "prettier", "--version"]),
            }
        else:
            # Sandbox exists but Node not found
            node_tools = {
                "eslint": "missing (sandbox incomplete)",
                "typescript": "missing (sandbox incomplete)", 
                "prettier": "missing (sandbox incomplete)",
            }
    else:
        # No sandbox, check system (fallback)
        node_tools = {
            "eslint": detect_tool_version(["npx", "eslint", "--version"]),
            "typescript": detect_tool_version(["npx", "tsc", "--version"]),
            "prettier": detect_tool_version(["npx", "prettier", "--version"]),
        }

    # Build report structure
    tools = {
        "python": python_tools,
        "node": node_tools,
    }

    # Write JSON (machine-readable)
    json_path = Path(out_dir) / "tools.json"
    with open(json_path, "w") as f:
        json.dump(tools, f, indent=2, sort_keys=True)

    # Write Markdown (human-readable)
    md_path = Path(out_dir) / "TOOLS.md"
    with open(md_path, "w") as f:
        f.write("# Tool Versions Report\n\n")

        f.write("## Python Tools\n\n")
        f.write("| Tool | Version |\n")
        f.write("|------|--------|\n")
        for tool, version in sorted(python_tools.items()):
            status = "[OK]" if version != "missing" else "[MISSING]"
            f.write(f"| {tool} | {status} {version} |\n")

        f.write("\n## Node Tools\n\n")
        f.write("| Tool | Version |\n")
        f.write("|------|--------|\n")
        for tool, version in sorted(node_tools.items()):
            status = "[OK]" if version != "missing" else "[MISSING]"
            f.write(f"| {tool} | {status} {version} |\n")

        f.write("\n---\n")
        f.write("*Generated by TheAuditor*\n")

    return tools
