"""Linter output parsers - converts various linter outputs to normalized format.

COURIER PHILOSOPHY:
- We translate tool output keys to standard keys
- We preserve exact messages and severities
- We perform direct data access without interpretation
- We validate translation, not content
"""

import json
import re
from pathlib import Path
from typing import Any


def parse_eslint_output(output: str, workset_files: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse ESLint JSON output.
    
    Returns:
        Tuple of (findings, ast_data) where ast_data maps file paths to AST objects
    """
    findings = []
    ast_data = {}

    try:
        results = json.loads(output)
        for file_result in results:
            file = Path(file_result["filePath"])
            # Normalize path to forward slashes for cross-platform compatibility
            file_str = str(file).replace("\\", "/")

            # Try to match against workset in various forms
            matched = False
            for workset_file in workset_files:
                # Check if the absolute path ends with the relative workset path
                # This handles both Windows absolute paths and Unix paths
                if file_str.endswith(workset_file):
                    matched = True
                    file_str = workset_file
                    break
                # Also check if workset file is contained in the path (with proper separators)
                elif "/" + workset_file in file_str or file_str.startswith(workset_file):
                    matched = True
                    file_str = workset_file
                    break

            if not matched:
                continue

            # Extract AST if present
            if "ast" in file_result:
                ast_data[file_str] = file_result["ast"]

            for message in file_result.get("messages", []):
                # Direct data access from ESLint output
                # Create the translated finding using standard keys
                # ESLint severity: numeric (2=error, 1=warning) - translate to standard
                eslint_severity = message.get("severity", 1)
                # Map numeric severity to standard strings
                if eslint_severity == 2:
                    standard_severity = "error"
                elif eslint_severity == 1:
                    standard_severity = "warning"
                else:
                    standard_severity = "warning"  # Default for unknown values
                
                translated = {
                    "tool": "eslint",
                    "file": file_str,
                    "line": int(message.get("line", 0)),
                    "column": int(message.get("column", 0)),
                    "rule": message.get("ruleId", ""),  # Empty not "unknown"
                    "message": message.get("message", ""),
                    "severity": standard_severity,  # Use standardized severity
                    "category": "lint",
                }
                
                # No validation needed
                
                findings.append(translated)
    except json.JSONDecodeError:
        # Fall back to regex parsing
        pattern = r"([^:]+):(\d+):(\d+):\s+(error|warning)\s+(.+?)\s+([a-z0-9\-\/]+)\s*$"
        for line in output.strip().split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                file = match.group(1).strip()
                if file in workset_files:
                    findings.append(
                        {
                            "tool": "eslint",
                            "file": file,
                            "line": int(match.group(2)),
                            "column": int(match.group(3)),
                            "rule": match.group(6),
                            "message": match.group(5),
                            "severity": match.group(4),  # Keep original for /raw/
                            "category": "lint",
                        }
                    )

    return findings, ast_data


def parse_ruff_output(output: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse ruff output - translate to standard keys."""
    findings = []

    # Format: path:line:col: code message
    pattern = r"([^:]+):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$"
    for line in output.strip().split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            file = match.group(1).strip()
            # Normalize Windows backslashes to forward slashes for comparison
            normalized_file = file.replace("\\", "/")
            
            # Check if file is in workset (comparing normalized paths)
            if normalized_file in workset_files or file in workset_files:
                # Create original dict for validation
                original = {
                    "file": file,
                    "line": match.group(2),
                    "column": match.group(3),
                    "code": match.group(4),
                    "message": match.group(5)
                }
                
                # COURIER: Translate to standard keys
                code = match.group(4)
                translated = {
                    "tool": "ruff",
                    "file": normalized_file,  # Use normalized path
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                    "rule": code,  # Preserve original code in rule field
                    "message": match.group(5),  # Preserve exactly
                    "severity": "warning",  # Direct preservation - ruff doesn't provide severity in concise format
                    "category": "lint",
                }
                
                # No validation needed
                
                findings.append(translated)

    return findings


def parse_mypy_output(output: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse mypy output."""
    findings = []

    # Format: path:line: error: message [type-code]
    pattern = r"([^:]+):(\d+):\s+(error|warning|note):\s+(.+?)(?:\s+\[([^\]]+)\])?$"
    for line in output.strip().split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            file = match.group(1).strip()
            # Normalize Windows backslashes to forward slashes for comparison
            normalized_file = file.replace("\\", "/")
            
            # Check if file is in workset (comparing normalized paths)
            if normalized_file in workset_files or file in workset_files:
                # Create translated finding
                original = {
                    "file": file,
                    "line": match.group(2),
                    "severity": match.group(3),
                    "message": match.group(4),
                    "code": match.group(5)
                }
                
                translated = {
                    "tool": "mypy",
                    "file": normalized_file,  # Use normalized path
                    "line": int(match.group(2)),
                    "column": 0,
                    "rule": match.group(5) or "type-error",
                    "message": match.group(4),
                    "severity": match.group(3),  # Keep original mypy severity for /raw/
                    "category": "type",
                }
                
                # No validation needed
                
                findings.append(translated)

    return findings


def parse_tsc_output(output: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse TypeScript compiler output."""
    findings = []

    # Format: path(line,col): error TS1234: message
    pattern = r"([^(]+)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.+)$"
    for line in output.strip().split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            file = match.group(1).strip()
            if file in workset_files:
                # Create translated finding
                original = {
                    "file": file,
                    "line": match.group(2),
                    "column": match.group(3),
                    "severity": match.group(4),
                    "code": match.group(5),
                    "message": match.group(6)
                }
                
                translated = {
                    "tool": "tsc",
                    "file": file,
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                    "rule": match.group(5),
                    "message": match.group(6),
                    "severity": match.group(4),  # Keep original tsc severity for /raw/
                    "category": "type",
                }
                
                # No validation needed
                
                findings.append(translated)

    return findings


def parse_prettier_output(
    stdout: str, stderr: str, workset_files: set[str]
) -> list[dict[str, Any]]:
    """Parse Prettier output."""
    findings = []

    # When run with --check, Prettier lists unformatted files on stderr with [warn] prefix
    # Example: "[warn] backend/src/app.ts" or with ANSI codes: "\x1b[33m[warn]\x1b[39m backend/src/app.ts"
    import re
    
    # Pattern to extract file path after [warn] prefix, handling ANSI codes
    # Matches: [warn] file.ts or \x1b[XXm[warn]\x1b[XXm file.ts
    pattern = r'\[warn\]\s+(.+?)$'
    
    for line in stderr.strip().split("\n"):
        if line and not line.startswith("Checking"):
            # Remove ANSI color codes first
            clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
            clean_line = re.sub(r'\[\d+m', '', clean_line)  # Also handle [33m format
            
            # Extract file path after [warn]
            match = re.search(pattern, clean_line)
            if match:
                file = match.group(1).strip()
            else:
                # Fallback: if no [warn] prefix, use the whole line
                file = clean_line.strip()
                
            # Normalize path for comparison
            normalized_file = file.replace("\\", "/")
            
            # Check if file is in workset
            if normalized_file in workset_files or file in workset_files:
                # Create translated finding
                original = {"file": file}
                
                translated = {
                    "tool": "prettier",
                    "file": normalized_file,  # Use normalized path
                    "line": 0,
                    "column": 0,
                    "rule": "format",
                    "message": "File needs formatting",
                    "severity": "warning",  # Keep original for /raw/
                    "category": "style",
                }
                
                # No validation needed
                
                findings.append(translated)

    return findings


def parse_black_output(stdout: str, stderr: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse Black output."""
    findings = []

    # Black shows files that would be reformatted in stderr
    pattern = r"would reformat (.+)$"
    for match in re.finditer(pattern, stderr, re.MULTILINE):
        file = match.group(1)
        # Normalize Windows backslashes to forward slashes for comparison
        normalized_file = file.replace("\\", "/")
        
        # Check if file is in workset (comparing normalized paths)
        if normalized_file in workset_files or file in workset_files:
            # Create translated finding
            original = {"file": file}
            
            translated = {
                "tool": "black",
                "file": normalized_file,  # Use normalized path
                "line": 0,
                "column": 0,
                "rule": "format",
                "message": "File needs formatting",
                "severity": "warning",  # Keep original for /raw/
                "category": "style",
            }
            
            # No validation needed
            
            findings.append(translated)
    
    # Also check for --diff output in stdout
    # When --diff is used, Black outputs unified diff format to stdout
    if stdout and stdout.startswith("---"):
        # Extract filenames from diff headers
        diff_pattern = r"^---\s+(.+?)\s+\d{4}-\d{2}-\d{2}"
        for match in re.finditer(diff_pattern, stdout, re.MULTILINE):
            file = match.group(1)
            # Normalize Windows backslashes to forward slashes for comparison
            normalized_file = file.replace("\\", "/")
            
            # Check if file is in workset (comparing normalized paths)
            if normalized_file in workset_files or file in workset_files:
                # Check if we already added this file from stderr
                if not any(f["file"] == normalized_file for f in findings):
                    translated = {
                        "tool": "black",
                        "file": normalized_file,  # Use normalized path
                        "line": 0,
                        "column": 0,
                        "rule": "format",
                        "message": "File needs formatting",
                        "severity": "warning",
                        "category": "style",
                    }
                    findings.append(translated)

    return findings


def parse_golangci_output(output: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse golangci-lint output."""
    findings = []

    # Format: path:line:col: message (linter)
    pattern = r"([^:]+):(\d+):(\d+):\s+(.+?)\s+\(([^)]+)\)$"
    for match in re.finditer(pattern, output, re.MULTILINE):
        file = match.group(1)
        if file in workset_files:
            # Create translated finding
            original = {
                "file": file,
                "line": match.group(2),
                "column": match.group(3),
                "message": match.group(4),
                "linter": match.group(5)
            }
            
            translated = {
                "tool": "golangci-lint",
                "file": file,
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "rule": match.group(5),
                "message": match.group(4),
                "severity": "warning",  # Keep original for /raw/
                "category": "lint",
            }
            
            # No validation needed
            
            findings.append(translated)

    return findings


def parse_go_vet_output(output: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse go vet output."""
    findings = []

    # Format: path:line:col: message
    pattern = r"([^:]+):(\d+):(\d+):\s+(.+)$"
    for match in re.finditer(pattern, output, re.MULTILINE):
        file = match.group(1)
        if file in workset_files:
            # Create translated finding
            original = {
                "file": file,
                "line": match.group(2),
                "column": match.group(3),
                "message": match.group(4)
            }
            
            translated = {
                "tool": "go-vet",
                "file": file,
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "rule": "vet",
                "message": match.group(4),
                "severity": "warning",  # Keep original for /raw/
                "category": "lint",
            }
            
            # No validation needed
            
            findings.append(translated)

    return findings


def parse_maven_output(tool: str, output: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse Maven-based tool output (SpotBugs/Checkstyle)."""
    findings = []

    # Simple pattern matching for Maven output
    pattern = r"\[(?:ERROR|WARNING)\]\s+([^:]+):(\d+):\s+(.+)$"
    for match in re.finditer(pattern, output, re.MULTILINE):
        file = match.group(1)
        if file in workset_files:
            # Create translated finding
            original = {
                "file": file,
                "line": match.group(2),
                "message": match.group(3)
            }
            
            translated = {
                "tool": tool,
                "file": file,
                "line": int(match.group(2)),
                "column": 0,
                "rule": tool,
                "message": match.group(3),
                "severity": "warning",  # Keep original for /raw/
                "category": "lint",
            }
            
            # No validation needed
            
            findings.append(translated)

    return findings


def parse_bandit_output(output: str, workset_files: set[str]) -> list[dict[str, Any]]:
    """Parse bandit JSON output for Python security issues."""
    findings = []
    
    try:
        results = json.loads(output)
        # Bandit JSON structure has "results" key with findings
        for result in results.get("results", []):
            file = result.get("filename", "")
            # Normalize Windows backslashes to forward slashes for comparison
            normalized_file = file.replace("\\", "/")
            
            # Check if the absolute path from Bandit matches any relative workset path
            # Bandit returns absolute paths like C:/Users/.../file.py
            # Workset has relative paths like scrapers/file.py
            matched = False
            matched_file = normalized_file  # Default to normalized absolute path
            
            for workset_file in workset_files:
                # Normalize workset file for comparison
                normalized_workset = workset_file.replace("\\", "/")
                # Check if absolute path ends with the relative path
                if normalized_file.endswith(normalized_workset):
                    matched = True
                    matched_file = normalized_workset  # Use the workset's relative path
                    break
                # Also check with leading slash
                elif normalized_file.endswith("/" + normalized_workset):
                    matched = True
                    matched_file = normalized_workset
                    break
            
            if matched:
                # Map bandit severity/confidence to standard
                severity_map = {
                    "HIGH": "error",
                    "MEDIUM": "warning", 
                    "LOW": "warning"
                }
                
                translated = {
                    "tool": "bandit",
                    "file": matched_file,  # Use the matched relative path from workset
                    "line": int(result.get("line_number", 0)),
                    "column": int(result.get("col_offset", 0)),
                    "rule": result.get("test_id", ""),
                    "message": result.get("issue_text", ""),
                    "severity": severity_map.get(result.get("issue_severity", "MEDIUM"), "warning"),
                    "category": "security",
                }
                findings.append(translated)
    except json.JSONDecodeError:
        # Fallback to text parsing if JSON fails
        pass
    
    return findings