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
        # Use cmd /c to run chcp without shell=True (more secure)
        subprocess.run(["cmd", "/c", "chcp", "65001"], shell=False, capture_output=True, timeout=1)
        # Also configure Python's stdout/stderr
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception:
        # Silently continue if chcp fails (not critical)
        pass


class VerboseGroup(click.Group):
    """AI-First help system - dynamically generates help from registered commands."""

    def format_commands(self, ctx, formatter):
        """Override to suppress default command listing (we use categorized format in format_help)."""
        pass  # Intentionally empty - categories are in format_help

    # Command taxonomy (metadata only - NOT help text)
    COMMAND_CATEGORIES = {
        'PROJECT_SETUP': {
            'title': 'PROJECT SETUP',
            'description': 'Initial configuration and environment setup',
            'commands': ['setup-ai'],  # init-js, init-config deprecated (hidden)
            'ai_context': 'Run these FIRST in new projects. Creates .pf/ structure, installs tools.',
        },
        'CORE_ANALYSIS': {
            'title': 'CORE ANALYSIS',
            'description': 'Essential indexing and workset commands',
            'commands': ['full', 'workset'],  # 'index' deprecated (hidden)
            'ai_context': 'Foundation commands. full runs complete audit, workset filters scope.',
        },
        'SECURITY_SCANNING': {
            'title': 'SECURITY SCANNING',
            'description': 'Vulnerability detection and taint analysis',
            'commands': ['detect-patterns', 'taint-analyze', 'boundaries', 'docker-analyze',
                        'detect-frameworks', 'rules', 'context', 'workflows', 'cdk', 'terraform', 'deadcode'],
            'ai_context': 'Security-focused analysis. detect-patterns=rules, taint-analyze=data flow, boundaries=control distance.',
        },
        'DEPENDENCIES': {
            'title': 'DEPENDENCIES',
            'description': 'Package analysis and documentation',
            'commands': ['deps', 'docs'],
            'ai_context': 'deps checks CVEs and versions, docs fetches/summarizes package documentation.',
        },
        'CODE_QUALITY': {
            'title': 'CODE QUALITY',
            'description': 'Linting and complexity analysis',
            'commands': ['lint', 'cfg', 'graph', 'graphql'],
            'ai_context': 'Quality checks. lint=linters, cfg=complexity, graph=architecture, graphql=schema analysis.',
        },
        'DATA_REPORTING': {
            'title': 'DATA & REPORTING',
            'description': 'Analysis aggregation and report generation',
            'commands': ['fce', 'report', 'structure', 'summary', 'metadata', 'blueprint'],  # tool-versions deprecated
            'ai_context': 'fce correlates findings, report generates AI chunks, structure maps codebase.',
        },
        'ADVANCED_QUERIES': {
            'title': 'ADVANCED QUERIES',
            'description': 'Direct database queries and impact analysis',
            'commands': ['explain', 'query', 'impact', 'refactor'],
            'ai_context': 'explain=comprehensive context, query=SQL-like symbol lookup, impact=blast radius, refactor=migration analysis.',
        },
        'INSIGHTS_ML': {
            'title': 'INSIGHTS & ML',
            'description': 'Machine learning and risk predictions',
            'commands': ['insights', 'learn', 'suggest', 'learn-feedback', 'session'],
            'ai_context': 'Optional ML layer. learn trains models, suggest predicts risky files, session analyzes AI agent behavior.',
        },
        'UTILITIES': {
            'title': 'UTILITIES',
            'description': 'Educational and helper commands',
            'commands': ['manual', 'planning'],
            'ai_context': 'manual teaches concepts (taint, workset, fce), planning tracks work.',
        },
    }

    def format_help(self, ctx, formatter):
        """Generate concise categorized help."""
        super().format_help(ctx, formatter)

        registered = {name: cmd for name, cmd in self.commands.items()
                     if not name.startswith('_') and not getattr(cmd, 'hidden', False)}

        formatter.write_paragraph()
        formatter.write_text("Commands:")

        for category_id, category_data in self.COMMAND_CATEGORIES.items():
            formatter.write_text(f"  {category_data['title']}:")
            for cmd_name in category_data['commands']:
                if cmd_name not in registered:
                    continue
                cmd = registered[cmd_name]
                # Get first sentence, truncate at word boundary if too long
                first_line = (cmd.help or "").split('\n')[0].strip()
                period_idx = first_line.find('.')
                if period_idx > 0:
                    short_help = first_line[:period_idx]
                else:
                    short_help = first_line
                # Truncate at word boundary if >50 chars
                if len(short_help) > 50:
                    short_help = short_help[:50].rsplit(' ', 1)[0] + "..."
                formatter.write_text(f"    {cmd_name:20s} {short_help}")
            formatter.write_paragraph()

        formatter.write_text("For detailed options: aud <command> --help")
        formatter.write_text("For concepts: aud manual --list")


@click.group(cls=VerboseGroup)
@click.version_option(version=__version__, prog_name="aud")
@click.help_option("-h", "--help")
def cli():
    """TheAuditor - Security & Code Intelligence Platform

    \b
    QUICK START:
      aud full                  # Complete security audit
      aud full --offline        # Air-gapped analysis
      aud manual --list         # Learn concepts

    \b
    For detailed options: aud <command> --help
    For concepts: aud manual --list"""
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
from theauditor.commands.graphql import graphql
from theauditor.commands.cfg import cfg
from theauditor.commands.full import full
from theauditor.commands.fce import fce
from theauditor.commands.impact import impact
from theauditor.commands.taint import taint_analyze
from theauditor.commands.boundaries import boundaries
from theauditor.commands.setup import setup_ai
from theauditor.commands.manual import manual

# Import additional migrated commands
from theauditor.commands.detect_patterns import detect_patterns
from theauditor.commands.detect_frameworks import detect_frameworks
from theauditor.commands.docs import docs
from theauditor.commands.tool_versions import tool_versions
from theauditor.commands.init_js import init_js
from theauditor.commands.init_config import init_config
from theauditor.commands.planning import planning

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
from theauditor.commands.explain import explain

# Import new commands
from theauditor.commands.docker_analyze import docker_analyze
from theauditor.commands.structure import structure
from theauditor.commands.metadata import metadata
from theauditor.commands.terraform import terraform
from theauditor.commands.cdk import cdk
from theauditor.commands.workflows import workflows
from theauditor.commands.deadcode import deadcode
from theauditor.commands.session import session

# Register simple commands
# DEPRECATED: 'aud init' and 'aud index' now run 'aud full' for backward compatibility
# Hidden from help but still registered for CI/CD pipelines
init.hidden = True
index.hidden = True
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
cli.add_command(boundaries)
cli.add_command(setup_ai)
# Legacy alias - create hidden wrapper
@click.command("setup-claude", hidden=True)
@click.pass_context
def setup_claude_alias(ctx, **kwargs):
    """Deprecated: Use setup-ai instead."""
    ctx.invoke(setup_ai, **kwargs)
setup_claude_alias.params = setup_ai.params  # Copy params from original
cli.add_command(setup_claude_alias)
cli.add_command(manual)

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
cli.add_command(explain)
cli.add_command(blueprint)

# Register new commands
cli.add_command(docker_analyze)
cli.add_command(structure)

# Register command groups
cli.add_command(graph)
cli.add_command(graphql)
cli.add_command(cfg)
cli.add_command(metadata)
cli.add_command(terraform)
cli.add_command(cdk)
cli.add_command(workflows)
cli.add_command(planning)
cli.add_command(deadcode)
cli.add_command(session)

# All commands have been migrated to separate modules

def main():
    """Main entry point for console script."""
    cli()


if __name__ == "__main__":
    main()
