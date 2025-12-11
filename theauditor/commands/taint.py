"""Perform taint analysis to detect security vulnerabilities via data flow tracking."""

import platform
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console
from theauditor.utils.error_handler import handle_exceptions

IS_WINDOWS = platform.system() == "Windows"


@click.command("taint", cls=RichCommand)
@handle_exceptions
@click.option("--db", default=None, help="Path to the SQLite database (default: repo_index.db)")
@click.option(
    "--max-depth", default=25, type=int, help="Maximum depth for taint propagation tracing"
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
    db, max_depth, json, verbose, severity, rules, memory, memory_limit, mode
):
    """Trace data flow from untrusted sources to dangerous sinks to detect injection vulnerabilities.

    Performs inter-procedural data flow analysis to identify security vulnerabilities where untrusted
    user input flows into dangerous functions without sanitization. Uses Control Flow Graph (CFG) for
    path-sensitive analysis and in-memory caching for 5-10x performance boost on large codebases.

    AI ASSISTANT CONTEXT:
      Purpose: Detects injection vulnerabilities via taint propagation analysis
      Input: .pf/repo_index.db (function calls, assignments, control flow)
      Output: findings_consolidated table, --json for stdout
      Prerequisites: aud full (populates database with call graph + CFG)
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
      # Use Case 1: Complete security audit (includes taint analysis)
      aud full

      # Use Case 2: Only show critical/high severity findings
      aud taint --severity high

      # Use Case 3: Verbose mode (show full taint paths)
      aud taint --verbose --severity critical

      # Use Case 4: Export for SAST tool integration
      aud taint --json > ./sast_results.json

      # Use Case 5: Fast scan (forward mode, less accurate)
      aud taint --mode forward  # Faster but may miss complex paths

      # Use Case 6: Memory-constrained environment
      aud taint --memory-limit 512  # Limit cache to 512MB

      # Use Case 7: Complete analysis (all flow directions)
      aud taint --mode complete  # Most thorough, slowest

    COMMON WORKFLOWS:
      Pre-Commit Security Check:
        aud full --index && aud taint --severity critical

      Pull Request Review:
        aud full --index && aud taint --severity high

      CI/CD Pipeline (fail on high severity):
        aud taint --severity high || exit 2

      Full Security Audit:
        aud full --offline && aud taint --verbose

    OUTPUT:
      Console or JSON (--json)         # Taint paths with severity
      taint_flows table                # Stored in database
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
      With --mode forward: 2-3x faster (less accurate)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        --json and --verbose    # JSON output ignores verbose flag

      Recommended Combinations:
        --severity critical --verbose    # Debug critical issues
        --mode backward --memory         # Optimal accuracy + performance (default)
        --mode forward --memory-limit 512  # Fast scan on low-memory systems

      Flag Modifiers:
        --mode: Analysis direction (backward=IFDS default, forward=faster, complete=thorough)
        --memory: In-memory caching (5-10x faster, uses ~500MB-2GB RAM)
        --max-depth: Controls inter-procedural depth (higher=slower+more paths)
        --severity: Filters output only (does not skip analysis)

    PREREQUISITES:
      Required:
        aud full               # Populates database with call graph + CFG

      Optional:
        aud workset            # Limits analysis to changed files only

    EXIT CODES:
      0 = Success, no vulnerabilities found
      1 = High severity vulnerabilities detected
      2 = Critical security vulnerabilities found
      3 = Analysis incomplete (database missing or parse error)

    RELATED COMMANDS:
      aud full               # Builds database and runs full pipeline
      aud detect-patterns    # Pattern-based security rules (complementary)
      aud fce                # Cross-references taint findings with patterns
      aud workset            # Limits scope to changed files

    SEE ALSO:
      aud manual taint       # Learn about taint analysis concepts
      aud manual severity    # Understand severity classifications

    TROUBLESHOOTING:
      Error: "Database not found"
        -> Run 'aud full' first to create .pf/repo_index.db

      Analysis too slow (>10 minutes):
        -> Use --mode forward for 2-3x speedup (less accurate)
        -> Use aud full --index first, then run taint on indexed data
        -> Reduce --max-depth from 5 to 3

      Out of memory errors:
        -> Set --memory-limit to lower value (e.g., --memory-limit 512)
        -> Use --no-memory to disable caching (slower but uses less RAM)
        -> Run aud full --index first, then taint on smaller scope

      False positives (sanitized input flagged):
        -> Check if sanitization function is recognized (see taint/core.py TaintRegistry)
        -> Use custom sanitizers via .theauditor.yml config
        -> Review with --verbose to see full taint path

      False negatives (known vulnerability not detected):
        -> Verify source is in taint source registry
        -> Check sink pattern is recognized
        -> Increase --max-depth to trace deeper paths
        -> Check .pf/pipeline.log for analysis warnings

    NOTE: Taint analysis is conservative (over-reports) to avoid missing vulnerabilities.
    Review findings manually - not all taint paths are exploitable. The default --mode backward
    uses IFDS algorithm for path-sensitive analysis, reducing false positives.
    """
    import json as json_lib

    from theauditor.commands.config import DB_PATH
    from theauditor.rules.orchestrator import RulesOrchestrator
    from theauditor.taint import TaintRegistry, normalize_taint_path, trace_taint
    from theauditor.utils.memory import get_recommended_memory_limit

    if memory_limit is None:
        memory_limit = get_recommended_memory_limit()
        console.print(
            f"\\[MEMORY] Using auto-detected memory limit: {memory_limit}MB", highlight=False
        )

    if db is None:
        db = DB_PATH

    db_path = Path(db)
    if not db_path.exists():
        console.print(f"[error]Error: Database not found at {db}[/error]", highlight=False)
        console.print("[error]Run 'aud full' first to build the repository index[/error]")
        raise click.ClickException(f"Database not found: {db}")

    console.print("[error]Validating database schema...[/error]")
    try:
        import sqlite3

        from theauditor.indexer.schema import validate_all_tables

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        mismatches = validate_all_tables(cursor)
        conn.close()

        if mismatches:
            console.print("[error][/error]")
            console.rule()
            console.print("[error] SCHEMA VALIDATION FAILED [/error]")
            console.rule()
            console.print("[error]Database schema does not match expected definitions.[/error]")
            console.print("[error]This will cause incorrect results or failures.\n[/error]")

            for table_name, errors in list(mismatches.items())[:5]:
                console.print(f"[error]Table: {table_name}[/error]", highlight=False)
                for error in errors[:2]:
                    console.print(f"[error]  - {error}[/error]", highlight=False)

            console.print(
                "[error]\nFix: Run 'aud full' to rebuild database with correct schema.[/error]",
            )
            console.rule()

            if not click.confirm("\nContinue anyway? (results may be incorrect)", default=False):
                raise click.ClickException("Aborted due to schema mismatch")

            console.print(
                "[error]WARNING: Continuing with schema mismatch - results may be unreliable[/error]",
            )
        else:
            console.print("[error]Schema validation passed.[/error]")
    except ImportError:
        console.print("[error]Schema validation skipped (schema module not available)[/error]")
    except Exception as e:
        console.print(f"[error]Schema validation error: {e}[/error]", highlight=False)
        console.print("[error]Continuing anyway...[/error]")

    if rules:
        console.print("Initializing security analysis infrastructure...")
        registry = TaintRegistry()
        orchestrator = RulesOrchestrator(project_path=Path("."), db_path=db_path)

        orchestrator.collect_rule_patterns(registry)

        all_findings = []

        console.print("Running infrastructure and configuration analysis...")
        infra_findings = orchestrator.run_standalone_rules()
        all_findings.extend(infra_findings)
        console.print(f"  Found {len(infra_findings)} infrastructure issues", highlight=False)

        console.print("Discovering framework-specific patterns...")
        discovery_findings = orchestrator.run_discovery_rules(registry)
        all_findings.extend(discovery_findings)

        stats = registry.get_stats()
        console.print(
            f"  Registry now has {stats['total_sinks']} sinks, {stats['total_sources']} sources",
            highlight=False,
        )

        console.print("Performing data-flow taint analysis...")

        if mode == "backward":
            console.print("  Using IFDS mode (graphs.db)")
        else:
            console.print(f"  Using {mode} flow resolution mode", highlight=False)
        result = trace_taint(
            db_path=str(db_path),
            max_depth=max_depth,
            registry=registry,
            use_memory_cache=memory,
            memory_limit_mb=memory_limit,
            mode=mode,
        )

        taint_paths = result.get("taint_paths", result.get("paths", []))
        console.print(f"  Found {len(taint_paths)} taint flow vulnerabilities", highlight=False)

        console.print("Running advanced security analysis...")

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
        console.print(f"  Found {len(advanced_findings)} advanced security issues", highlight=False)

        console.print(
            f"\nTotal vulnerabilities found: {len(all_findings) + len(taint_paths)}",
            highlight=False,
        )

        result["infrastructure_issues"] = infra_findings
        result["discovery_findings"] = discovery_findings
        result["advanced_findings"] = advanced_findings
        result["all_rule_findings"] = all_findings

        result["total_vulnerabilities"] = len(taint_paths) + len(all_findings)
    else:
        console.print("Performing taint analysis (rules disabled)...")

        if mode == "backward":
            console.print("  Using IFDS mode (graphs.db)")
        else:
            console.print(f"  Using {mode} flow resolution mode", highlight=False)

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
                console.print(
                    f"\\[DB] Wrote {len(findings_dicts)} taint findings to database for FCE correlation",
                    highlight=False,
                )
        except Exception as e:
            console.print(
                f"[error]\\[DB] Warning: Database write failed: {e}[/error]",
                highlight=False,
            )

    if json:
        console.print(json_lib.dumps(result, indent=2, sort_keys=True), markup=False)
    else:
        if result.get("success"):
            paths = result.get("taint_paths", result.get("paths", []))
            console.print(f"\n\\[TAINT] Found {len(paths)} taint paths", highlight=False)
            console.print(f"\\[TAINT] Sources: {result.get('sources_found', 0)}", highlight=False)
            console.print(f"\\[TAINT] Sinks: {result.get('sinks_found', 0)}", highlight=False)

            for i, path in enumerate(paths[:10], 1):
                path = normalize_taint_path(path)
                sink_type = path.get("sink", {}).get("type", "unknown")
                console.print(f"\n{i}. {sink_type}", highlight=False)
                console.print(
                    f"   Source: {path['source']['file']}:{path['source']['line']}", highlight=False
                )
                console.print(
                    f"   Sink: {path['sink']['file']}:{path['sink']['line']}", highlight=False
                )

            if len(paths) > 10:
                console.print(
                    f"\n... and {len(paths) - 10} additional paths (use --json for full output)",
                    highlight=False,
                )
        else:
            console.print(f"\n\\[ERROR] {result.get('error', 'Unknown error')}")

    if result.get("success"):
        summary = result.get("summary", {})
        if summary.get("critical_count", 0) > 0:
            exit(2)
        elif summary.get("high_count", 0) > 0:
            exit(1)
    else:
        raise click.ClickException(result.get("error", "Analysis failed"))
