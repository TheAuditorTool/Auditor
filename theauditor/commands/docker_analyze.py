"""Docker security analysis command."""

import json
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import err_console, console
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes


@click.command("docker-analyze", cls=RichCommand)
@handle_exceptions
@click.option("--db-path", default="./.pf/repo_index.db", help="Path to repo_index.db")
@click.option("--output", help="Output file for findings (JSON format)")
@click.option(
    "--severity",
    type=click.Choice(["all", "critical", "high", "medium", "low"]),
    default="all",
    help="Minimum severity to report",
)
@click.option(
    "--check-vulns/--no-check-vulns",
    default=True,
    help="Check base images for vulnerabilities (requires network)",
)
def docker_analyze(db_path, output, severity, check_vulns):
    """Analyze Dockerfiles and container images for security vulnerabilities and misconfigurations.

    Performs static analysis on Dockerfiles to detect common security issues including privilege
    escalation risks, exposed secrets, insecure base images, and container hardening failures.
    Optionally checks base images against vulnerability databases (requires network).

    AI ASSISTANT CONTEXT:
      Purpose: Identifies Docker security issues and container misconfigurations
      Input: .pf/repo_index.db (Dockerfile contents extracted by 'aud full')
      Output: .pf/raw/docker_findings.json (security issues with severity)
      Prerequisites: aud full (populates database with Dockerfile contents)
      Integration: Part of security audit workflow, runs in 'aud full' pipeline
      Performance: ~2-5 seconds local analysis, +10-30s if checking vulnerabilities

    WHAT IT DETECTS:
      Privilege Escalation:
        - USER root instructions (containers running as root)
        - Missing USER statements (defaults to root)
        - SUDO usage in RUN commands
        - Capabilities additions (--cap-add=SYS_ADMIN, etc.)

      Secret Exposure:
        - ENV/ARG instructions with high-entropy values (likely secrets)
        - Hardcoded passwords, API keys, tokens in ENV
        - Private key material (.pem, .key files) copied into image
        - AWS credentials, GitHub tokens in RUN commands

      Insecure Base Images:
        - Outdated base images (Alpine <3.14, Ubuntu <20.04)
        - Unverified base images (no digest pinning)
        - Base images with known CVEs (if --check-vulns enabled)
        - Use of 'latest' tag (non-deterministic builds)

      Container Hardening Failures:
        - Missing HEALTHCHECK instruction
        - Exposed privileged ports (<1024)
        - World-writable file permissions (chmod 777)
        - Running package managers as non-root

    SUPPORTED FILE TYPES:
      - Dockerfile (standard)
      - Dockerfile.* (multi-stage: Dockerfile.prod, Dockerfile.dev)
      - .dockerignore (analyzed for secret exclusion)
      - docker-compose.yml (analyzed for service configurations)

    HOW IT WORKS:
      1. Reads Dockerfile content from database (extracted by 'aud full')
      2. Parses Docker instructions (FROM, RUN, ENV, ARG, USER, COPY, etc.)
      3. Applies security rules (privilege checks, secret detection, etc.)
      4. Optionally queries vulnerability databases for base image CVEs
      5. Generates findings with severity (critical/high/medium/low)
      6. Outputs JSON to .pf/raw/docker_findings.json

    EXAMPLES:
      # Use Case 1: Quick Docker security scan after indexing
      aud full && aud docker-analyze

      # Use Case 2: Offline analysis (skip vulnerability checks)
      aud docker-analyze --no-check-vulns

      # Use Case 3: Only show critical/high severity issues
      aud docker-analyze --severity high

      # Use Case 4: CI/CD integration with JSON output
      aud docker-analyze --output ./build/docker_security.json || exit $?

      # Use Case 5: Combined security audit workflow
      aud full && aud docker-analyze --severity critical

    COMMON WORKFLOWS:
      Pre-Deployment Security Check:
        aud full && aud docker-analyze --severity high --check-vulns

      CI/CD Pipeline (fail on critical):
        aud docker-analyze --severity critical || exit 2

      Development Audit (all issues):
        aud docker-analyze --output ./docker_audit.json

    OUTPUT FILES:
      .pf/raw/docker_findings.json     # Security findings (if --output specified)
      .pf/repo_index.db (tables read):
        - files: Dockerfile paths and content
        - assignments: ENV/ARG instructions

    OUTPUT FORMAT (JSON Schema):
      {
        "findings": [
          {
            "type": "root_user",
            "severity": "high",
            "file": "Dockerfile",
            "line": 12,
            "message": "Container runs as root user (no USER instruction)",
            "recommendation": "Add 'USER nonroot' before ENTRYPOINT"
          }
        ],
        "summary": {
          "critical": 0,
          "high": 1,
          "medium": 3,
          "low": 2
        },
        "total": 6
      }

    PERFORMANCE EXPECTATIONS:
      Small (1-2 Dockerfiles):     ~2 seconds,   ~100MB RAM
      Medium (5-10 Dockerfiles):   ~5 seconds,   ~150MB RAM
      Large (20+ Dockerfiles):     ~10 seconds,  ~200MB RAM
      With --check-vulns:          +10-30 seconds (network API calls)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --severity critical --check-vulns    # Pre-production validation
        --no-check-vulns --severity all      # Fast dev audit

      Flag Modifiers:
        --check-vulns: Queries vulnerability databases (requires network)
        --severity: Filters output (does not skip analysis)
        --output: Saves JSON without printing to stdout

    PREREQUISITES:
      Required:
        aud full               # Populates database with Dockerfile contents

      Optional:
        Network access         # For --check-vulns (queries CVE databases)

    EXIT CODES:
      0 = Success, no critical/high issues found
      1 = High severity findings detected
      2 = Critical security vulnerabilities found
      3 = Analysis incomplete (database missing or parse error)

    RELATED COMMANDS:
      aud full               # Extracts Dockerfile contents to database
      aud detect-patterns    # Pattern-based security rules (includes Docker)
      aud deps               # Analyzes package vulnerabilities in images
      aud terraform          # Analyzes infrastructure-as-code security

    SEE ALSO:
      aud manual docker      # Deep dive into Docker security analysis
      aud manual severity    # Learn about severity classifications

    TROUBLESHOOTING:
      Error: "Database not found"
        → Run 'aud full' first to populate .pf/repo_index.db

      No Dockerfiles found despite having Dockerfile:
        → Check 'aud full' output for parsing errors
        → Verify Dockerfile syntax is valid
        → Check .pf/pipeline.log for extractor failures

      Vulnerability checks timing out:
        → Use --no-check-vulns for offline analysis
        → Check network connectivity to vulnerability databases
        → Increase timeout with env var THEAUDITOR_TIMEOUT_SECONDS

      False positives for secret detection:
        → High entropy values (random strings) may be flagged
        → Review findings manually, not all ENV values are secrets
        → Legitimate base64 values may trigger detection

    NOTE: Base image vulnerability checks require network access and may be rate-limited
    by external APIs. Use --no-check-vulns for air-gapped environments.
    """
    from theauditor.docker_analyzer import analyze_docker_images

    if not Path(db_path).exists():
        err_console.print(
            f"[error]Error: Database not found at {db_path}[/error]", highlight=False
        )
        err_console.print("[error]Run 'aud full' first to create the database[/error]", )
        return ExitCodes.TASK_INCOMPLETE

    console.print("Analyzing Docker images for security issues...")
    if check_vulns:
        console.print("  Including vulnerability scan of base images...")
    findings = analyze_docker_images(db_path, check_vulnerabilities=check_vulns)

    if severity != "all":
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        min_severity = severity_order.get(severity.lower(), 0)
        findings = [
            f
            for f in findings
            if severity_order.get(f.get("severity", "").lower(), 0) >= min_severity
        ]

    severity_counts = {}
    for finding in findings:
        sev = finding.get("severity", "unknown").lower()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    if findings:
        console.print(f"\nFound {len(findings)} Docker security issues:", highlight=False)

        for sev in ["critical", "high", "medium", "low"]:
            if sev in severity_counts:
                console.print(f"  {sev.upper()}: {severity_counts[sev]}", highlight=False)

        console.print("\nFindings:")
        for finding in findings:
            console.print(f"\n\\[{finding['severity'].upper()}] {finding['type']}", highlight=False)
            console.print(f"  File: {finding['file']}", highlight=False)
            console.print(f"  {finding['message']}", highlight=False)
            if finding.get("recommendation"):
                console.print(f"  Fix: {finding['recommendation']}", highlight=False)
    else:
        console.print("No Docker security issues found")

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        docker_data = {"findings": findings, "summary": severity_counts, "total": len(findings)}

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(docker_data, f, indent=2)

        console.print(f"\nResults saved to: {output}", highlight=False)

    if severity_counts.get("critical", 0) > 0:
        return ExitCodes.CRITICAL_SEVERITY
    elif severity_counts.get("high", 0) > 0:
        return ExitCodes.HIGH_SEVERITY
    else:
        return ExitCodes.SUCCESS
