"""Parse and analyze project dependencies."""

import platform
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console
from theauditor.utils.constants import ExitCodes
from theauditor.utils.error_handler import handle_exceptions

IS_WINDOWS = platform.system() == "Windows"


@click.command(cls=RichCommand)
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--check-latest", is_flag=True, help="Check for latest versions from registries")
@click.option(
    "--upgrade-all", is_flag=True, help="YOLO mode: Update ALL packages to latest versions"
)
@click.option(
    "--upgrade-py", is_flag=True, help="Upgrade Python deps (requirements*.txt + pyproject.toml)"
)
@click.option("--upgrade-npm", is_flag=True, help="Upgrade npm deps (package.json files)")
@click.option(
    "--upgrade-docker",
    is_flag=True,
    help="Upgrade Docker images (docker-compose*.yml + Dockerfile)",
)
@click.option("--upgrade-cargo", is_flag=True, help="Upgrade Rust deps (Cargo.toml)")
@click.option(
    "--allow-prerelease", is_flag=True, help="Allow alpha/beta/rc versions (default: stable only)"
)
@click.option("--offline", is_flag=True, help="Force offline mode (no network)")
@click.option("--print-stats", is_flag=True, help="Print dependency statistics")
@click.option("--vuln-scan", is_flag=True, help="Scan dependencies for known vulnerabilities")
@click.option("--usage", default=None, help="Show usage examples for a package (e.g., 'axios', 'requests')")
def deps(
    root,
    check_latest,
    upgrade_all,
    upgrade_py,
    upgrade_npm,
    upgrade_docker,
    upgrade_cargo,
    allow_prerelease,
    offline,
    print_stats,
    vuln_scan,
    usage,
):
    """Analyze dependencies for vulnerabilities and updates.

    Comprehensive dependency analysis supporting Python (pip/poetry) and
    JavaScript/TypeScript (npm/yarn). Can check for outdated packages,
    known vulnerabilities, and selectively upgrade by ecosystem.

    Supported Files:
      - package.json / package-lock.json (npm/yarn)
      - pyproject.toml (Poetry/setuptools)
      - requirements.txt / requirements-*.txt (pip)
      - setup.py / setup.cfg (setuptools)
      - docker-compose*.yml / Dockerfile (Docker)
      - Cargo.toml (Rust)

    Operation Modes:
      Default:        Parse and inventory all dependencies
      --check-latest: Check for available updates (grouped by file)
      --vuln-scan:    Run security scanners (npm audit + OSV-Scanner)
      --upgrade-all:  YOLO mode - upgrade everything to latest

    Selective Upgrades (use after --check-latest to see what's outdated):
      --upgrade-py:     Only requirements*.txt + pyproject.toml
      --upgrade-npm:    Only package.json files
      --upgrade-docker: Only docker-compose*.yml + Dockerfile
      --upgrade-cargo:  Only Cargo.toml
      (Combine flags to upgrade multiple ecosystems)

    AI ASSISTANT CONTEXT:
      Purpose: Analyze dependencies for vulnerabilities, outdated packages, and upgrades
      Input: package.json, pyproject.toml, requirements.txt, Cargo.toml, Dockerfiles
      Output: Console or JSON (--json), findings stored in database
      Prerequisites: None (reads manifest files directly, no database required)
      Integration: Run standalone or as part of aud full pipeline

    EXAMPLES:
      aud deps                              # Basic dependency inventory
      aud deps --check-latest               # Check for outdated packages (grouped by file)
      aud deps --upgrade-py                 # Upgrade only Python dependencies
      aud deps --upgrade-py --upgrade-npm   # Upgrade Python and npm
      aud deps --vuln-scan                  # Security vulnerability scan
      aud deps --upgrade-all                # DANGEROUS: Upgrade everything
      aud deps --offline                    # Skip all network operations

    Vulnerability Scanning (--vuln-scan):
      - Runs 2 native tools: npm audit and OSV-Scanner
      - Cross-references findings for validation (confidence scoring)
      - Reports CVEs with severity levels
      - Exit code 2 for critical vulnerabilities
      - Requires: Run 'aud setup-ai --target .' first
      - Offline mode: Uses local OSV databases (faster, no rate limits)

    YOLO Mode (--upgrade-all):
      - Updates ALL packages to latest versions
      - Creates .bak files of originals
      - May break your project (that's the point!)

    Output:
      Data stored in database         # Query with aud query --findings
      Use --json for stdout output    # Pipe to file if needed

    Exit Codes:
      0 = Success
      2 = Critical vulnerabilities found (--vuln-scan)

    SEE ALSO:
      aud manual deps          Learn about dependency analysis
      aud manual dependencies  Package dependencies and vulnerability scanning

    Note: Respects proxy settings and npm/pip configurations."""
    import sys

    from theauditor.package_managers.deps import (
        check_latest_versions,
        generate_grouped_report,
        parse_dependencies,
        upgrade_all_deps,
    )
    from theauditor.vulnerability_scanner import format_vulnerability_report, scan_dependencies

    # Handle --usage flag: extract and display code snippets from cached docs
    if usage:
        _handle_usage_query(usage, root, offline)
        return

    deps_list = parse_dependencies(root_path=root)

    if not deps_list:
        console.print("No dependency files found (package.json, pyproject.toml, requirements.txt)")
        console.print("  Searched in: " + str(Path(root).resolve()), markup=False)
        return

    if vuln_scan:
        console.print("\n\\[SCAN] Running native vulnerability scanners...")
        console.print("  Using: npm audit, OSV-Scanner")
        if offline:
            console.print("  Mode: Offline (all tools use local data)")
        else:
            console.print("  Mode: Online registry checks (npm) + offline OSV database")
            console.print("        OSV-Scanner always uses local database (never hits API)")
        console.print("  Cross-referencing findings across 2 sources...")

        vulnerabilities = scan_dependencies(deps_list, offline=offline)

        if vulnerabilities:
            vuln_output = out.replace("deps.json", "vulnerabilities.json")

            report = format_vulnerability_report(vulnerabilities)
            console.print("\n" + report, markup=False)
            console.print(f"\nDetailed report written to {vuln_output}", highlight=False)

            critical_count = sum(1 for v in vulnerabilities if v["severity"] == "critical")
            if critical_count > 0:
                console.print(
                    f"\n\\[FAIL] Found {critical_count} CRITICAL vulnerabilities - failing build"
                )
                sys.exit(ExitCodes.CRITICAL_SEVERITY)
        else:
            console.print("  [success]No known vulnerabilities found in dependencies[/success]")

        return

    if upgrade_all and not offline:
        console.print("\\[YOLO MODE] Upgrading ALL packages to latest versions...")
        console.print("  [warning]This may break things. That's the point![/warning]")
        if allow_prerelease:
            console.print(
                "  [warning]Including alpha/beta/RC versions (--allow-prerelease)[/warning]"
            )

        latest_info = check_latest_versions(
            deps_list, allow_net=True, offline=offline, allow_prerelease=allow_prerelease
        )
        if not latest_info:
            console.print("  [error]Failed to fetch latest versions[/error]")
            return

        failed_checks = sum(1 for info in latest_info.values() if info.get("error") is not None)
        successful_checks = sum(
            1 for info in latest_info.values() if info.get("latest") is not None
        )

        if failed_checks > 0:
            console.print(
                f"\n  \\[WARN] {failed_checks} packages failed to check (will be skipped):"
            )

            errors = [
                (k.split(":")[1], v.get("error", "Unknown"))
                for k, v in latest_info.items()
                if v.get("error")
            ]
            for pkg, err in errors:
                console.print(f"     - {pkg}: {err}", highlight=False)
            console.print(
                f"  \\[OK] Proceeding with {successful_checks} packages that checked successfully"
            )

        upgraded = upgrade_all_deps(root_path=root, latest_info=latest_info, deps_list=deps_list)

        arrow = "->" if IS_WINDOWS else "->"

        # Print per-file details with package changes
        console.print("\n\\[UPGRADED] Files modified:")
        total_packages = 0
        total_files = 0

        for file_type, file_list in upgraded.items():
            if not file_list:
                continue
            for file_info in file_list:
                total_files += 1
                file_path = file_info.get("path", file_type)
                count = file_info.get("count", 0)
                changes = file_info.get("changes", [])
                total_packages += count

                console.print(f"\n  {file_path} ({count} packages):", highlight=False)

                # Sort changes alphabetically
                sorted_changes = sorted(changes, key=lambda x: x[0].lower())
                for name, old_ver, new_ver, delta in sorted_changes:
                    delta_marker = " [MAJOR]" if delta == "major" else ""
                    console.print(
                        f"    - {name}: {old_ver} {arrow} {new_ver}{delta_marker}",
                        highlight=False,
                    )

        if total_files == 0:
            console.print("  No files were modified (all packages up to date)")
        else:
            console.print(
                f"\n  Total: {total_packages} packages across {total_files} files",
                highlight=False,
            )

        console.print("\n\\[NEXT STEPS]:")
        console.print("  1. Run: pip install -r requirements.txt")
        console.print("  2. Or: npm install")
        console.print("  3. Pray it still works")
        return

    any_selective = upgrade_py or upgrade_npm or upgrade_docker or upgrade_cargo
    if any_selective and not offline:
        ecosystems = []
        if upgrade_py:
            ecosystems.append("py")
        if upgrade_npm:
            ecosystems.append("npm")
        if upgrade_docker:
            ecosystems.append("docker")
        if upgrade_cargo:
            ecosystems.append("cargo")

        ecosystem_names = {"py": "Python", "npm": "npm", "docker": "Docker", "cargo": "Cargo"}
        selected = ", ".join(ecosystem_names[e] for e in ecosystems)
        console.print(f"\\[SELECTIVE UPGRADE] Upgrading: {selected}", highlight=False)
        if allow_prerelease:
            console.print(
                "  [warning]Including alpha/beta/RC versions (--allow-prerelease)[/warning]"
            )

        filtered_deps = [d for d in deps_list if d["manager"] in ecosystems]

        if not filtered_deps:
            console.print("  \\[SKIP] No dependencies found for selected ecosystems")
            return

        console.print(f"  Found {len(filtered_deps)} dependencies to check", highlight=False)

        latest_info = check_latest_versions(
            filtered_deps, allow_net=True, offline=offline, allow_prerelease=allow_prerelease
        )
        if not latest_info:
            console.print("  [error]Failed to fetch latest versions[/error]")
            return

        failed_checks = sum(1 for info in latest_info.values() if info.get("error") is not None)
        successful_checks = sum(
            1 for info in latest_info.values() if info.get("latest") is not None
        )

        if failed_checks > 0:
            console.print(
                f"\n  \\[WARN] {failed_checks} packages failed to check (will be skipped):"
            )
            errors = [
                (k.split(":")[1], v.get("error", "Unknown"))
                for k, v in latest_info.items()
                if v.get("error")
            ]
            for pkg, err in errors[:5]:
                console.print(f"     - {pkg}: {err}", highlight=False)
            if failed_checks > 5:
                console.print(f"     ... and {failed_checks - 5} more", highlight=False)
            console.print(
                f"  \\[OK] Proceeding with {successful_checks} packages that checked successfully"
            )

        upgraded = upgrade_all_deps(
            root_path=root, latest_info=latest_info, deps_list=filtered_deps, ecosystems=ecosystems
        )

        arrow = "->" if IS_WINDOWS else "->"

        # Count total files modified
        total_files = sum(len(file_list) for file_list in upgraded.values())
        total_packages = sum(
            file_info.get("count", 0)
            for file_list in upgraded.values()
            for file_info in file_list
        )

        if total_files == 0:
            console.print(f"\n  \\[OK] All {selected} dependencies are already up to date!")
            return

        # Print per-file details with package changes
        console.print("\n\\[UPGRADED] Files modified:")

        for file_type, file_list in upgraded.items():
            if not file_list:
                continue
            for file_info in file_list:
                file_path = file_info.get("path", file_type)
                count = file_info.get("count", 0)
                changes = file_info.get("changes", [])

                console.print(f"\n  {file_path} ({count} packages):", highlight=False)

                # Sort changes alphabetically
                sorted_changes = sorted(changes, key=lambda x: x[0].lower())
                for name, old_ver, new_ver, delta in sorted_changes:
                    delta_marker = " [MAJOR]" if delta == "major" else ""
                    console.print(
                        f"    - {name}: {old_ver} {arrow} {new_ver}{delta_marker}",
                        highlight=False,
                    )

        console.print(
            f"\n  Total: {total_packages} packages across {total_files} files",
            highlight=False,
        )

        console.print("\n\\[NEXT STEPS]:")
        if upgrade_py:
            console.print("  - Run: pip install -r requirements.txt")
        if upgrade_npm:
            console.print("  - Run: npm install")
        if upgrade_cargo:
            console.print("  - Run: cargo build")
        if upgrade_docker:
            console.print("  - Run: docker-compose pull")
        return

    latest_info = {}
    if check_latest and not offline:
        unique_packages = {}
        for dep in deps_list:
            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
            if key not in unique_packages:
                unique_packages[key] = 0
            unique_packages[key] += 1

        console.print(f"Checking {len(deps_list)} dependencies for updates...", highlight=False)
        console.print(f"  Unique packages to check: {len(unique_packages)}", highlight=False)

        registries = []
        if any(d["manager"] == "npm" for d in deps_list):
            registries.append("npm registry")
        if any(d["manager"] == "py" for d in deps_list):
            registries.append("PyPI")
        if any(d["manager"] == "docker" for d in deps_list):
            registries.append("Docker Hub")

        if registries:
            console.print(f"  Connecting to: {', '.join(registries)}", highlight=False)
        latest_info = check_latest_versions(
            deps_list, allow_net=True, offline=offline, allow_prerelease=allow_prerelease
        )
        if latest_info:
            successful_checks = sum(
                1 for info in latest_info.values() if info.get("latest") is not None
            )
            failed_checks = sum(1 for info in latest_info.values() if info.get("error") is not None)

            console.print(
                f"  \\[OK] Checked {successful_checks}/{len(unique_packages)} unique packages"
            )
            if failed_checks > 0:
                console.print(f"  \\[WARN] {failed_checks} packages failed to check")

                errors = [
                    (k.split(":")[1], v["error"]) for k, v in latest_info.items() if v.get("error")
                ][:3]
                for pkg, err in errors:
                    console.print(f"     - {pkg}: {err}", highlight=False)
        else:
            console.print(
                "  [error]Failed to check versions (network issue or offline mode)[/error]"
            )

    npm_count = sum(1 for d in deps_list if d["manager"] == "npm")
    py_count = sum(1 for d in deps_list if d["manager"] == "py")
    docker_count = sum(1 for d in deps_list if d["manager"] == "docker")
    cargo_count = sum(1 for d in deps_list if d["manager"] == "cargo")

    console.print(f"  Total: {len(deps_list)} dependencies", highlight=False)
    if npm_count > 0:
        console.print(f"  Node/npm: {npm_count}", highlight=False)
    if py_count > 0:
        console.print(f"  Python: {py_count}", highlight=False)
    if docker_count > 0:
        console.print(f"  Docker: {docker_count}", highlight=False)
    if cargo_count > 0:
        console.print(f"  Cargo/Rust: {cargo_count}", highlight=False)

    if latest_info:
        generate_grouped_report(deps_list, latest_info, hide_up_to_date=True)

    if not check_latest and not upgrade_all:
        console.print("\nTIP: Run with --check-latest to check for outdated packages.")


# =============================================================================
# Usage Extractor Integration (Tasks 2.3, 2.4, 2.5)
# =============================================================================


def _detect_manager(package: str, docs_dir: Path) -> str | None:
    """Detect which package manager has cached docs for this package.

    Algorithm:
    1. If package starts with '@' -> npm only (scoped package)
    2. Otherwise check BOTH in priority order:
       a. npm first (larger ecosystem, more likely)
       b. py second
    3. Return first match found, or None if no cache exists

    Case sensitivity: Directory names are case-sensitive on Linux,
    but package names in cache use original casing from registry.
    """
    npm_dir = docs_dir / "npm"
    py_dir = docs_dir / "py"

    if package.startswith("@"):
        # Scoped packages are npm-only
        npm_pattern = package.replace("@", "_at_").replace("/", "_")
        if npm_dir.exists() and any(npm_dir.glob(f"{npm_pattern}@*")):
            return "npm"
        return None

    # Check npm first (larger ecosystem)
    if npm_dir.exists() and any(npm_dir.glob(f"{package}@*")):
        return "npm"
    # Then check Python
    if py_dir.exists() and any(py_dir.glob(f"{package}@*")):
        return "py"
    return None


def _handle_usage_query(package: str, root: str, offline: bool) -> None:
    """Handle --usage flag: extract and display code snippets as JSON."""
    from theauditor.package_managers.usage_extractor import UsageExtractor

    docs_dir = Path(root) / ".pf" / "context" / "docs"
    extractor = UsageExtractor(str(docs_dir))

    # Detect manager
    manager = _detect_manager(package, docs_dir)
    snippets = extractor.extract_usage(manager, package) if manager else []

    # Cache miss handling - try fetch if online
    if not snippets and not offline and manager is None:
        # Try to determine manager for fetch (default to npm for unknown)
        fetch_manager = "npm"
        from theauditor.package_managers.docs_fetch import fetch_docs

        fetch_docs(
            deps=[{"name": package, "version": "latest", "manager": fetch_manager}],
            offline=False,
        )
        # Retry detection and extraction
        manager = _detect_manager(package, docs_dir)
        if manager:
            snippets = extractor.extract_usage(manager, package)

    # Output JSON and write finding to database
    _output_usage_json(package, manager, snippets, root)


def _output_usage_json(package: str, manager: str | None, snippets: list, root: str) -> None:
    """Output snippets as JSON and write finding to database."""
    import json
    import sqlite3
    from datetime import UTC, datetime

    total = len(snippets)
    returned = min(10, total)

    output = {
        "package": package,
        "manager": manager,
        "snippets": [
            {
                "rank": i + 1,
                "score": s.score,
                "language": s.language,
                "content": s.content,
                "context": s.context,
                "source_file": s.source_file,
            }
            for i, s in enumerate(snippets[:returned])
        ],
        "total_found": total,
        "returned": returned,
    }

    if not snippets:
        output["error"] = f"No cached docs found for {package}"

    # Write finding to findings_consolidated
    db_path = Path(root) / ".pf" / "repo_index.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            if snippets:
                # Success finding - usage examples found
                message = f"Found {total} usage examples for {package} (top score: {snippets[0].score})"
                severity = "info"
            else:
                # Cache miss finding - no docs available
                message = f"No cached documentation found for package: {package}"
                severity = "low"

            cursor.execute(
                """INSERT INTO findings_consolidated
                   (file, line, rule, tool, message, severity, category, confidence, timestamp, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"package:{package}",  # file field stores package reference
                    0,
                    "USAGE_QUERY",
                    "usage-extractor",
                    message,
                    severity,
                    "documentation",
                    1.0,
                    datetime.now(UTC).isoformat(),
                    json.dumps(output),
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass  # Database write failure is non-fatal

    # Output JSON to stdout
    print(json.dumps(output, indent=2))
