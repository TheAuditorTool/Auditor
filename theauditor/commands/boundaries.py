"""Analyze security boundary enforcement across entry points."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from theauditor.boundaries.boundary_analyzer import (
    analyze_input_validation_boundaries,
    generate_report,
)
from theauditor.boundaries.chain_tracer import (
    ValidationChain,
    trace_validation_chains,
)
from theauditor.boundaries.security_audit import (
    format_security_audit,
    run_security_audit,
)
from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.error_handler import handle_exceptions


def format_validation_chain(chain: ValidationChain) -> str:
    """Format a validation chain for terminal output.

    Visual chain with arrows and status markers.
    ASCII-safe output (no emojis per CLAUDE.md rules).

    Format:
        POST /users (body: CreateUserInput)
            | [PASS] Zod validated at entry
            v
        userService.create(data: CreateUserInput)
            | [PASS] Type preserved
            v
        repo.insert(data: any)        <- CHAIN BROKEN
            | [FAIL] Cast to any - validation meaningless now
    """
    lines = []

    # Header
    lines.append(f"{chain.entry_point}")
    lines.append(f"  File: {chain.entry_file}:{chain.entry_line}")
    lines.append(f"  Status: {chain.chain_status.upper()}")
    lines.append("")

    # Chain visualization
    for i, hop in enumerate(chain.hops):
        is_break = chain.break_index == i

        # Function with type info
        func_line = f"  {hop.function}({hop.type_info})"
        if is_break:
            func_line += "        <- CHAIN BROKEN"
        lines.append(func_line)

        # Status marker
        if hop.validation_status == "validated":
            status = "[PASS] Validated at entry"
        elif hop.validation_status == "preserved":
            status = "[PASS] Type preserved"
        elif hop.validation_status == "broken":
            status = f"[FAIL] {hop.break_reason or 'Type safety lost'}"
        else:
            status = "[----] Unknown type status"

        lines.append(f"      | {status}")

        # Arrow to next (unless last)
        if i < len(chain.hops) - 1:
            lines.append("      v")

    lines.append("")
    return "\n".join(lines)


def format_validation_chains_report(chains: list[ValidationChain]) -> str:
    """Format multiple validation chains as a report."""
    lines = []
    lines.append("=== VALIDATION CHAIN ANALYSIS ===\n")

    # Summary
    total = len(chains)
    intact = sum(1 for c in chains if c.chain_status == "intact")
    broken = sum(1 for c in chains if c.chain_status == "broken")
    no_val = sum(1 for c in chains if c.chain_status == "no_validation")

    lines.append(f"Entry Points Analyzed: {total}")
    lines.append(f"  Chains Intact:      {intact} ({intact * 100 // total if total else 0}%)")
    lines.append(f"  Chains Broken:      {broken} ({broken * 100 // total if total else 0}%)")
    lines.append(f"  No Validation:      {no_val} ({no_val * 100 // total if total else 0}%)")
    lines.append("")

    # Show broken chains first (most important)
    broken_chains = [c for c in chains if c.chain_status == "broken"]
    if broken_chains:
        lines.append("[BROKEN CHAINS]:\n")
        for chain in broken_chains[:10]:
            lines.append(format_validation_chain(chain))
        if len(broken_chains) > 10:
            lines.append(f"... and {len(broken_chains) - 10} more broken chains\n")

    # Show no_validation chains
    no_val_chains = [c for c in chains if c.chain_status == "no_validation"]
    if no_val_chains:
        lines.append("[NO VALIDATION]:\n")
        for chain in no_val_chains[:5]:
            lines.append(f"  {chain.entry_point}")
            lines.append(f"    File: {chain.entry_file}:{chain.entry_line}")
            lines.append("    [FAIL] No validation at entry\n")
        if len(no_val_chains) > 5:
            lines.append(f"... and {len(no_val_chains) - 5} more without validation\n")

    # Show intact chains (good examples)
    intact_chains = [c for c in chains if c.chain_status == "intact"]
    if intact_chains:
        lines.append("[INTACT CHAINS]:\n")
        for chain in intact_chains[:3]:
            lines.append(f"  {chain.entry_point}")
            lines.append(f"    File: {chain.entry_file}:{chain.entry_line}")
            lines.append("    [PASS] Validation preserved through chain\n")
        if len(intact_chains) > 3:
            lines.append(f"... and {len(intact_chains) - 3} more intact chains\n")

    return "\n".join(lines)


@click.command("boundaries", cls=RichCommand)
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
@click.option(
    "--validated",
    is_flag=True,
    help="Trace validation chains through data flow (shows where type safety breaks)",
)
@click.option(
    "--audit",
    is_flag=True,
    help="Run security boundary audit (input/output/DB/file trust boundaries)",
)
def boundaries(db, boundary_type, output_format, max_entries, severity, validated, audit):
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
      Prerequisites: aud full (populates call graph for distance calculation)
      Integration: Security audit pipeline, complements taint analysis
      Runtime: ~5-30s depending on entry point count and call graph size

    EXIT CODES:
      0 = Success, no critical boundary violations detected
      1 = Critical boundary violations found (missing controls at entry points)

    RELATED COMMANDS:
      aud taint      # Track data flow from sources to sinks
      aud blueprint --boundaries  # Show boundary architecture overview
      aud full               # Complete analysis including boundaries

    SEE ALSO:
      aud manual boundaries  # Deep dive into boundary analysis concepts
      aud manual taint       # Understand taint tracking relationship

    TROUBLESHOOTING:
      Error: "Database not found":
        -> Run 'aud full' first to populate repo_index.db
        -> Check .pf/repo_index.db exists

      No entry points found:
        -> Ensure routes/endpoints are indexed (Python/JS routes)
        -> Run 'aud full' with appropriate language support

      Analysis is slow (>60s):
        -> Reduce --max-entries to limit entry point count
        -> Large call graphs increase traversal time
    """

    db = Path.cwd() / ".pf" / "repo_index.db" if db is None else Path(db)

    if not db.exists():
        err_console.print(f"[error]Error: Database not found at {db}[/error]", highlight=False)
        err_console.print(
            "[error]Run 'aud full' first to populate the database[/error]",
        )
        sys.exit(1)

    # Handle --validated flag: Trace validation chains through data flow
    if validated:
        err_console.print("Tracing validation chains through data flow...")
        chains = trace_validation_chains(db_path=str(db), max_entries=max_entries)

        if output_format == "json":
            output = {
                "analysis_type": "validation_chains",
                "total_chains": len(chains),
                "chains": [asdict(c) for c in chains],
            }
            console.print(json.dumps(output, indent=2), markup=False)
        else:
            report = format_validation_chains_report(chains)
            console.print(report, markup=False)

        # Exit code based on broken chains
        broken_count = sum(1 for c in chains if c.chain_status == "broken")
        no_val_count = sum(1 for c in chains if c.chain_status == "no_validation")
        if broken_count > 0 or no_val_count > 0:
            sys.exit(1)
        sys.exit(0)

    # Handle --audit flag: Run security boundary audit
    if audit:
        err_console.print("Running security boundary audit...")
        audit_report = run_security_audit(db_path=str(db), max_findings=max_entries)

        if output_format == "json":
            output = {
                "analysis_type": "security_audit",
                "total_pass": audit_report.total_pass,
                "total_fail": audit_report.total_fail,
                "categories": {
                    cat: asdict(result)
                    for cat, result in audit_report.results.items()
                },
            }
            console.print(json.dumps(output, indent=2), markup=False)
        else:
            report = format_security_audit(audit_report)
            console.print(report, markup=False)

        # Exit code based on failures
        if audit_report.total_fail > 0:
            sys.exit(1)
        sys.exit(0)

    # Standard boundary analysis (original behavior)
    results = []

    if boundary_type in ["all", "input-validation"]:
        err_console.print(
            "[error]Analyzing input validation boundaries...[/error]",
        )
        validation_results = analyze_input_validation_boundaries(
            db_path=str(db), max_entries=max_entries
        )
        results.extend(validation_results)

    if boundary_type == "multi-tenant":
        err_console.print(
            "[error]Error: Multi-tenant boundary analysis not yet wired to this command[/error]",
        )
        err_console.print(
            "[error]Use: aud full (includes multi-tenant analysis via rules)[/error]",
        )
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
        console.print(json.dumps(output, indent=2), markup=False)
    else:
        report = generate_report(results)
        console.print(report, markup=False)

    critical_count = sum(
        1 for r in results for v in r.get("violations", []) if v["severity"] == "CRITICAL"
    )

    if critical_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
