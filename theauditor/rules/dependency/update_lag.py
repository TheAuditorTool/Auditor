"""Detect severely outdated dependencies using existing version check data."""

import json
import sqlite3
from pathlib import Path

from theauditor.indexer.schema import build_query
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="update_lag",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/"])


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect severely outdated dependencies from deps_latest.json."""
    findings = []

    deps_latest_path = Path(".pf/raw/deps_latest.json")
    if not deps_latest_path.exists():
        return findings

    try:
        with open(deps_latest_path, encoding="utf-8") as f:
            latest_info = json.load(f)

        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        query = build_query("package_configs", ["file_path", "package_name", "version"])
        cursor.execute(query)

        package_files = {}
        for file_path, pkg_name, _version in cursor.fetchall():
            if "package.json" in file_path:
                key = f"npm:{pkg_name}"
            elif "requirements.txt" in file_path or "pyproject.toml" in file_path:
                key = f"py:{pkg_name}"
            else:
                key = f"unknown:{pkg_name}"

            package_files[key] = file_path

        conn.close()

        for key, info in latest_info.items():
            if info.get("error"):
                continue

            if not info.get("is_outdated", False):
                continue

            delta = info.get("delta", "")
            locked = info.get("locked", "")
            latest = info.get("latest", "")

            if delta == "major":
                parts = key.split(":", 1)
                if len(parts) != 2:
                    continue

                manager, pkg_name = parts
                file_path = package_files.get(
                    key, "package.json" if manager == "npm" else "requirements.txt"
                )

                try:
                    locked_major = int(locked.split(".")[0].lstrip("v^~<>="))
                    latest_major = int(latest.split(".")[0].lstrip("v^~<>="))
                    versions_behind = latest_major - locked_major

                    if versions_behind >= 2:
                        severity = Severity.MEDIUM if versions_behind == 2 else Severity.HIGH

                        findings.append(
                            StandardFinding(
                                file_path=file_path,
                                line=1,
                                rule_name="update_lag",
                                message=f"Dependency '{pkg_name}' is {versions_behind} major versions behind (using {locked}, latest is {latest})",
                                severity=severity,
                                category="dependency",
                                snippet=f"{pkg_name}: {locked} (latest: {latest})",
                                cwe_id="CWE-1104",
                            )
                        )
                except (ValueError, IndexError):
                    continue

    except (json.JSONDecodeError, OSError, sqlite3.Error):
        pass

    return findings
