"""TheAuditor CLI - Main entry point and command registration hub."""

import platform
import subprocess
import sys

import click
from theauditor import __version__

# Configure UTF-8 console output for Windows
if platform.system() == "Windows":
    try:
        # Set console code page to UTF-8
        subprocess.run(["chcp", "65001"], shell=True, capture_output=True, timeout=1)
        # Also configure Python's stdout/stderr
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception:
        # Silently continue if chcp fails (not critical)
        pass


class VerboseGroup(click.Group):
    """Custom group that shows all subcommands and their key options in help."""
    
    def format_help(self, ctx, formatter):
        """Format help to show all commands with their key options."""
        # Original help text
        super().format_help(ctx, formatter)
        
        # Add detailed command listing
        formatter.write_paragraph()
        formatter.write_text("Detailed Command Overview:")
        formatter.write_paragraph()
        
        # Core commands
        formatter.write_text("CORE ANALYSIS:")
        with formatter.indentation():
            formatter.write_text("aud full                    # Complete 20-phase security audit")
            formatter.write_text("  --offline                 # Skip network operations (deps, docs)")
            formatter.write_text("  --exclude-self            # Exclude TheAuditor's own files")
            formatter.write_text("  --quiet                   # Minimal output")
            formatter.write_paragraph()
            
            formatter.write_text("aud index                   # Build file manifest and symbol database")
            formatter.write_text("  --exclude-self            # Exclude TheAuditor's own files")
            formatter.write_paragraph()
            
            formatter.write_text("aud workset                 # Analyze only changed files")
            formatter.write_text("  --diff HEAD~3..HEAD       # Specify git commit range")
            formatter.write_text("  --all                     # Include all files")
        
        formatter.write_paragraph()
        formatter.write_text("SECURITY SCANNING:")
        with formatter.indentation():
            formatter.write_text("aud detect-patterns         # Run 100+ security pattern rules")
            formatter.write_text("  --workset                 # Scan only workset files")
            formatter.write_paragraph()
            
            formatter.write_text("aud taint-analyze           # Track data flow from sources to sinks")
            formatter.write_text("  --no-interprocedural      # Disable cross-function tracking")
            formatter.write_paragraph()
            
            formatter.write_text("aud docker-analyze          # Analyze Docker security issues")
            formatter.write_text("  --severity critical       # Filter by severity")
            formatter.write_text("  --check-vulns             # Enable vulnerability scanning")
        
        formatter.write_paragraph()
        formatter.write_text("DEPENDENCIES:")
        with formatter.indentation():
            formatter.write_text("aud deps                    # Analyze project dependencies")
            formatter.write_text("  --vuln-scan               # Run npm audit, pip-audit, OSV-Scanner")
            formatter.write_text("  --offline                 # Use offline databases (no network)")
            formatter.write_text("  --check-latest            # Check for outdated packages")
            formatter.write_text("  --upgrade-all             # YOLO: upgrade everything to latest")
            formatter.write_paragraph()

            formatter.write_text("aud docs fetch              # Fetch documentation for dependencies")
            formatter.write_text("aud docs summarize          # Create AI-optimized doc capsules")
            formatter.write_text("aud docs list               # List available documentation")
            formatter.write_text("aud docs view <package>     # View specific package docs")
        
        formatter.write_paragraph()
        formatter.write_text("CODE QUALITY:")
        with formatter.indentation():
            formatter.write_text("aud lint                    # Run all configured linters")
            formatter.write_text("  --workset                 # Lint only changed files")
            formatter.write_text("  --print-plan              # Preview linters without running")
        
        formatter.write_paragraph()
        formatter.write_text("ANALYSIS & REPORTING:")
        with formatter.indentation():
            formatter.write_text("aud graph build             # Build dependency graph")
            formatter.write_text("aud graph analyze           # Find cycles and architectural issues")
            formatter.write_text("aud graph viz               # Visualize dependency graph")
            formatter.write_text("  --view full|cycles|hotspots|layers|impact  # Visualization mode")
            formatter.write_paragraph()
            
            formatter.write_text("aud cfg analyze             # Analyze control flow complexity")
            formatter.write_text("  --complexity-threshold 15 # Set complexity threshold")
            formatter.write_text("  --find-dead-code          # Find unreachable code")
            formatter.write_text("  --workset                 # Analyze workset files only")
            formatter.write_text("aud cfg viz                 # Visualize function control flow")
            formatter.write_text("  --file src/auth.py        # File containing function")
            formatter.write_text("  --function validate       # Function to visualize")
            formatter.write_paragraph()
            
            formatter.write_text("aud impact                  # Analyze change impact radius")
            formatter.write_text("  --file src/auth.py        # Specify file to analyze")
            formatter.write_text("  --line 42                 # Specific line number")
            formatter.write_paragraph()
            
            formatter.write_text("aud refactor                # Detect incomplete refactorings")
            formatter.write_text("  --auto-detect             # Auto-detect from migrations")
            formatter.write_text("  --workset                 # Check current changes")
            formatter.write_paragraph()

            formatter.write_text("aud context                 # Apply user-defined business logic")
            formatter.write_text("  --file context.yaml       # Semantic context YAML file")
            formatter.write_text("  --verbose                 # Show detailed findings")
            formatter.write_paragraph()

            formatter.write_text("aud blueprint               # Architectural visualization (NO ML/CUDA)")
            formatter.write_text("  --format text             # Visual ASCII display (default)")
            formatter.write_text("  --format json             # Structured JSON export")
            formatter.write_text("  # Shows: structure, hot files, security, data flow, imports")
            formatter.write_text("  # Prereq: Run 'aud full' for complete blueprint")
            formatter.write_paragraph()

            formatter.write_text("aud fce                     # Run Factual Correlation Engine")
            formatter.write_text("aud report                  # Generate final report")
            formatter.write_text("aud structure               # Generate project structure report")
            formatter.write_text("  --max-depth 5             # Directory depth limit")
            formatter.write_text("  --output structure.json   # Custom output path")
        
        formatter.write_paragraph()
        formatter.write_text("ADVANCED:")
        with formatter.indentation():
            formatter.write_text("aud insights                # Run optional insights analysis")
            formatter.write_text("  --mode ml                 # ML risk predictions")
            formatter.write_text("  --mode graph              # Architecture health scoring")
            formatter.write_text("  --mode taint              # Security severity analysis")
            formatter.write_paragraph()
            
            formatter.write_text("aud learn                   # Train ML models on codebase")
            formatter.write_text("aud suggest                 # Get ML-powered suggestions")
        
        formatter.write_paragraph()
        formatter.write_text("SETUP & CONFIG:")
        with formatter.indentation():
            formatter.write_text("aud init                    # Initialize .pf/ directory")
            formatter.write_text("aud setup-ai                # Setup sandboxed tools + vuln databases")
            formatter.write_text("  --target .                # Target directory (downloads ~500MB)")
            formatter.write_paragraph()
            
            formatter.write_text("aud init-js                 # Create/merge package.json")
            formatter.write_text("aud init-config             # Initialize configuration")
        
        formatter.write_paragraph()
        formatter.write_text("For detailed help on any command: aud <command> --help")


@click.group(cls=VerboseGroup)
@click.version_option(version=__version__, prog_name="aud")
@click.help_option("-h", "--help")
def cli():
    """TheAuditor - Security & Code Intelligence Platform for AI-Assisted Development

    PURPOSE:
      Provides ground truth about your codebase through comprehensive security
      analysis, taint tracking, and quality auditing. Designed for both human
      developers and AI assistants to detect vulnerabilities, incomplete
      refactorings, and architectural issues.

    QUICK START:
      aud init                    # First-time setup (creates .pf/ directory)
      aud full                    # Run complete 20-phase security audit
      aud full --offline          # Air-gapped analysis (no network calls)

    COMMON WORKFLOWS:
      First time setup:
        aud init && aud full              # Complete initialization and audit

      After code changes:
        aud workset --diff HEAD~1         # Identify changed files
        aud lint --workset                # Quality check changes
        aud taint-analyze --workset       # Security check changes

      Pull request review:
        aud workset --diff main..feature  # What changed in PR
        aud impact --file api.py --line 1 # Check change impact
        aud detect-patterns --workset     # Security patterns

      Security audit:
        aud full --offline                # Complete offline audit
        aud deps --vuln-scan              # Check for CVEs
        aud explain severity              # Understand findings

      Performance optimization:
        aud cfg analyze --threshold 20    # Find complex functions
        aud graph analyze                 # Find circular dependencies
        aud structure                     # Understand architecture

      CI/CD pipeline:
        aud full --quiet || exit $?       # Fail on critical issues

      Understanding results:
        aud explain taint                 # Learn about concepts
        aud structure                     # Project overview
        aud report --print-stats          # Summary statistics

    OUTPUT STRUCTURE:
      .pf/
      ├── raw/                    # Immutable tool outputs (ground truth)
      ├── readthis/              # AI-optimized chunks (<65KB each)
      │   ├── *_chunk01.json     # Chunked findings for LLM consumption
      │   └── summary.json       # Executive summary
      ├── repo_index.db          # SQLite database with all code symbols
      └── pipeline.log           # Detailed execution trace

    EXIT CODES:
      0 = Success, no issues found
      1 = High severity findings detected
      2 = Critical security vulnerabilities found
      3 = Analysis incomplete or failed

    ENVIRONMENT VARIABLES:
      THEAUDITOR_LIMITS_MAX_FILE_SIZE=2097152   # Max file size in bytes (2MB)
      THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=65536    # Max chunk size (65KB)
      THEAUDITOR_TIMEOUT_SECONDS=1800           # Default timeout (30 min)
      THEAUDITOR_DB_BATCH_SIZE=200              # Database batch insert size

    For detailed help on any command: aud <command> --help
    Full documentation: https://github.com/TheAuditorTool/Auditor"""
    pass


# Import and register commands
from theauditor.commands.init import init
from theauditor.commands.index import index
from theauditor.commands.workset import workset
from theauditor.commands.lint import lint
from theauditor.commands.deps import deps
from theauditor.commands.report import report
from theauditor.commands.summary import summary
from theauditor.commands.graph import graph
from theauditor.commands.cfg import cfg
from theauditor.commands.full import full
from theauditor.commands.fce import fce
from theauditor.commands.impact import impact
from theauditor.commands.taint import taint_analyze
from theauditor.commands.setup import setup_ai
from theauditor.commands.explain import explain

# Import additional migrated commands
from theauditor.commands.detect_patterns import detect_patterns
from theauditor.commands.detect_frameworks import detect_frameworks
from theauditor.commands.docs import docs
from theauditor.commands.tool_versions import tool_versions
from theauditor.commands.init_js import init_js
from theauditor.commands.init_config import init_config

# Import ML commands
from theauditor.commands.ml import learn, suggest, learn_feedback

# Import internal commands (prefixed with _)
from theauditor.commands._archive import _archive

# Import rules command
from theauditor.commands.rules import rules_command

# Import refactoring analysis commands
from theauditor.commands.refactor import refactor_command
from theauditor.commands.insights import insights_command
from theauditor.commands.context import context_command
from theauditor.commands.query import query
from theauditor.commands.blueprint import blueprint

# Import new commands
from theauditor.commands.docker_analyze import docker_analyze
from theauditor.commands.structure import structure
from theauditor.commands.metadata import metadata
from theauditor.commands.terraform import terraform

# Register simple commands
cli.add_command(init)
cli.add_command(index)
cli.add_command(workset)
cli.add_command(lint)
cli.add_command(deps)
cli.add_command(report)
cli.add_command(summary)
cli.add_command(full)
cli.add_command(fce)
cli.add_command(impact)
cli.add_command(taint_analyze)
cli.add_command(setup_ai)
cli.add_command(setup_ai, name="setup-claude")  # Hidden legacy alias
cli.add_command(explain)

# Register additional migrated commands
cli.add_command(detect_patterns)
cli.add_command(detect_frameworks)
cli.add_command(docs)
cli.add_command(tool_versions)
cli.add_command(init_js)
cli.add_command(init_config)

# Register ML commands
cli.add_command(learn)
cli.add_command(suggest)
cli.add_command(learn_feedback)

# Register internal commands (not for direct user use)
cli.add_command(_archive)

# Register rules command
cli.add_command(rules_command)

# Register refactoring analysis commands
cli.add_command(refactor_command, name="refactor")
cli.add_command(insights_command, name="insights")
cli.add_command(context_command, name="context")
cli.add_command(query)
cli.add_command(blueprint)

# Register new commands
cli.add_command(docker_analyze)
cli.add_command(structure)

# Register command groups
cli.add_command(graph)
cli.add_command(cfg)
cli.add_command(metadata)
cli.add_command(terraform)

# All commands have been migrated to separate modules

def main():
    """Main entry point for console script."""
    cli()


if __name__ == "__main__":
    main()