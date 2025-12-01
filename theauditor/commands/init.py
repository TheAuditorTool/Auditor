"""[DEPRECATED] Init command - now redirects to 'aud full' for data fidelity."""

import time

import click

from theauditor.pipeline.ui import console


@click.command()
@click.option("--offline", is_flag=True, help="Skip network operations (deps, docs)")
@click.option("--quiet", is_flag=True, help="Minimal output")
@click.option(
    "--exclude-self", is_flag=True, help="Exclude TheAuditor's own files (for self-testing)"
)
@click.pass_context
def init(ctx, offline, quiet, exclude_self):
    """[DEPRECATED] This command now runs 'aud full' for data fidelity.

    ════════════════════════════════════════════════════════════════════════════════
    DEPRECATION NOTICE: 'aud init' is DEPRECATED
    ════════════════════════════════════════════════════════════════════════════════

    The 'aud init' command no longer provides sufficient initialization for modern
    TheAuditor analysis. It now automatically runs the complete 'aud full' pipeline
    (20 phases) which handles all initialization internally.

    WHY THIS CHANGE:
      • 'aud init' originally ran: index → workset → deps → docs (4 steps)
      • Modern analysis requires: frameworks, graphs, CFGs, taint, patterns, etc.
      • Running partial initialization leads to incomplete analysis context
      • 'aud full' auto-creates .pf/ directory and handles all setup automatically

    WHAT HAPPENS NOW:
      Running 'aud init' will execute 'aud full' which includes:
        [OK] Automatic .pf/ directory creation (no separate init needed)
        [OK] Repository indexing (AST parsing)
        [OK] Framework detection (Django, Flask, React, etc.)
        [OK] Dependency analysis and vulnerability scanning
        [OK] Workset creation (file filtering)
        [OK] Security pattern detection (200+ patterns)
        [OK] Taint analysis (cross-file data flow)
        [OK] Graph analysis (hotspots, cycles)
        [OK] Control flow graphs (complexity analysis)
        [OK] Factual Correlation Engine (finding aggregation)
        [OK] Report generation (AI-optimized chunks)

    MIGRATION GUIDE:
      OLD Workflow:
        aud init                     # Setup only (4 steps)
        aud taint-analyze            # Separate analysis
        aud deadcode                 # Separate analysis

      NEW Workflow:
        aud full                     # One command does everything
        aud full --offline           # Air-gapped (skips network operations)
        aud full --quiet             # Minimal output for CI/CD

    BACKWARD COMPATIBILITY:
      This command will continue to work to maintain CI/CD compatibility, but will
      run the full audit pipeline. Update your workflows:

      CI/CD Pipelines:
        OLD: aud init --offline && aud taint-analyze
        NEW: aud full --offline --quiet

      Development Workflow:
        OLD: aud init && aud full
        NEW: aud full  # (init happens automatically)

      Fresh Project Setup:
        OLD: cd project && aud init
        NEW: cd project && aud full

    UNSUPPORTED FLAGS (removed in deprecation):
      The following flags from the old 'aud init' are NOT supported:
        --skip-docs, --skip-deps   → Use 'aud full --offline' to skip network I/O

      Supported flags (mapped to 'aud full'):
        --offline                  → Skips network operations (deps, docs)
        --quiet                    → Minimal output for automation
        --exclude-self             → Excludes TheAuditor's own files

    PERFORMANCE:
      OLD 'aud init': ~10-30 seconds (4 setup steps only)
      NEW redirect:   ~10-60 minutes (complete 20-phase pipeline)

      This is INTENTIONAL - first-time setup should run complete audit.
      The .pf/ directory is created automatically, no separate init needed.

    AUTO-INITIALIZATION:
      'aud full' automatically detects if .pf/ doesn't exist and creates it.
      No separate initialization command is needed in modern workflows.

    TIMELINE:
      This deprecation warning will be removed in v2.0 when 'aud init' is fully
      retired. Update your scripts and pipelines now to avoid future issues.

    For more information:
      aud full --help              # See complete pipeline documentation
      aud explain workset          # Learn about incremental analysis

    ════════════════════════════════════════════════════════════════════════════════
    """

    if not quiet:
        console.print("")
        console.rule()
        console.print(" " * 28 + "DEPRECATION WARNING", markup=False)
        console.rule()
        console.print("")
        console.print("  The 'aud init' command is DEPRECATED and now runs 'aud full' instead.")
        console.print("")
        console.print("  WHY: 'aud init' alone no longer provides sufficient initialization")
        console.print("       for modern TheAuditor analysis. 'aud full' auto-creates .pf/")
        console.print("       directory and handles all setup + analysis in one command.")
        console.print("")
        console.print(
            "  IMPACT: This will run the COMPLETE 20-phase audit pipeline (~10-60 minutes)"
        )
        console.print("          instead of just 4-step initialization (~10-30 seconds).")
        console.print("")
        console.print("  ACTION REQUIRED:")
        console.print("    • Replace 'aud init && aud full' with just 'aud full'")
        console.print("    • Update CI/CD pipelines to use 'aud full' directly")
        console.print("    • Use 'aud full --offline' for air-gapped environments")
        console.print("    • Use 'aud full --quiet' for minimal output in automation")
        console.print("")
        console.print("  NOTE: .pf/ directory is created automatically by 'aud full'.")
        console.print("        No separate initialization step is needed.")
        console.print("")
        console.print("  This warning will be removed in v2.0 when 'aud init' is fully retired.")
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
        root=".",
        quiet=quiet,
        exclude_self=exclude_self,
        offline=offline,
        subprocess_taint=False,
        wipecache=False,
    )
