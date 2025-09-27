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
            formatter.write_text("aud full                    # Complete 13-phase security audit")
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
            formatter.write_paragraph()
            
            formatter.write_text("aud docker-analyze          # Analyze Docker security issues")
            formatter.write_text("  --severity critical       # Filter by severity")
        
        formatter.write_paragraph()
        formatter.write_text("DEPENDENCIES:")
        with formatter.indentation():
            formatter.write_text("aud deps                    # Analyze project dependencies")
            formatter.write_text("  --vuln-scan               # Run npm audit & pip-audit")
            formatter.write_text("  --check-latest            # Check for outdated packages")
            formatter.write_text("  --upgrade-all             # YOLO: upgrade everything to latest")
        
        formatter.write_paragraph()
        formatter.write_text("CODE QUALITY:")
        with formatter.indentation():
            formatter.write_text("aud lint                    # Run all configured linters")
            formatter.write_text("  --fix                     # Auto-fix issues where possible")
            formatter.write_text("  --workset                 # Lint only changed files")
        
        formatter.write_paragraph()
        formatter.write_text("ANALYSIS & REPORTING:")
        with formatter.indentation():
            formatter.write_text("aud graph build             # Build dependency graph")
            formatter.write_text("aud graph analyze           # Find cycles and architectural issues")
            formatter.write_paragraph()
            
            formatter.write_text("aud cfg analyze             # Analyze control flow complexity")
            formatter.write_text("  --complexity-threshold 15 # Set complexity threshold")
            formatter.write_text("  --find-dead-code          # Find unreachable code")
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
            
            formatter.write_text("aud fce                     # Run Factual Correlation Engine")
            formatter.write_text("aud report                  # Generate final report")
            formatter.write_text("aud structure               # Generate project structure report")
        
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
            formatter.write_text("aud setup-claude            # Setup sandboxed JS/TS tools")
            formatter.write_text("  --target .                # Target directory")
            formatter.write_paragraph()
            
            formatter.write_text("aud init-js                 # Create/merge package.json")
            formatter.write_text("aud init-config             # Initialize configuration")
        
        formatter.write_paragraph()
        formatter.write_text("For detailed help on any command: aud <command> --help")


@click.group(cls=VerboseGroup)
@click.version_option(version=__version__, prog_name="aud")
@click.help_option("-h", "--help")
def cli():
    """TheAuditor - Offline, air-gapped CLI for repo indexing and evidence checking.
    
    Quick Start:
      aud init                    # Initialize project
      aud full                    # Run complete audit
      aud full --offline          # Run without network operations
    
    View results in .pf/readthis/ directory."""
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
from theauditor.commands.setup import setup_claude

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

# Import new commands
from theauditor.commands.docker_analyze import docker_analyze
from theauditor.commands.structure import structure
from theauditor.commands.metadata import metadata

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
cli.add_command(setup_claude)

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

# Register new commands
cli.add_command(docker_analyze)
cli.add_command(structure)

# Register command groups
cli.add_command(graph)
cli.add_command(cfg)
cli.add_command(metadata)

# All commands have been migrated to separate modules

def main():
    """Main entry point for console script."""
    cli()


if __name__ == "__main__":
    main()