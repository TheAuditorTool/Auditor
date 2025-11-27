"""Analyze security boundary enforcement across entry points."""

import json
import sys
from pathlib import Path

import click

from theauditor.boundaries.boundary_analyzer import (
    analyze_input_validation_boundaries,
    generate_report,
)
from theauditor.utils.error_handler import handle_exceptions


@click.command("boundaries")
@handle_exceptions
@click.option("--db", default=None, help="Path to repo_index.db (default: .pf/repo_index.db)")
@click.option(
    "--type",
    "boundary_type",
    type=click.Choice(["all", "input-validation", "multi-tenant", "authorization", "sanitization"]),
    default="all",
    help="Boundary type to analyze",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["report", "json"]),
    default="report",
    help="Output format (report=human-readable, json=machine-parseable)",
)
@click.option(
    "--max-entries",
    default=100,
    type=int,
    help="Maximum entry points to analyze (performance limit)",
)
@click.option(
    "--severity",
    type=click.Choice(["all", "critical", "high", "medium", "low"]),
    default="all",
    help="Filter findings by severity",
)
def boundaries(db, boundary_type, output_format, max_entries, severity):
    """Analyze security boundary enforcement and measure distance from entry to control points.

    Detects where security controls (validation, authentication, sanitization) are enforced
    relative to entry points. Reports factual distance measurements - NOT recommendations.

    CRITICAL CONCEPTS:
      Boundary: Point where trust level changes (external->internal, untrusted->validated)
      Distance: Number of function calls between entry point and control point
      Entry Point: HTTP route, CLI command, message handler (external data ingress)
      Control Point: Validation, authentication, sanitization (security enforcement)

    DISTANCE SEMANTICS:
      Distance 0: Control at entry (validation in function signature)
      Distance 1-2: Control nearby (acceptable for most boundaries)
      Distance 3+: Control far from entry (data spreads before enforcement)
      Distance None: No control found (missing boundary enforcement)

    AI ASSISTANT CONTEXT:
      Purpose: Measure boundary enforcement quality via call-chain distance analysis
      Input: .pf/repo_index.db (symbols, call_graph, routes, validators)
      Output: Boundary analysis report with distance measurements (facts only, NO recommendations)
      Prerequisites: aud index (populates call graph for distance calculation)
      Integration: Security audit pipeline, complements taint analysis
      Performance: ~5-30s depending on entry point count and call graph size

    WHAT IT ANALYZES (By Boundary Type):
      Input Validation:
        Entry Points: python_routes, js_routes (HTTP endpoints)
        Control Patterns: validate(), parse(), check(), sanitize(), schema validators
        Violation: External data flows N functions before validation
        Example: req.body -> service.create() -> db.insert() -> validate() (distance 3)

      Multi-Tenant Isolation (RLS):
        Entry Points: Database queries on tenant-sensitive tables
        Control Patterns: tenant_id in WHERE clause, SET LOCAL app.current_tenant_id
        Violation: Query on sensitive table without tenant filter
        Example: SELECT * FROM orders WHERE id=? (missing tenant_id filter)

      Authorization:
        Entry Points: Protected routes, admin operations
        Control Patterns: @requires_auth, check_permission(), req.user validation
        Violation: Protected operation without auth check
        Example: DELETE /api/user/:id without permission check

      Sanitization:
        Entry Points: User input to dangerous sinks (SQL, HTML, shell)
        Control Patterns: Parameterized queries, HTML escaping, input sanitization
        Violation: User input used in sink without sanitization
        Example: db.query(f"SELECT * FROM users WHERE name='{name}'")

    BOUNDARY QUALITY LEVELS (Factual Classification):
      clear: Single control at distance 0 (validation at entry)
      acceptable: Single control at distance 1-2 (validation nearby)
      fuzzy: Multiple controls OR distance 3+ (scattered/late enforcement)
      missing: No control found (no boundary enforcement detected)

    OUTPUT STRUCTURE (--format json):
      {
        "entry_point": "POST /api/users",
        "entry_file": "src/routes/users.js",
        "entry_line": 34,
        "controls": [
          {
            "control_function": "validateUser",
            "control_file": "src/validators/user.js",
            "control_line": 12,
            "distance": 2,
            "path": ["create_user", "processUser", "validateUser"]
          }
        ],
        "quality": {
          "quality": "acceptable",
          "reason": "Single control point 'validateUser' at distance 2",
          "facts": [
            "Validation occurs 2 function call(s) after entry",
            "Data flows through 2 intermediate function(s) before validation",
            "Single validation control point detected"
          ]
        },
        "violations": []
      }

    TRUTH COURIER DESIGN:
      Reports: Factual observations about boundary state (distance, control presence)
      Does NOT: Provide recommendations, prescribe fixes, suggest changes
      Example (CORRECT): "Validation occurs at distance 3 (3 calls after entry)"
      Example (WRONG): "Fix: Move validation to entry point"

    INTEGRATION WITH OTHER COMMANDS:
      aud taint-analyze: Detects data flow violations (untrusted->sink)
      aud boundaries: Detects control placement violations (distance from entry)
      aud blueprint --boundaries: Shows boundary architecture in codebase structure
      aud context query --boundary "/api/users": Shows boundary details for specific route

    MULTI-TENANT SaaS USE CASE (Critical for Compliance):
      Problem: Missing tenant_id filter = cross-tenant data leak = lawsuit
      Detection: Queries on tenant-sensitive tables without tenant_id in WHERE clause
      Measurement: Distance from authenticated tenant_id to database query
      Example Violation:
        app.get('/api/docs', auth, (req, res) => {
          const docId = req.params.id;
          // Distance to tenant check: 2 (after DB access - TOO LATE)
          const doc = db.query('SELECT * FROM docs WHERE id=?', [docId]);
          if (doc.tenant_id !== req.user.tenantId) return 403;
        })
      Fact Reported: "Tenant validation occurs at distance 2 (after database access)"

    EXAMPLE USAGE:
      # Analyze all boundary types
      aud boundaries

      # Input validation boundaries only
      aud boundaries --type input-validation

      # Multi-tenant RLS boundaries only
      aud boundaries --type multi-tenant

      # JSON output for programmatic processing
      aud boundaries --type input-validation --format json

      # Filter critical findings only
      aud boundaries --severity critical

      # Limit analysis to 50 entry points (performance)
      aud boundaries --max-entries 50

    COMMON PATTERNS DETECTED:
      Joi/Zod Triple Handler Problem:
        Observation: Multiple validation controls at distances 0, 1, 3
        Fact: 3 different validation points indicate distributed boundary
        Implication: Different code paths encounter different validation

      Validation After Use:
        Observation: Validation at distance 3 (data flows through 3 functions first)
        Fact: Distance 3 creates 3 potential unvalidated code paths
        Implication: Data may spread to multiple locations before validation

      User-Controlled Tenant ID:
        Observation: tenant_id sourced from req.query (user input)
        Fact: Tenant identifier originates from untrusted source
        Implication: User can access arbitrary tenant data

      Missing Validation:
        Observation: Entry point accepts external data without validation control
        Fact: No validation control detected within search depth
        Implication: External data flows to downstream functions without validation gate
    """

    if db is None:
        db = Path.cwd() / ".pf" / "repo_index.db"
    else:
        db = Path(db)

    if not db.exists():
        click.echo(f"Error: Database not found at {db}", err=True)
        click.echo("Run 'aud full' first to populate the database", err=True)
        sys.exit(1)

    results = []

    if boundary_type in ["all", "input-validation"]:
        click.echo("Analyzing input validation boundaries...", err=True)
        validation_results = analyze_input_validation_boundaries(
            db_path=str(db), max_entries=max_entries
        )
        results.extend(validation_results)

    if boundary_type == "multi-tenant":
        click.echo("Error: Multi-tenant boundary analysis not yet wired to this command", err=True)
        click.echo("Use: aud full (includes multi-tenant analysis via rules)", err=True)
        sys.exit(1)

    if severity != "all":
        results = [
            r
            for r in results
            if any(v["severity"].lower() == severity for v in r.get("violations", []))
        ]

    if output_format == "json":
        output = {
            "boundary_type": boundary_type,
            "total_entry_points": len(results),
            "analysis": results,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        report = generate_report(results)
        click.echo(report)

    critical_count = sum(
        1 for r in results for v in r.get("violations", []) if v["severity"] == "CRITICAL"
    )

    if critical_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
