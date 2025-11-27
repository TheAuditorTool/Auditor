"""Perform taint analysis to detect security vulnerabilities via data flow tracking."""

import platform
from pathlib import Path

import click

from theauditor.utils.error_handler import handle_exceptions

IS_WINDOWS = platform.system() == "Windows"


@click.command("taint-analyze")
@handle_exceptions
@click.option("--db", default=None, help="Path to the SQLite database (default: repo_index.db)")
@click.option(
    "--output", default="./.pf/raw/taint_analysis.json", help="Output path for analysis results"
)
@click.option(
    "--max-depth", default=5, type=int, help="Maximum depth for taint propagation tracing"
)
@click.option("--json", is_flag=True, help="Output raw JSON instead of formatted report")
@click.option("--verbose", is_flag=True, help="Show detailed path information")
@click.option(
    "--severity",
    type=click.Choice(["all", "critical", "high", "medium", "low"]),
    default="all",
    help="Filter results by severity level",
)
@click.option("--rules/--no-rules", default=True, help="Enable/disable rule-based detection")
@click.option(
    "--memory/--no-memory",
    default=True,
    help="Use in-memory caching for 5-10x performance (enabled by default)",
)
@click.option(
    "--memory-limit",
    default=None,
    type=int,
    help="Memory limit for cache in MB (auto-detected based on system RAM if not set)",
)
@click.option(
    "--mode",
    default="backward",
    type=click.Choice(["backward", "forward", "complete"]),
    help="Analysis mode: backward (IFDS), forward (entry->exit), complete (all flows)",
)
def taint_analyze(
    db, output, max_depth, json, verbose, severity, rules, memory, memory_limit, mode
):
    """Trace data flow from untrusted sources to dangerous sinks to detect injection vulnerabilities.

    Performs inter-procedural data flow analysis to identify security vulnerabilities where untrusted
    user input flows into dangerous functions without sanitization. Uses Control Flow Graph (CFG) for
    path-sensitive analysis and in-memory caching for 5-10x performance boost on large codebases.

    AI ASSISTANT CONTEXT:
      Purpose: Detects injection vulnerabilities via taint propagation analysis
      Input: .pf/repo_index.db (function calls, assignments, control flow)
      Output: .pf/raw/taint_analysis.json (taint paths with severity)
      Prerequisites: aud index (populates database with call graph + CFG)
      Integration: Core security analysis, runs in 'aud full' pipeline
      Performance: ~30s-5min depending on codebase size (CFG+memory optimization)

    WHAT IT DETECTS (By Vulnerability Class):
      SQL Injection (SQLi):
        Sources: request.args, request.form, request.json, user input
        Sinks: cursor.execute(), db.query(), raw SQL string concatenation
        Example: cursor.execute(f"SELECT * FROM users WHERE id={user_id}")

      Command Injection (RCE):
        Sources: os.environ, sys.argv, HTTP parameters
        Sinks: os.system(), subprocess.call(), eval(), exec()
        Example: os.system(f"ping {user_input}")

      Cross-Site Scripting (XSS):
        Sources: HTTP request data, URL parameters
        Sinks: render_template() without escaping, innerHTML assignments
        Example: return f"<div>{user_name}</div>"  # No HTML escaping

      Path Traversal:
        Sources: File upload names, URL paths, user-specified paths
        Sinks: open(), Path().read_text(), os.path.join()
        Example: open(f"/var/data/{user_file}")  # No path validation

      LDAP Injection:
        Sources: User authentication inputs
        Sinks: ldap.search(), ldap.bind() with unsanitized filters

      NoSQL Injection:
        Sources: JSON request bodies, query parameters
        Sinks: MongoDB find(), Elasticsearch query DSL
        Example: db.users.find({"name": user_input})  # No validation

    DATA FLOW ANALYSIS METHOD:
      1. Identify Taint Sources (140+ patterns):
         - HTTP request data: Flask request.args, FastAPI params, Django request.GET
         - Environment variables: os.environ, sys.argv
         - File I/O: open().read(), Path().read_text()
         - Database results: cursor.fetchall() (secondary taint)

      2. Trace Taint Propagation:
         - Variable assignments: x = tainted_source
         - Function calls: propagate through parameters
         - String operations: f-strings, concatenation, format()
         - Collections: list/dict operations that preserve taint

      3. Identify Security Sinks (200+ patterns):
         - SQL: cursor.execute, db.query, raw SQL
         - Commands: os.system, subprocess, eval, exec
         - File ops: open, shutil, pathlib with user input
         - Templates: render without escaping

      4. Path Sensitivity (CFG Analysis):
         - Tracks conditional sanitization: if sanitize(x): safe_func(x)
         - Detects unreachable sinks: after return statements
         - Prunes false positives: validated paths vs unvalidated

    HOW IT WORKS (Algorithm):
      1. Read database: function_call_args, assignments, cfg_blocks tables
      2. Build call graph: inter-procedural analysis across functions
      3. Identify sources: Match against 140+ taint source patterns
      4. Propagate taint: Follow data flow through assignments/calls
      5. Detect sinks: Match against 200+ security sink patterns
      6. Classify severity: Critical (no sanitization) to Low (partial sanitization)
      7. Output: JSON with taint paths source→sink with line numbers

    EXAMPLES:
      # Use Case 1: Complete security audit after indexing
      aud index && aud taint-analyze

      # Use Case 2: Only show critical/high severity findings
      aud taint-analyze --severity high

      # Use Case 3: Verbose mode (show full taint paths)
      aud taint-analyze --verbose --severity critical

      # Use Case 4: Export for SAST tool integration
      aud taint-analyze --json --output ./sast_results.json

      # Use Case 5: Fast scan (disable CFG for speed)
      aud taint-analyze --no-cfg  # 3-5x faster but less accurate

      # Use Case 6: Memory-constrained environment
      aud taint-analyze --memory-limit 512  # Limit cache to 512MB

      # Use Case 7: Combined with workset (analyze recent changes)
      aud workset --diff HEAD~1 && aud taint-analyze --workset

    COMMON WORKFLOWS:
      Pre-Commit Security Check:
        aud index && aud taint-analyze --severity critical

      Pull Request Review:
        aud workset --diff main..feature && aud taint-analyze --workset

      CI/CD Pipeline (fail on high severity):
        aud taint-analyze --severity high || exit 2

      Full Security Audit:
        aud full --offline && aud taint-analyze --verbose

    OUTPUT FILES:
      .pf/raw/taint_analysis.json      # Taint paths with severity
      .pf/readthis/taint_chunk*.json   # AI-optimized chunks (<65KB)
      .pf/repo_index.db (tables read):
        - function_call_args: Sink detection
        - assignments: Taint propagation
        - cfg_blocks: Path-sensitive analysis

    OUTPUT FORMAT (JSON Schema):
      {
        "vulnerabilities": [
          {
            "type": "sql_injection",
            "severity": "critical",
            "source": {
              "file": "api.py",
              "line": 42,
              "function": "get_user",
              "variable": "user_id",
              "origin": "request.args"
            },
            "sink": {
              "file": "api.py",
              "line": 45,
              "function": "get_user",
              "call": "cursor.execute",
              "argument": "query"
            },
            "path": ["user_id = request.args.get('id')", "query = f'SELECT * WHERE id={user_id}'", "cursor.execute(query)"],
            "sanitized": false,
            "confidence": "high"
          }
        ],
        "summary": {
          "total": 15,
          "critical": 3,
          "high": 7,
          "medium": 4,
          "low": 1
        }
      }

    PERFORMANCE EXPECTATIONS:
      Small (<5K LOC):     ~10 seconds,   ~200MB RAM
      Medium (20K LOC):    ~30 seconds,   ~500MB RAM
      Large (100K+ LOC):   ~5 minutes,    ~2GB RAM
      With --memory:       5-10x faster (caching enabled)
      With --no-cfg:       3-5x faster (less accurate)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        --json and --verbose    # JSON output ignores verbose flag

      Recommended Combinations:
        --severity critical --verbose    # Debug critical issues
        --memory --use-cfg              # Optimal accuracy + performance (default)
        --no-cfg --memory-limit 512     # Fast scan on low-memory systems

      Flag Modifiers:
        --use-cfg: Path-sensitive analysis (recommended, slower but accurate)
        --memory: In-memory caching (5-10x faster, uses ~500MB-2GB RAM)
        --max-depth: Controls inter-procedural depth (higher=slower+more paths)
        --severity: Filters output only (does not skip analysis)

    PREREQUISITES:
      Required:
        aud index              # Populates database with call graph + CFG

      Optional:
        aud workset            # Limits analysis to changed files only

    EXIT CODES:
      0 = Success, no vulnerabilities found
      1 = High severity vulnerabilities detected
      2 = Critical security vulnerabilities found
      3 = Analysis incomplete (database missing or parse error)

    RELATED COMMANDS:
      aud index              # Builds call graph and CFG (run first)
      aud detect-patterns    # Pattern-based security rules (complementary)
      aud fce                # Cross-references taint findings with patterns
      aud workset            # Limits scope to changed files

    SEE ALSO:
      aud explain taint      # Learn about taint analysis concepts
      aud explain severity   # Understand severity classifications

    TROUBLESHOOTING:
      Error: "Database not found"
        → Run 'aud index' first to create .pf/repo_index.db

      Analysis too slow (>10 minutes):
        → Use --no-cfg for 3-5x speedup (less accurate)
        → Limit scope with 'aud workset' first
        → Reduce --max-depth from 5 to 3

      Out of memory errors:
        → Set --memory-limit to lower value (e.g., --memory-limit 512)
        → Use --no-memory to disable caching (slower but uses less RAM)
        → Analyze in smaller batches with --path-filter

      False positives (sanitized input flagged):
        → Check if sanitization function is recognized (see taint/core.py TaintRegistry)
        → Use custom sanitizers via .theauditor.yml config
        → Review with --verbose to see full taint path

      False negatives (known vulnerability not detected):
        → Verify source is in taint source registry
        → Check sink pattern is recognized
        → Increase --max-depth to trace deeper paths
        → Check .pf/pipeline.log for analysis warnings

    NOTE: Taint analysis is conservative (over-reports) to avoid missing vulnerabilities.
    Review findings manually - not all taint paths are exploitable. Path-sensitive analysis
    (--use-cfg) reduces false positives by respecting conditional sanitization.
    """
    import json as json_lib

    from theauditor.config_runtime import load_runtime_config
    from theauditor.rules.orchestrator import RulesOrchestrator
    from theauditor.taint import TaintRegistry, normalize_taint_path, trace_taint
    from theauditor.utils.memory import get_recommended_memory_limit

    if memory_limit is None:
        memory_limit = get_recommended_memory_limit()
        click.echo(f"[MEMORY] Using auto-detected memory limit: {memory_limit}MB")

    config = load_runtime_config(".")

    if db is None:
        db = config["paths"]["db"]

    db_path = Path(db)
    if not db_path.exists():
        click.echo(f"Error: Database not found at {db}", err=True)
        click.echo("Run 'aud full' first to build the repository index", err=True)
        raise click.ClickException(f"Database not found: {db}")

    click.echo("Validating database schema...", err=True)
    try:
        import sqlite3

        from theauditor.indexer.schema import validate_all_tables

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        mismatches = validate_all_tables(cursor)
        conn.close()

        if mismatches:
            click.echo("", err=True)
            click.echo("=" * 60, err=True)
            click.echo(" SCHEMA VALIDATION FAILED ", err=True)
            click.echo("=" * 60, err=True)
            click.echo("Database schema does not match expected definitions.", err=True)
            click.echo("This will cause incorrect results or failures.\n", err=True)

            for table_name, errors in list(mismatches.items())[:5]:
                click.echo(f"Table: {table_name}", err=True)
                for error in errors[:2]:
                    click.echo(f"  - {error}", err=True)

            click.echo("\nFix: Run 'aud index' to rebuild database with correct schema.", err=True)
            click.echo("=" * 60, err=True)

            if not click.confirm("\nContinue anyway? (results may be incorrect)", default=False):
                raise click.ClickException("Aborted due to schema mismatch")

            click.echo(
                "WARNING: Continuing with schema mismatch - results may be unreliable", err=True
            )
        else:
            click.echo("Schema validation passed.", err=True)
    except ImportError:
        click.echo("Schema validation skipped (schema module not available)", err=True)
    except Exception as e:
        click.echo(f"Schema validation error: {e}", err=True)
        click.echo("Continuing anyway...", err=True)

    if rules:
        click.echo("Initializing security analysis infrastructure...")
        registry = TaintRegistry()
        orchestrator = RulesOrchestrator(project_path=Path("."), db_path=db_path)

        orchestrator.collect_rule_patterns(registry)

        all_findings = []

        click.echo("Running infrastructure and configuration analysis...")
        infra_findings = orchestrator.run_standalone_rules()
        all_findings.extend(infra_findings)
        click.echo(f"  Found {len(infra_findings)} infrastructure issues")

        click.echo("Discovering framework-specific patterns...")
        discovery_findings = orchestrator.run_discovery_rules(registry)
        all_findings.extend(discovery_findings)

        stats = registry.get_stats()
        click.echo(
            f"  Registry now has {stats['total_sinks']} sinks, {stats['total_sources']} sources"
        )

        click.echo("Performing data-flow taint analysis...")

        if mode == "backward":
            click.echo("  Using IFDS mode (graphs.db)")
        else:
            click.echo(f"  Using {mode} flow resolution mode")
        result = trace_taint(
            db_path=str(db_path),
            max_depth=max_depth,
            registry=registry,
            use_memory_cache=memory,
            memory_limit_mb=memory_limit,
            mode=mode,
        )

        taint_paths = result.get("taint_paths", result.get("paths", []))
        click.echo(f"  Found {len(taint_paths)} taint flow vulnerabilities")

        click.echo("Running advanced security analysis...")

        def taint_checker(var_name, line_num=None):
            """Check if variable is in any taint path."""
            for path in taint_paths:
                if path.get("source", {}).get("name") == var_name:
                    return True

                if path.get("sink", {}).get("name") == var_name:
                    return True

                for step in path.get("path", []):
                    if isinstance(step, dict) and step.get("name") == var_name:
                        return True
            return False

        advanced_findings = orchestrator.run_taint_dependent_rules(taint_checker)
        all_findings.extend(advanced_findings)
        click.echo(f"  Found {len(advanced_findings)} advanced security issues")

        click.echo(f"\nTotal vulnerabilities found: {len(all_findings) + len(taint_paths)}")

        result["infrastructure_issues"] = infra_findings
        result["discovery_findings"] = discovery_findings
        result["advanced_findings"] = advanced_findings
        result["all_rule_findings"] = all_findings

        result["total_vulnerabilities"] = len(taint_paths) + len(all_findings)
    else:
        click.echo("Performing taint analysis (rules disabled)...")

        if mode == "backward":
            click.echo("  Using IFDS mode (graphs.db)")
        else:
            click.echo(f"  Using {mode} flow resolution mode")

        registry = TaintRegistry()

        result = trace_taint(
            db_path=str(db_path),
            max_depth=max_depth,
            registry=registry,
            use_memory_cache=memory,
            memory_limit_mb=memory_limit,
            mode=mode,
        )

    if result.get("success"):
        normalized_paths = []
        for path in result.get("taint_paths", result.get("paths", [])):
            normalized_paths.append(normalize_taint_path(path))
        result["taint_paths"] = normalized_paths
        result["paths"] = normalized_paths

    if severity != "all" and result.get("success"):
        filtered_paths = []
        for path in result.get("taint_paths", result.get("paths", [])):
            path = normalize_taint_path(path)
            if (
                path["severity"].lower() == severity
                or (severity == "critical" and path["severity"].lower() == "critical")
                or (severity == "high" and path["severity"].lower() in ["critical", "high"])
            ):
                filtered_paths.append(path)

        result["taint_paths"] = filtered_paths
        result["paths"] = filtered_paths
        result["total_vulnerabilities"] = len(filtered_paths)

        from collections import defaultdict

        vuln_counts = defaultdict(int)
        for path in filtered_paths:
            vuln_counts[path.get("vulnerability_type", "Unknown")] += 1
        result["vulnerabilities_by_type"] = dict(vuln_counts)

        from theauditor.taint.insights import generate_summary

        result["summary"] = generate_summary(filtered_paths)

    if db_path.exists():
        try:
            from theauditor.indexer.database import DatabaseManager

            db_manager = DatabaseManager(str(db_path))

            findings_dicts = []
            for taint_path in result.get("taint_paths", []):
                sink = taint_path.get("sink", {})
                source = taint_path.get("source", {})

                vuln_type = taint_path.get("vulnerability_type", "Unknown")
                source_name = source.get("name", "unknown")
                sink_name = sink.get("name", "unknown")
                message = f"{vuln_type}: {source_name} → {sink_name}"

                findings_dicts.append(
                    {
                        "file": sink.get("file", ""),
                        "line": int(sink.get("line", 0)),
                        "column": sink.get("column"),
                        "rule": f"taint-{sink.get('category', 'unknown')}",
                        "tool": "taint",
                        "message": message,
                        "severity": "high",
                        "category": "injection",
                        "code_snippet": None,
                        "additional_info": taint_path,
                    }
                )

            for finding in result.get("all_rule_findings", []):
                findings_dicts.append(
                    {
                        "file": finding.get("file", ""),
                        "line": int(finding.get("line", 0)),
                        "rule": finding.get("rule", "unknown"),
                        "tool": "taint",
                        "message": finding.get("message", ""),
                        "severity": finding.get("severity", "medium"),
                        "category": finding.get("category", "security"),
                    }
                )

            if findings_dicts:
                db_manager.write_findings_batch(findings_dicts, tool_name="taint")
                db_manager.close()
                click.echo(
                    f"[DB] Wrote {len(findings_dicts)} taint findings to database for FCE correlation"
                )
        except Exception as e:
            click.echo(f"[DB] Warning: Database write failed: {e}", err=True)
            click.echo("[DB] JSON output will still be generated for AI consumption")

    output_path = Path(".pf") / "raw" / "taint.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        import json as json_lib

        json_lib.dump(result, f, indent=2, sort_keys=True)
    click.echo(f"[OK] Taint analysis saved to {output_path}")

    if json:
        click.echo(json_lib.dumps(result, indent=2, sort_keys=True))
    else:
        if result.get("success"):
            paths = result.get("taint_paths", result.get("paths", []))
            click.echo(f"\n[TAINT] Found {len(paths)} taint paths")
            click.echo(f"[TAINT] Sources: {result.get('sources_found', 0)}")
            click.echo(f"[TAINT] Sinks: {result.get('sinks_found', 0)}")

            for i, path in enumerate(paths[:10], 1):
                path = normalize_taint_path(path)
                sink_type = path.get("sink", {}).get("type", "unknown")
                click.echo(f"\n{i}. {sink_type}")
                click.echo(f"   Source: {path['source']['file']}:{path['source']['line']}")
                click.echo(f"   Sink: {path['sink']['file']}:{path['sink']['line']}")

            if len(paths) > 10:
                click.echo(
                    f"\n... and {len(paths) - 10} additional paths (use --json for full output)"
                )
        else:
            click.echo(f"\n[ERROR] {result.get('error', 'Unknown error')}")

    if result.get("success"):
        summary = result.get("summary", {})
        if summary.get("critical_count", 0) > 0:
            exit(2)
        elif summary.get("high_count", 0) > 0:
            exit(1)
    else:
        raise click.ClickException(result.get("error", "Analysis failed"))
