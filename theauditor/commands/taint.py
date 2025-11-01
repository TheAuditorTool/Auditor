"""Perform taint analysis to detect security vulnerabilities via data flow tracking."""

import sys
import platform
import click
from pathlib import Path
from datetime import datetime, UTC
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.consolidated_output import write_to_group

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"



@click.command("taint-analyze")
@handle_exceptions
@click.option("--db", default=None, help="Path to the SQLite database (default: repo_index.db)")
@click.option("--output", default="./.pf/raw/taint_analysis.json", help="Output path for analysis results")
@click.option("--max-depth", default=5, type=int, help="Maximum depth for taint propagation tracing")
@click.option("--json", is_flag=True, help="Output raw JSON instead of formatted report")
@click.option("--verbose", is_flag=True, help="Show detailed path information")
@click.option("--severity", type=click.Choice(["all", "critical", "high", "medium", "low"]),
              default="all", help="Filter results by severity level")
@click.option("--rules/--no-rules", default=True, help="Enable/disable rule-based detection")
@click.option("--use-cfg/--no-cfg", default=True,
              help="Use flow-sensitive CFG analysis (enabled by default)")
@click.option("--memory/--no-memory", default=True,
              help="Use in-memory caching for 5-10x performance (enabled by default)")
@click.option("--memory-limit", default=None, type=int,
              help="Memory limit for cache in MB (auto-detected based on system RAM if not set)")
def taint_analyze(db, output, max_depth, json, verbose, severity, rules, use_cfg, memory, memory_limit):
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
        → Check if sanitization function is recognized (see taint/registry.py)
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
    from theauditor.taint_analyzer import trace_taint, save_taint_analysis, normalize_taint_path, SECURITY_SINKS
    from theauditor.taint.insights import format_taint_report, calculate_severity, generate_summary, classify_vulnerability
    from theauditor.config_runtime import load_runtime_config
    from theauditor.rules.orchestrator import RulesOrchestrator, RuleContext
    from theauditor.taint.registry import TaintRegistry
    from theauditor.utils.memory import get_recommended_memory_limit
    import json as json_lib
    
    # Auto-detect memory limit if not specified
    if memory_limit is None:
        memory_limit = get_recommended_memory_limit()
        click.echo(f"[MEMORY] Using auto-detected memory limit: {memory_limit}MB")
    
    # Load configuration for default paths
    config = load_runtime_config(".")
    
    # Use default database path if not provided
    if db is None:
        db = config["paths"]["db"]
    
    # Verify database exists
    db_path = Path(db)
    if not db_path.exists():
        click.echo(f"Error: Database not found at {db}", err=True)
        click.echo("Run 'aud index' first to build the repository index", err=True)
        raise click.ClickException(f"Database not found: {db}")

    # SCHEMA CONTRACT: Pre-flight validation before expensive analysis
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

            for table_name, errors in list(mismatches.items())[:5]:  # Show first 5 tables
                click.echo(f"Table: {table_name}", err=True)
                for error in errors[:2]:  # Show first 2 errors per table
                    click.echo(f"  - {error}", err=True)

            click.echo("\nFix: Run 'aud index' to rebuild database with correct schema.", err=True)
            click.echo("=" * 60, err=True)

            if not click.confirm("\nContinue anyway? (results may be incorrect)", default=False):
                raise click.ClickException("Aborted due to schema mismatch")

            click.echo("WARNING: Continuing with schema mismatch - results may be unreliable", err=True)
        else:
            click.echo("Schema validation passed.", err=True)
    except ImportError:
        click.echo("Schema validation skipped (schema module not available)", err=True)
    except Exception as e:
        click.echo(f"Schema validation error: {e}", err=True)
        click.echo("Continuing anyway...", err=True)

    # Check if rules are enabled
    if rules:
        # STAGE 1: Initialize infrastructure
        click.echo("Initializing security analysis infrastructure...")
        registry = TaintRegistry()
        orchestrator = RulesOrchestrator(project_path=Path("."), db_path=db_path)
        
        # CRITICAL: Collect patterns from all rules and register them with the taint registry
        # This allows rules to contribute their patterns (ws.broadcast, Math.random, etc.)
        orchestrator.collect_rule_patterns(registry)
        
        # Track all findings
        all_findings = []
        
        # STAGE 2: Run standalone infrastructure rules
        click.echo("Running infrastructure and configuration analysis...")
        infra_findings = orchestrator.run_standalone_rules()
        all_findings.extend(infra_findings)
        click.echo(f"  Found {len(infra_findings)} infrastructure issues")
        
        # STAGE 3: Run discovery rules to populate registry
        click.echo("Discovering framework-specific patterns...")
        discovery_findings = orchestrator.run_discovery_rules(registry)
        all_findings.extend(discovery_findings)
        
        stats = registry.get_stats()
        click.echo(f"  Registry now has {stats['total_sinks']} sinks, {stats['total_sources']} sources")
        
        # STAGE 4: Run enriched taint analysis with registry
        click.echo("Performing data-flow taint analysis...")
        click.echo(f"  Using {'Stage 3 (CFG multi-hop)' if use_cfg else 'Stage 2 (call-graph)'}")
        result = trace_taint(
            db_path=str(db_path),
            max_depth=max_depth,
            registry=registry,
            use_cfg=use_cfg,  # Stage 3 ON by default (unless --no-cfg)
            use_memory_cache=memory,
            memory_limit_mb=memory_limit  # Now uses auto-detected or user-specified limit
        )
        
        # Extract taint paths
        taint_paths = result.get("taint_paths", result.get("paths", []))
        click.echo(f"  Found {len(taint_paths)} taint flow vulnerabilities")
        
        # STAGE 5: Run taint-dependent rules
        click.echo("Running advanced security analysis...")
        
        # Create taint checker from results
        def taint_checker(var_name, line_num=None):
            """Check if variable is in any taint path."""
            for path in taint_paths:
                # Check source
                if path.get("source", {}).get("name") == var_name:
                    return True
                # Check sink
                if path.get("sink", {}).get("name") == var_name:
                    return True
                # Check intermediate steps
                for step in path.get("path", []):
                    if isinstance(step, dict) and step.get("name") == var_name:
                        return True
            return False
        
        advanced_findings = orchestrator.run_taint_dependent_rules(taint_checker)
        all_findings.extend(advanced_findings)
        click.echo(f"  Found {len(advanced_findings)} advanced security issues")
        
        # STAGE 6: Consolidate all findings
        click.echo(f"\nTotal vulnerabilities found: {len(all_findings) + len(taint_paths)}")
        
        # Add all non-taint findings to result
        result["infrastructure_issues"] = infra_findings
        result["discovery_findings"] = discovery_findings
        result["advanced_findings"] = advanced_findings
        result["all_rule_findings"] = all_findings
        
        # Update total count
        result["total_vulnerabilities"] = len(taint_paths) + len(all_findings)
    else:
        # Original taint analysis without orchestrator
        click.echo("Performing taint analysis (rules disabled)...")
        click.echo(f"  Using {'Stage 3 (CFG multi-hop)' if use_cfg else 'Stage 2 (call-graph)'}")
        result = trace_taint(
            db_path=str(db_path),
            max_depth=max_depth,
            use_cfg=use_cfg,  # Stage 3 ON by default (unless --no-cfg)
            use_memory_cache=memory,
            memory_limit_mb=memory_limit  # Now uses auto-detected or user-specified limit
        )
    
    # Enrich raw paths with interpretive insights
    if result.get("success"):
        # Add severity and classification to each path
        enriched_paths = []
        for path in result.get("taint_paths", result.get("paths", [])):
            # Normalize the path first
            path = normalize_taint_path(path)
            # Add severity
            path["severity"] = calculate_severity(path)
            # Enrich sink information with vulnerability classification
            path["vulnerability_type"] = classify_vulnerability(
                path.get("sink", {}), 
                SECURITY_SINKS
            )
            enriched_paths.append(path)
        
        # Update result with enriched paths
        result["taint_paths"] = enriched_paths
        result["paths"] = enriched_paths
        
        # Generate summary
        result["summary"] = generate_summary(enriched_paths)
    
    # Filter by severity if requested
    if severity != "all" and result.get("success"):
        filtered_paths = []
        for path in result.get("taint_paths", result.get("paths", [])):
            # Normalize the path to ensure all keys exist
            path = normalize_taint_path(path)
            if path["severity"].lower() == severity or (
                severity == "critical" and path["severity"].lower() == "critical"
            ) or (
                severity == "high" and path["severity"].lower() in ["critical", "high"]
            ):
                filtered_paths.append(path)
        
        # Update counts
        result["taint_paths"] = filtered_paths
        result["paths"] = filtered_paths  # Keep both keys synchronized
        result["total_vulnerabilities"] = len(filtered_paths)
        
        # Recalculate vulnerability types
        from collections import defaultdict
        vuln_counts = defaultdict(int)
        for path in filtered_paths:
            # Path is already normalized from filtering above
            vuln_counts[path.get("vulnerability_type", "Unknown")] += 1
        result["vulnerabilities_by_type"] = dict(vuln_counts)
        
        # CRITICAL FIX: Recalculate summary with filtered paths
        from theauditor.taint.insights import generate_summary
        result["summary"] = generate_summary(filtered_paths)

    # ===== DUAL-WRITE PATTERN =====
    # Write to DATABASE first (for FCE performance), then JSON (for AI consumption)
    # Extract findings from taint_paths for database storage
    if db_path.exists():
        try:
            from theauditor.indexer.database import DatabaseManager
            db_manager = DatabaseManager(str(db_path))

            # Convert taint_paths to findings format for database
            # CRITICAL: Store complete taint path in details_json for FCE reconstruction
            findings_dicts = []
            for taint_path in result.get('taint_paths', []):
                # Extract from nested structure (taint paths have source/sink objects, not flat fields)
                sink = taint_path.get('sink', {})
                source = taint_path.get('source', {})

                # Construct descriptive message
                vuln_type = taint_path.get('vulnerability_type', 'Unknown')
                source_name = source.get('name', 'unknown')
                sink_name = sink.get('name', 'unknown')
                message = f"{vuln_type}: {source_name} → {sink_name}"

                findings_dicts.append({
                    'file': sink.get('file', ''),                        # Sink location (where vulnerability manifests)
                    'line': int(sink.get('line', 0)),                    # Sink line number
                    'column': sink.get('column'),                        # Sink column
                    'rule': f"taint-{sink.get('category', 'unknown')}", # Sink category (xss, sql, etc.)
                    'tool': 'taint',
                    'message': message,                                  # Constructed: "XSS: req.body → res.send"
                    'severity': 'high',                                  # Default high (all taint flows are critical)
                    'category': 'injection',
                    'code_snippet': None,                                # Not available in taint path structure
                    'additional_info': taint_path                        # Store complete path (source, intermediate steps, sink)
                })

            # Also add rule-based findings if available
            for finding in result.get('all_rule_findings', []):
                findings_dicts.append({
                    'file': finding.get('file', ''),
                    'line': int(finding.get('line', 0)),
                    'rule': finding.get('rule', 'unknown'),
                    'tool': 'taint',
                    'message': finding.get('message', ''),
                    'severity': finding.get('severity', 'medium'),
                    'category': finding.get('category', 'security')
                })

            if findings_dicts:
                db_manager.write_findings_batch(findings_dicts, tool_name='taint')
                db_manager.close()
                click.echo(f"[DB] Wrote {len(findings_dicts)} taint findings to database for FCE correlation")
        except Exception as e:
            # Non-fatal: if DB write fails, JSON write still succeeds
            click.echo(f"[DB] Warning: Database write failed: {e}", err=True)
            click.echo("[DB] JSON output will still be generated for AI consumption")
    # ===== END DUAL-WRITE =====

    # Write to consolidated group instead of separate file
    write_to_group("security_analysis", "taint", result, root=".")
    click.echo(f"[OK] Taint analysis saved to security_analysis.json")
    
    # Output results
    if json:
        # JSON output for programmatic use
        click.echo(json_lib.dumps(result, indent=2, sort_keys=True))
    else:
        # Human-readable report
        report = format_taint_report(result)
        click.echo(report)
        
        # Additional verbose output
        if verbose and result.get("success"):
            paths = result.get("taint_paths", result.get("paths", []))
            if paths and len(paths) > 10:
                click.echo("\n" + "=" * 60)
                click.echo("ADDITIONAL VULNERABILITY DETAILS")
                click.echo("=" * 60)
                
                for i, path in enumerate(paths[10:20], 11):
                    # Normalize path to ensure all keys exist
                    path = normalize_taint_path(path)
                    click.echo(f"\n{i}. {path['vulnerability_type']} ({path['severity']})")
                    click.echo(f"   Source: {path['source']['file']}:{path['source']['line']}")
                    click.echo(f"   Sink: {path['sink']['file']}:{path['sink']['line']}")
                    arrow = "->" if IS_WINDOWS else "→"
                    click.echo(f"   Pattern: {path['source'].get('pattern', '')} {arrow} {path['sink'].get('pattern', '')}")  # Empty not unknown
                
                if len(paths) > 20:
                    click.echo(f"\n... and {len(paths) - 20} additional vulnerabilities not shown")
    
    # Provide actionable recommendations based on findings
    if not json and result.get("success"):
        summary = result.get("summary", {})
        risk_level = summary.get("risk_level", "UNKNOWN")
        
        click.echo("\n" + "=" * 60)
        click.echo("RECOMMENDED ACTIONS")
        click.echo("=" * 60)
        
        if risk_level == "CRITICAL":
            click.echo("[CRITICAL] CRITICAL SECURITY ISSUES DETECTED")
            click.echo("1. Review and fix all CRITICAL vulnerabilities immediately")
            click.echo("2. Add input validation and sanitization at all entry points")
            click.echo("3. Use parameterized queries for all database operations")
            click.echo("4. Implement output encoding for all user-controlled data")
            click.echo("5. Consider a security audit before deployment")
        elif risk_level == "HIGH":
            click.echo("[HIGH] HIGH RISK VULNERABILITIES FOUND")
            click.echo("1. Prioritize fixing HIGH severity issues this sprint")
            click.echo("2. Review all user input handling code")
            click.echo("3. Implement security middleware/filters")
            click.echo("4. Add security tests for vulnerable paths")
        elif risk_level == "MEDIUM":
            click.echo("[MEDIUM] MODERATE SECURITY CONCERNS")
            click.echo("1. Schedule vulnerability fixes for next sprint")
            click.echo("2. Review and update security best practices")
            click.echo("3. Add input validation where missing")
        else:
            click.echo("[LOW] LOW RISK PROFILE")
            click.echo("1. Continue following secure coding practices")
            click.echo("2. Regular security scanning recommended")
            click.echo("3. Keep dependencies updated")
    
    # Exit with appropriate code
    if result.get("success"):
        summary = result.get("summary", {})
        if summary.get("critical_count", 0) > 0:
            exit(2)  # Critical vulnerabilities found
        elif summary.get("high_count", 0) > 0:
            exit(1)  # High severity vulnerabilities found
    else:
        raise click.ClickException(result.get("error", "Analysis failed"))