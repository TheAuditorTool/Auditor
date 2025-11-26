"""Parse and analyze project dependencies."""


import platform
from pathlib import Path
import click
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"


@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--check-latest", is_flag=True, help="Check for latest versions from registries")
@click.option("--upgrade-all", is_flag=True, help="YOLO mode: Update ALL packages to latest versions")
@click.option("--upgrade-py", is_flag=True, help="Upgrade Python deps (requirements*.txt + pyproject.toml)")
@click.option("--upgrade-npm", is_flag=True, help="Upgrade npm deps (package.json files)")
@click.option("--upgrade-docker", is_flag=True, help="Upgrade Docker images (docker-compose*.yml + Dockerfile)")
@click.option("--upgrade-cargo", is_flag=True, help="Upgrade Rust deps (Cargo.toml)")
@click.option("--allow-prerelease", is_flag=True, help="Allow alpha/beta/rc versions (default: stable only)")
@click.option("--offline", is_flag=True, help="Force offline mode (no network)")
@click.option("--out", default="./.pf/raw/deps.json", help="Output dependencies file")
@click.option("--print-stats", is_flag=True, help="Print dependency statistics")
@click.option("--vuln-scan", is_flag=True, help="Scan dependencies for known vulnerabilities")
def deps(root, check_latest, upgrade_all, upgrade_py, upgrade_npm, upgrade_docker, upgrade_cargo,
         allow_prerelease, offline, out, print_stats, vuln_scan):
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

    Examples:
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

    Output Files:
      .pf/raw/deps.json               # Dependency inventory
      .pf/raw/deps_latest.json        # Latest version info
      .pf/raw/vulnerabilities.json    # Security findings

    Exit Codes:
      0 = Success
      2 = Critical vulnerabilities found (--vuln-scan)

    Note: Respects proxy settings and npm/pip configurations."""
    from theauditor.deps import parse_dependencies, write_deps_json, check_latest_versions, write_deps_latest_json, upgrade_all_deps, generate_grouped_report
    from theauditor.vulnerability_scanner import scan_dependencies, format_vulnerability_report
    import sys

    # Parse dependencies
    deps_list = parse_dependencies(root_path=root)

    if not deps_list:
        click.echo("No dependency files found (package.json, pyproject.toml, requirements.txt)")
        click.echo("  Searched in: " + str(Path(root).resolve()))
        return

    write_deps_json(deps_list, output_path=out)

    # Vulnerability scanning
    if vuln_scan:
        click.echo(f"\n[SCAN] Running native vulnerability scanners...")
        click.echo(f"  Using: npm audit, OSV-Scanner")
        if offline:
            click.echo(f"  Mode: Offline (all tools use local data)")
        else:
            click.echo(f"  Mode: Online registry checks (npm) + offline OSV database")
            click.echo(f"        OSV-Scanner always uses local database (never hits API)")
        click.echo(f"  Cross-referencing findings across 2 sources...")

        vulnerabilities = scan_dependencies(deps_list, offline=offline)

        if vulnerabilities:
            # JSON report already written by scanner (with tool_status)
            vuln_output = out.replace("deps.json", "vulnerabilities.json")

            # Display human-readable report
            report = format_vulnerability_report(vulnerabilities)
            click.echo("\n" + report)
            click.echo(f"\nDetailed report written to {vuln_output}")

            # Exit with error code if critical vulnerabilities found
            critical_count = sum(1 for v in vulnerabilities if v["severity"] == "critical")
            if critical_count > 0:
                click.echo(f"\n[FAIL] Found {critical_count} CRITICAL vulnerabilities - failing build")
                sys.exit(ExitCodes.CRITICAL_SEVERITY)
        else:
            click.echo(f"  [OK] No known vulnerabilities found in dependencies")

        # Don't continue with other operations after vuln scan
        return

    # YOLO MODE: Upgrade all to latest
    if upgrade_all and not offline:
        click.echo("[YOLO MODE] Upgrading ALL packages to latest versions...")
        click.echo("  [WARN] This may break things. That's the point!")
        if allow_prerelease:
            click.echo("  [WARN] Including alpha/beta/RC versions (--allow-prerelease)")

        # Get latest versions
        latest_info = check_latest_versions(deps_list, allow_net=True, offline=offline, allow_prerelease=allow_prerelease)
        if not latest_info:
            click.echo("  [FAIL] Failed to fetch latest versions")
            return

        # Check if all packages were successfully checked
        failed_checks = sum(1 for info in latest_info.values() if info.get("error") is not None)
        successful_checks = sum(1 for info in latest_info.values() if info.get("latest") is not None)

        if failed_checks > 0:
            click.echo(f"\n  [WARN] {failed_checks} packages failed to check (will be skipped):")
            # Show which packages failed and why
            errors = [(k.split(":")[1], v.get("error", "Unknown")) for k, v in latest_info.items() if v.get("error")]
            for pkg, err in errors:
                click.echo(f"     - {pkg}: {err}")
            click.echo(f"  [OK] Proceeding with {successful_checks} packages that checked successfully")

        # Upgrade all dependency files
        upgraded = upgrade_all_deps(root_path=root, latest_info=latest_info, deps_list=deps_list)

        # Count unique packages that were upgraded
        unique_upgraded = len([1 for k, v in latest_info.items() if v.get("is_outdated", False)])
        total_updated = sum(upgraded.values())

        click.echo(f"\n[UPGRADED] Dependency files:")
        for file_type, count in upgraded.items():
            if count > 0:
                click.echo(f"  [OK] {file_type}: {count} dependency entries updated")

        # Show what was actually upgraded
        click.echo(f"\n[CHANGES] Packages upgraded:")
        upgraded_packages = [
            (k.split(":")[1], v["locked"], v["latest"], v.get("delta", ""))
            for k, v in latest_info.items()
            if v.get("is_outdated", False) and v.get("latest") is not None
        ]

        # Sort by package name for consistent output
        upgraded_packages.sort(key=lambda x: x[0].lower())

        # Show ALL upgrades with details (no truncation)
        for name, old_ver, new_ver, delta in upgraded_packages:
            delta_marker = " [MAJOR]" if delta == "major" else ""
            # Use arrow character that works on Windows
            arrow = "->" if IS_WINDOWS else "→"
            click.echo(f"  - {name}: {old_ver} {arrow} {new_ver}{delta_marker}")

        # Show summary that matches the "Outdated: 10/29" format
        if total_updated > unique_upgraded:
            click.echo(f"\n  Summary: {unique_upgraded} unique packages updated across {total_updated} occurrences")

        click.echo("\n[NEXT STEPS]:")
        click.echo("  1. Run: pip install -r requirements.txt")
        click.echo("  2. Or: npm install")
        click.echo("  3. Pray it still works")
        return

    # SELECTIVE UPGRADE MODE: Upgrade specific ecosystems only
    any_selective = upgrade_py or upgrade_npm or upgrade_docker or upgrade_cargo
    if any_selective and not offline:
        # Build list of ecosystems to upgrade
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
        click.echo(f"[SELECTIVE UPGRADE] Upgrading: {selected}")
        if allow_prerelease:
            click.echo("  [WARN] Including alpha/beta/RC versions (--allow-prerelease)")

        # Filter deps to only selected ecosystems
        filtered_deps = [d for d in deps_list if d["manager"] in ecosystems]

        if not filtered_deps:
            click.echo(f"  [SKIP] No dependencies found for selected ecosystems")
            return

        click.echo(f"  Found {len(filtered_deps)} dependencies to check")

        # Get latest versions for filtered deps only
        latest_info = check_latest_versions(filtered_deps, allow_net=True, offline=offline, allow_prerelease=allow_prerelease)
        if not latest_info:
            click.echo("  [FAIL] Failed to fetch latest versions")
            return

        # Check if all packages were successfully checked
        failed_checks = sum(1 for info in latest_info.values() if info.get("error") is not None)
        successful_checks = sum(1 for info in latest_info.values() if info.get("latest") is not None)

        if failed_checks > 0:
            click.echo(f"\n  [WARN] {failed_checks} packages failed to check (will be skipped):")
            errors = [(k.split(":")[1], v.get("error", "Unknown")) for k, v in latest_info.items() if v.get("error")]
            for pkg, err in errors[:5]:  # Show first 5
                click.echo(f"     - {pkg}: {err}")
            if failed_checks > 5:
                click.echo(f"     ... and {failed_checks - 5} more")
            click.echo(f"  [OK] Proceeding with {successful_checks} packages that checked successfully")

        # Upgrade only selected ecosystems
        upgraded = upgrade_all_deps(root_path=root, latest_info=latest_info, deps_list=filtered_deps, ecosystems=ecosystems)

        # Count unique packages that were upgraded
        unique_upgraded = len([1 for k, v in latest_info.items() if v.get("is_outdated", False)])
        total_updated = sum(upgraded.values())

        if total_updated == 0:
            click.echo(f"\n  [OK] All {selected} dependencies are already up to date!")
            return

        click.echo(f"\n[UPGRADED] Dependency files:")
        for file_type, count in upgraded.items():
            if count > 0:
                click.echo(f"  [OK] {file_type}: {count} dependency entries updated")

        # Show what was actually upgraded
        click.echo(f"\n[CHANGES] Packages upgraded:")
        upgraded_packages = [
            (k.split(":")[1], v["locked"], v["latest"], v.get("delta", ""))
            for k, v in latest_info.items()
            if v.get("is_outdated", False) and v.get("latest") is not None
        ]
        upgraded_packages.sort(key=lambda x: x[0].lower())

        for name, old_ver, new_ver, delta in upgraded_packages:
            delta_marker = " [MAJOR]" if delta == "major" else ""
            arrow = "->" if IS_WINDOWS else "->"
            click.echo(f"  - {name}: {old_ver} {arrow} {new_ver}{delta_marker}")

        if total_updated > unique_upgraded:
            click.echo(f"\n  Summary: {unique_upgraded} unique packages updated across {total_updated} occurrences")

        # Ecosystem-specific next steps
        click.echo("\n[NEXT STEPS]:")
        if upgrade_py:
            click.echo("  - Run: pip install -r requirements.txt")
        if upgrade_npm:
            click.echo("  - Run: npm install")
        if upgrade_cargo:
            click.echo("  - Run: cargo build")
        if upgrade_docker:
            click.echo("  - Run: docker-compose pull")
        return

    # Check latest versions if requested
    latest_info = {}
    if check_latest and not offline:
        # Count unique packages first (by manager:name:version - Universal Keys)
        unique_packages = {}
        for dep in deps_list:
            # UNIVERSAL KEY: Include version for ALL managers (Tweak 2)
            key = f"{dep['manager']}:{dep['name']}:{dep.get('version', '')}"
            if key not in unique_packages:
                unique_packages[key] = 0
            unique_packages[key] += 1

        click.echo(f"Checking {len(deps_list)} dependencies for updates...")
        click.echo(f"  Unique packages to check: {len(unique_packages)}")

        # Show which registries we're connecting to
        registries = []
        if any(d['manager'] == 'npm' for d in deps_list):
            registries.append("npm registry")
        if any(d['manager'] == 'py' for d in deps_list):
            registries.append("PyPI")
        if any(d['manager'] == 'docker' for d in deps_list):
            registries.append("Docker Hub")

        if registries:
            click.echo(f"  Connecting to: {', '.join(registries)}")
        latest_info = check_latest_versions(deps_list, allow_net=True, offline=offline, allow_prerelease=allow_prerelease)
        if latest_info:
            write_deps_latest_json(latest_info, output_path=out.replace("deps.json", "deps_latest.json"))

            # Count successful vs failed checks
            successful_checks = sum(1 for info in latest_info.values() if info.get("latest") is not None)
            failed_checks = sum(1 for info in latest_info.values() if info.get("error") is not None)

            click.echo(f"  [OK] Checked {successful_checks}/{len(unique_packages)} unique packages")
            if failed_checks > 0:
                click.echo(f"  [WARN] {failed_checks} packages failed to check")
                # Show first few errors
                errors = [(k.split(":")[1], v["error"]) for k, v in latest_info.items() if v.get("error")][:3]
                for pkg, err in errors:
                    click.echo(f"     - {pkg}: {err}")
        else:
            click.echo("  [FAIL] Failed to check versions (network issue or offline mode)")

    # Always show output
    click.echo(f"Dependencies written to {out}")

    # Count by manager
    npm_count = sum(1 for d in deps_list if d["manager"] == "npm")
    py_count = sum(1 for d in deps_list if d["manager"] == "py")
    docker_count = sum(1 for d in deps_list if d["manager"] == "docker")
    cargo_count = sum(1 for d in deps_list if d["manager"] == "cargo")

    click.echo(f"  Total: {len(deps_list)} dependencies")
    if npm_count > 0:
        click.echo(f"  Node/npm: {npm_count}")
    if py_count > 0:
        click.echo(f"  Python: {py_count}")
    if docker_count > 0:
        click.echo(f"  Docker: {docker_count}")
    if cargo_count > 0:
        click.echo(f"  Cargo/Rust: {cargo_count}")

    if latest_info:
        # Always use grouped report (only sane output format)
        generate_grouped_report(deps_list, latest_info, hide_up_to_date=True)

    # Add a helpful hint if no network operation was performed
    if not check_latest and not upgrade_all:
        click.echo("\nTIP: Run with --check-latest to check for outdated packages.")
