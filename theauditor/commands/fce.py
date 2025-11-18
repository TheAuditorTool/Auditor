"""Run Factual Correlation Engine to aggregate and correlate findings."""

import click
from theauditor.utils.error_handler import handle_exceptions


@click.command(name="fce")
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--capsules", default="./.pf/capsules", help="Capsules directory")
@click.option("--manifest", default="manifest.json", help="Manifest file path")
@click.option("--workset", default="./.pf/workset.json", help="Workset file path")
@click.option("--timeout", default=600, type=int, help="Timeout in seconds")
@click.option("--print-plan", is_flag=True, help="Print detected tools without running")
def fce(root, capsules, manifest, workset, timeout, print_plan):
    """Cross-reference findings to identify compound vulnerabilities.

    The Factual Correlation Engine (FCE) is TheAuditor's advanced analysis
    system that correlates findings from multiple tools to detect complex
    vulnerability patterns that single tools miss. It identifies when
    multiple "low severity" issues combine to create critical risks.

    Correlation Rules (30 Advanced Patterns):
      Authentication & Authorization:
        - Missing auth + exposed endpoints = Critical
        - Weak passwords + no rate limiting = High risk
        - Session fixation + XSS = Session hijacking

      Injection Combinations:
        - User input + SQL queries + no validation = SQL injection
        - File upload + path traversal = Remote code execution
        - Template injection + user data = XSS

      Data Exposure:
        - Debug mode + error messages = Information disclosure
        - Hardcoded secrets + public repo = Credential leak
        - Missing encryption + sensitive data = Data breach

      Infrastructure:
        - CORS misconfiguration + auth bypass = Account takeover
        - Outdated deps + known CVEs = Exploitable vulnerabilities
        - Docker misconfig + privileged mode = Container escape

      Code Quality Impact:
        - High complexity + no tests = Hidden vulnerabilities
        - Dead code + security logic = Bypassed protections
        - Circular deps + auth logic = Authorization bypass

    How FCE Works:
      1. Loads findings from all analysis tools
      2. Applies correlation rules to find patterns
      3. Elevates severity when patterns match
      4. Generates actionable compound findings

    Examples:
      aud fce                     # Run correlation engine
      aud fce --print-plan        # Preview what will be analyzed
      aud fce --timeout 1200      # Increase timeout for large projects

    Input Sources:
      - Pattern detection results
      - Taint analysis findings
      - Lint results
      - Dependency vulnerabilities
      - Graph analysis
      - Control flow analysis

    Output:
      .pf/raw/correlation_analysis.json  # Consolidated FCE results
        └── analyses:
            ├── fce               # Correlated findings
            └── fce_failures      # Critical compound issues

    Finding Format:
      {
        "rule": "sql_injection_compound",
        "severity": "critical",
        "confidence": "high",
        "evidence": [
          {"tool": "taint", "finding": "user_input_to_query"},
          {"tool": "patterns", "finding": "sql_concatenation"},
          {"tool": "lint", "finding": "no_input_validation"}
        ],
        "recommendation": "Implement parameterized queries",
        "files_affected": ["api/users.py", "db/queries.py"]
      }

    Value Proposition:
      - Finds vulnerabilities that single tools miss
      - Reduces false positives through correlation
      - Prioritizes real compound risks
      - Provides evidence chain for each finding

    AI ASSISTANT CONTEXT:
      Purpose: Cross-reference findings to detect compound vulnerabilities
      Input: Database + .pf/raw/*_analysis.json (consolidated analysis files)
      Output: .pf/raw/correlation_analysis.json (consolidated FCE results)
      Prerequisites: aud full (or multiple analysis commands)
      Integration: Final security validation, risk prioritization
      Performance: ~10-30 seconds (correlation rule matching)

    FLAG INTERACTIONS:
      --print-plan: Preview mode (no analysis, shows detected tools)
      --timeout: Increase for large projects (default 600s = 10 minutes)
      --root: Specify non-default project directory

    TROUBLESHOOTING:
      FCE timeout (>10 minutes):
        Cause: Very large codebase with many findings
        Solution: Increase --timeout to 1200 or run on workset

      No correlations found:
        Cause: Missing analysis phases (incomplete data)
        Solution: Run 'aud full' to populate all data sources

      "Unknown error" in FCE:
        Cause: Malformed JSON in .pf/raw/ artifacts
        Solution: Re-run analysis phases to regenerate clean artifacts

      High memory usage:
        Cause: Loading all findings into memory for correlation
        Solution: Run on workset or split into multiple runs

    Note: FCE is most effective after running 'aud full' to ensure
    all analysis data is available for correlation."""
    # SANDBOX DELEGATION: Check if running in sandbox
    from theauditor.sandbox_executor import is_in_sandbox, execute_in_sandbox

    if not is_in_sandbox():
        # Not in sandbox - delegate to sandbox Python
        import sys
        exit_code = execute_in_sandbox("fce", sys.argv[2:], root=root)
        sys.exit(exit_code)

    from theauditor.fce import run_fce

    result = run_fce(
        root_path=root,
        capsules_dir=capsules,
        manifest_path=manifest,
        workset_path=workset,
        timeout=timeout,
        print_plan=print_plan,
    )

    if result.get("printed_plan"):
        return

    if result["success"]:
        if result["failures_found"] == 0:
            click.echo("[OK] All tools passed - no failures detected")
        else:
            click.echo(f"Found {result['failures_found']} failures")
            # Check if output_files exists and has at least 2 elements
            if result.get('output_files') and len(result.get('output_files', [])) > 1:
                click.echo(f"FCE report written to: {result['output_files'][1]}")
            elif result.get('output_files') and len(result.get('output_files', [])) > 0:
                click.echo(f"FCE report written to: {result['output_files'][0]}")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        raise click.ClickException(result.get("error", "FCE failed"))