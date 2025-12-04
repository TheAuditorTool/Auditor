"""Detect peer dependency mismatches (database-first implementation)."""

import json
import sqlite3

from theauditor.indexer.schema import build_query
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="peer_conflicts",
    category="dependency",
    target_extensions=[".json"],
    exclude_patterns=["node_modules/", ".venv/", "test/"])


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect peer dependency version mismatches."""
    findings = []

    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        query = build_query(
            "package_configs",
            ["file_path", "package_name", "version", "peer_dependencies"],
            where="peer_dependencies IS NOT NULL",
        )
        cursor.execute(query)

        packages_with_peers = cursor.fetchall()

        installed_versions: dict[str, str] = {}
        query = build_query("package_configs", ["package_name", "version"])
        cursor.execute(query)
        for pkg_name, version in cursor.fetchall():
            if version:
                installed_versions[pkg_name] = version

        for file_path, _pkg_name, _version, peer_deps_json in packages_with_peers:
            if not peer_deps_json:
                continue

            try:
                peer_deps = json.loads(peer_deps_json)
                if not isinstance(peer_deps, dict):
                    continue

                for peer_name, peer_requirement in peer_deps.items():
                    if not peer_name or not peer_requirement:
                        continue

                    actual_version = installed_versions.get(peer_name)

                    if not actual_version:
                        findings.append(
                            StandardFinding(
                                file_path=file_path,
                                line=1,
                                rule_name="peer-dependency-missing",
                                message=f"Package '{pkg_name}' requires peer dependency '{peer_name}' ({peer_requirement}) but it is not installed",
                                severity=Severity.MEDIUM,
                                category="dependency",
                                snippet=f"{pkg_name} requires {peer_name}: {peer_requirement}",
                                cwe_id="CWE-1104",
                            )
                        )
                        continue

                    if _has_major_version_mismatch(peer_requirement, actual_version):
                        findings.append(
                            StandardFinding(
                                file_path=file_path,
                                line=1,
                                rule_name="peer-dependency-conflict",
                                message=f"Package '{pkg_name}' requires peer dependency '{peer_name}' {peer_requirement}, but version {actual_version} is installed",
                                severity=Severity.HIGH,
                                category="dependency",
                                snippet=f"{pkg_name} requires {peer_name} {peer_requirement} (installed: {actual_version})",
                                cwe_id="CWE-1104",
                            )
                        )

            except json.JSONDecodeError:
                continue

        conn.close()

    except sqlite3.Error:
        pass

    return findings


def _has_major_version_mismatch(requirement: str, actual: str) -> bool:
    """Check if requirement and actual version have major version mismatch."""
    try:
        req_clean = requirement.lstrip("^~<>=vV").split(".")[0]
        if req_clean in ("*", "x", "X", ""):
            return False

        req_major = int(req_clean)

        actual_clean = actual.lstrip("vV").split(".")[0]
        actual_major = int(actual_clean)

        if requirement.startswith("^") or requirement.startswith("~"):
            return actual_major != req_major
        elif requirement.startswith(">="):
            return actual_major < req_major
        elif requirement.startswith(">"):
            return actual_major <= req_major
        elif requirement.startswith("<="):
            return actual_major > req_major
        elif requirement.startswith("<"):
            return actual_major >= req_major
        else:
            return actual_major != req_major

    except (ValueError, IndexError):
        return False
