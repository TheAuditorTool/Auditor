"""[DEPRECATED] Index command - now redirects to 'aud full' for data fidelity."""

import time

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console
from theauditor.utils.error_handler import handle_exceptions


@click.command(cls=RichCommand)
@handle_exceptions
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--quiet", is_flag=True, help="Minimal output")
@click.option(
    "--exclude-self", is_flag=True, help="Exclude TheAuditor's own files (for self-testing)"
)
@click.option("--offline", is_flag=True, help="Skip network operations (deps, docs)")
@click.option(
    "--subprocess-taint",
    is_flag=True,
    help="Run taint analysis as subprocess (slower but isolated)",
)
@click.option("--wipecache", is_flag=True, help="Delete all caches before run")
@click.pass_context
def index(ctx, root, quiet, exclude_self, offline, subprocess_taint, wipecache):
    """[DEPRECATED] This command now runs 'aud full' for data fidelity.

    ════════════════════════════════════════════════════════════════════════════════
    DEPRECATION NOTICE: 'aud index' is DEPRECATED
    ════════════════════════════════════════════════════════════════════════════════

    The 'aud index' command no longer provides sufficient data fidelity for modern
    TheAuditor analysis. It now automatically runs the complete 'aud full' pipeline
    (20 phases) to ensure all analysis commands have proper context.

    WHY THIS CHANGE:
      • Taint analysis requires framework detection (Phase 2)
      • Deadcode detection requires workset creation (Phase 3)
      • Graph analysis requires dependency graphs (Phase 9-11)
      • Impact analysis requires call graphs and CFGs
      • Running partial pipelines leads to incomplete/incorrect results

    WHAT HAPPENS NOW:
      Running 'aud index' will execute the COMPLETE audit pipeline including:
        - Repository indexing (AST parsing)
        - Framework detection (Django, Flask, React, etc.)
        - Dependency analysis and vulnerability scanning
        - Workset creation (file filtering)
        - Security pattern detection (200+ patterns)
        - Taint analysis (cross-file data flow)
        - Graph analysis (hotspots, cycles)
        - Control flow graphs (complexity analysis)
        - Factual Correlation Engine (finding aggregation)
        - Report generation (AI-optimized chunks)

    MIGRATION GUIDE:
      OLD Workflow:
        aud index                    # Phase 1 only
        aud taint-analyze            # Incomplete context
        aud deadcode                 # Incomplete context

      NEW Workflow:
        aud full                     # All phases (includes taint, deadcode, etc.)
        aud full --offline           # Air-gapped (skips network operations)
        aud full --quiet             # Minimal output for CI/CD

    BACKWARD COMPATIBILITY:
      This command will continue to work to maintain CI/CD compatibility, but will
      run the full audit pipeline instead of just indexing. Update your workflows:

      CI/CD Pipelines:
        OLD: aud index && aud taint-analyze && aud deadcode
        NEW: aud full --quiet

      Development Workflow:
        OLD: aud index --print-stats
        NEW: aud full

      Self-Testing:
        OLD: aud index --exclude-self
        NEW: aud full --exclude-self

    UNSUPPORTED FLAGS (removed in deprecation):
      The following flags from the old 'aud index' are NOT supported:
        --manifest, --db           → Configure via .auditorconfig or env vars
        --print-stats              → Use 'aud full' (always shows summary)
        --dry-run                  → Use 'aud full --offline' for no network I/O
        --follow-symlinks          → Controlled by .auditorconfig
        --no-archive               → Archiving handled by 'aud full' automatically

    PERFORMANCE:
      OLD 'aud index': ~10-30 seconds (Phase 1 only)
      NEW redirect:    ~10-60 minutes (complete 20-phase pipeline)

      This is INTENTIONAL - you should be running the full audit for data fidelity.
      For incremental analysis, use workset filtering after initial audit:
        aud full                     # Initial complete audit
        aud taint-analyze --workset  # Incremental on changed files

    TIMELINE:
      This deprecation warning will be removed in v2.0 when 'aud index' is fully
      retired. Update your scripts and pipelines now to avoid future issues.

    For more information:
      aud full --help              # See complete pipeline documentation
      aud manual workset           # Learn about incremental analysis
      aud manual fce               # Understand finding correlation

    ════════════════════════════════════════════════════════════════════════════════
    """

    if not quiet:
        console.print("")
        console.rule()
        console.print(" " * 28 + "DEPRECATION WARNING", markup=False)
        console.rule()
        console.print("")
        console.print("  The 'aud index' command is DEPRECATED and now runs 'aud full' instead.")
        console.print("")
        console.print("  WHY: 'aud index' alone no longer provides sufficient data fidelity")
        console.print("       for modern TheAuditor analysis. Most commands require the full")
        console.print("       pipeline context (frameworks, workset, graphs) to operate correctly.")
        console.print("")
        console.print(
            "  IMPACT: This will run the COMPLETE 20-phase audit pipeline (~10-60 minutes)"
        )
        console.print("          instead of just Phase 1 indexing (~10-30 seconds).")
        console.print("")
        console.print("  ACTION REQUIRED:")
        console.print("    • Update CI/CD pipelines to use 'aud full' explicitly")
        console.print("    • Replace 'aud index && aud taint-analyze' with just 'aud full'")
        console.print("    • Use 'aud full --offline' for air-gapped environments")
        console.print("    • Use 'aud full --quiet' for minimal output in automation")
        console.print("")
        console.print("  This warning will be removed in v2.0 when 'aud index' is fully retired.")
        console.print("")
        console.rule()
        console.print("")
        console.print("Proceeding with 'aud full' in 3 seconds... (Press Ctrl+C to cancel)")
        console.print("")

        try:
            time.sleep(3)
        except KeyboardInterrupt:
            console.print("\nCancelled. Please update your command to use 'aud full' instead.")
            ctx.exit(0)

    from theauditor.commands.full import full

    ctx.invoke(
        full,
        root=root,
        quiet=quiet,
        exclude_self=exclude_self,
        offline=offline,
        subprocess_taint=subprocess_taint,
        wipecache=wipecache,
    )
