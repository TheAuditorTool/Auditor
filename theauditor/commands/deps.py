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
@click.option("--allow-prerelease", is_flag=True, help="Allow alpha/beta/rc versions (default: stable only)")
@click.option("--offline", is_flag=True, help="Force offline mode (no network)")
@click.option("--out", default="./.pf/raw/deps.json", help="Output dependencies file")
@click.option("--print-stats", is_flag=True, help="Print dependency statistics")
@click.option("--vuln-scan", is_flag=True, help="Scan dependencies for known vulnerabilities")
def deps(root, check_latest, upgrade_all, allow_prerelease, offline, out, print_stats, vuln_scan):
    """Analyze dependencies for vulnerabilities and updates.

    Comprehensive dependency analysis supporting Python (pip/poetry) and
    JavaScript/TypeScript (npm/yarn). Can check for outdated packages,
    known vulnerabilities, and even auto-upgrade everything (YOLO mode).

    Supported Files:
      - package.json / package-lock.json (npm/yarn)
      - pyproject.toml (Poetry/setuptools)
      - requirements.txt / requirements-*.txt (pip)
      - setup.py / setup.cfg (setuptools)

    Operation Modes:
      Default:        Parse and inventory all dependencies
      --check-latest: Check for available updates
      --vuln-scan:    Run security scanners (npm audit + OSV-Scanner)
      --upgrade-all:  YOLO mode - upgrade everything to latest

    Examples:
      aud deps                        # Basic dependency inventory
      aud deps --check-latest         # Check for outdated packages
      aud deps --vuln-scan            # Security vulnerability scan
      aud deps --upgrade-all          # DANGEROUS: Upgrade everything
      aud deps --offline              # Skip all network operations

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
    # SANDBOX DELEGATION: Check if running in sandbox
    from theauditor.sandbox_executor import is_in_sandbox, execute_in_sandbox

    if not is_in_sandbox():
        # Not in sandbox - delegate to sandbox Python
        import sys
        exit_code = execute_in_sandbox("deps", sys.argv[2:], root=root)
        sys.exit(exit_code)

    from theauditor.deps import parse_dependencies, write_deps_json, check_latest_versions, write_deps_latest_json, upgrade_all_deps
    from theauditor.vulnerability_scanner import scan_dependencies, write_vulnerabilities_json, format_vulnerability_report
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
            click.echo(f"\n  [WARN] Only {successful_checks}/{len(latest_info)} packages checked successfully")
            click.echo(f"  [FAIL] Cannot upgrade with {failed_checks} failed checks")
            click.echo("  Fix network issues and try again")
            return
            
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
        
        # Show first 20 upgrades with details
        for name, old_ver, new_ver, delta in upgraded_packages[:20]:
            delta_marker = " [MAJOR]" if delta == "major" else ""
            # Use arrow character that works on Windows
            arrow = "->" if IS_WINDOWS else "→"
            click.echo(f"  - {name}: {old_ver} {arrow} {new_ver}{delta_marker}")
        
        if len(upgraded_packages) > 20:
            click.echo(f"  ... and {len(upgraded_packages) - 20} more packages")
        
        # Show summary that matches the "Outdated: 10/29" format
        if total_updated > unique_upgraded:
            click.echo(f"\n  Summary: {unique_upgraded} unique packages updated across {total_updated} occurrences")
        
        click.echo("\n[NEXT STEPS]:")
        click.echo("  1. Run: pip install -r requirements.txt")
        click.echo("  2. Or: npm install")
        click.echo("  3. Pray it still works")
        return
        
    # Check latest versions if requested
    latest_info = {}
    if check_latest and not offline:
        # Count unique packages first
        unique_packages = {}
        for dep in deps_list:
            key = f"{dep['manager']}:{dep['name']}"
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
        # Count how many of the TOTAL deps are outdated (only if successfully checked)
        outdated_deps = 0
        checked_deps = 0
        for dep in deps_list:
            key = f"{dep['manager']}:{dep['name']}"
            if key in latest_info and latest_info[key].get("latest") is not None:
                checked_deps += 1
                if latest_info[key]["is_outdated"]:
                    outdated_deps += 1
        
        # Also count unique outdated packages
        outdated_unique = sum(1 for info in latest_info.values() if info.get("is_outdated", False))
        
        # Show outdated/checked rather than outdated/total
        if checked_deps == len(deps_list):
            # All were checked successfully
            click.echo(f"  Outdated: {outdated_deps}/{len(deps_list)}")
        else:
            # Some failed, show both numbers
            click.echo(f"  Outdated: {outdated_deps}/{checked_deps} checked ({len(deps_list)} total)")
        
        # Show major updates
        major_updates = [
            (k.split(":")[1], v["locked"], v["latest"])
            for k, v in latest_info.items()
            if v.get("delta") == "major"
        ]
        if major_updates:
            click.echo("\n  Major version updates available:")
            for name, locked, latest in major_updates[:5]:
                click.echo(f"    - {name}: {locked} -> {latest}")
            if len(major_updates) > 5:
                click.echo(f"    ... and {len(major_updates) - 5} more")
    
    # Add a helpful hint if no network operation was performed
    if not check_latest and not upgrade_all:
        click.echo("\nTIP: Run with --check-latest to check for outdated packages.")
