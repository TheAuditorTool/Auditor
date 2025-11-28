"""TheAuditor CLI - Main entry point and command registration hub."""
# ruff: noqa: E402 - Intentional lazy loading: commands imported after cli group definition

import platform
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from theauditor import __version__

# Windows console encoding fix
if platform.system() == "Windows":
    subprocess.run(["cmd", "/c", "chcp", "65001"], shell=False, capture_output=True, timeout=1)
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


class RichGroup(click.Group):
    """Rich-enabled help formatter that renders the CLI as a dashboard."""

    COMMAND_CATEGORIES = {
        "PROJECT_SETUP": {
            "title": "PROJECT SETUP",
            "style": "bold cyan",
            "description": "Initial configuration and environment setup",
            "commands": ["setup-ai", "tools"],
        },
        "CORE_ANALYSIS": {
            "title": "CORE ANALYSIS",
            "style": "bold green",
            "description": "Essential indexing and workset commands",
            "commands": ["full", "workset"],
        },
        "SECURITY_SCANNING": {
            "title": "SECURITY SCANNING",
            "style": "bold red",
            "description": "Vulnerability detection and taint analysis",
            "commands": ["detect-patterns", "taint-analyze", "boundaries", "detect-frameworks"],
        },
        "DEPENDENCIES": {
            "title": "DEPENDENCIES",
            "style": "bold yellow",
            "description": "Package analysis and documentation",
            "commands": ["deps", "docs"],
        },
        "CODE_QUALITY": {
            "title": "CODE QUALITY",
            "style": "bold magenta",
            "description": "Linting and complexity analysis",
            "commands": ["lint", "cfg", "graph", "graphql"],
        },
        "DATA_REPORTING": {
            "title": "DATA & REPORTING",
            "style": "bold blue",
            "description": "Analysis aggregation and report generation",
            "commands": ["fce", "structure", "summary", "metadata", "blueprint"],
        },
        "ADVANCED_QUERIES": {
            "title": "ADVANCED QUERIES",
            "style": "bold white",
            "description": "Direct database queries and impact analysis",
            "commands": ["explain", "query", "impact", "refactor"],
        },
        "INSIGHTS_ML": {
            "title": "INSIGHTS & ML",
            "style": "bold purple",
            "description": "Machine learning and risk predictions",
            "commands": ["insights", "learn", "suggest", "session"],
        },
        "UTILITIES": {
            "title": "UTILITIES",
            "style": "dim white",
            "description": "Educational and helper commands",
            "commands": ["manual", "planning"],
        },
    }

    def format_help(self, ctx, formatter):
        """Render help output using Rich components."""
        console = Console(force_terminal=sys.stdout.isatty())

        # Header
        console.print()
        console.rule(f"[bold]TheAuditor Security Platform v{__version__}[/bold]")
        console.print(
            "[center]Local-first | Air-gapped | Polyglot Static Analysis[/center]",
            style="dim"
        )
        console.print()

        # Get all registered commands
        registered = {
            name: cmd
            for name, cmd in self.commands.items()
            if not name.startswith("_") and not getattr(cmd, "hidden", False)
        }

        # Render Categories
        for cat_id, cat_data in self.COMMAND_CATEGORIES.items():
            # Create a table for commands in this category
            table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
            table.add_column("Command", style="bold white", width=20)
            table.add_column("Description", style="dim")

            has_commands = False
            for cmd_name in cat_data["commands"]:
                if cmd_name in registered:
                    cmd = registered[cmd_name]
                    # Extract short help
                    help_text = (cmd.help or "").split("\n")[0].strip()
                    if len(help_text) > 60:
                        help_text = help_text[:57] + "..."

                    table.add_row(f"aud {cmd_name}", help_text)
                    has_commands = True

            if has_commands:
                panel = Panel(
                    table,
                    title=f"[{cat_data['style']}]{cat_data['title']}[/]",
                    subtitle=f"[dim]{cat_data['description']}[/dim]",
                    subtitle_align="right",
                    border_style=cat_data['style'],
                    box=box.ROUNDED
                )
                console.print(panel)

        # Footer
        console.print()
        console.print(
            "[dim]Run [bold]aud <command> --help[/bold] for detailed usage options.[/dim]",
            justify="center"
        )
        console.print(
            "[dim]Run [bold]aud manual --list[/bold] for concept documentation.[/dim]",
            justify="center"
        )
        console.print()


@click.group(cls=RichGroup)
@click.version_option(version=__version__, prog_name="aud")
@click.help_option("-h", "--help")
def cli():
    """TheAuditor - Security & Code Intelligence Platform"""
    pass


# ------------------------------------------------------------------------------
# COMMAND REGISTRATION
# ------------------------------------------------------------------------------
from theauditor.commands._archive import _archive
from theauditor.commands.blueprint import blueprint
from theauditor.commands.boundaries import boundaries
from theauditor.commands.cdk import cdk
from theauditor.commands.cfg import cfg
from theauditor.commands.context import context_command
from theauditor.commands.deadcode import deadcode
from theauditor.commands.deps import deps
from theauditor.commands.detect_frameworks import detect_frameworks
from theauditor.commands.detect_patterns import detect_patterns
from theauditor.commands.docker_analyze import docker_analyze
from theauditor.commands.docs import docs
from theauditor.commands.explain import explain
from theauditor.commands.fce import fce
from theauditor.commands.full import full
from theauditor.commands.graph import graph
from theauditor.commands.graphql import graphql
from theauditor.commands.impact import impact
from theauditor.commands.index import index
from theauditor.commands.init import init
from theauditor.commands.init_config import init_config
from theauditor.commands.init_js import init_js
from theauditor.commands.insights import insights_command
from theauditor.commands.lint import lint
from theauditor.commands.manual import manual
from theauditor.commands.metadata import metadata
from theauditor.commands.ml import learn, learn_feedback, suggest
from theauditor.commands.planning import planning
from theauditor.commands.query import query
from theauditor.commands.refactor import refactor_command
from theauditor.commands.rules import rules_command
from theauditor.commands.session import session
from theauditor.commands.setup import setup_ai
from theauditor.commands.structure import structure
from theauditor.commands.summary import summary
from theauditor.commands.taint import taint_analyze
from theauditor.commands.terraform import terraform
from theauditor.commands.tools import tools
from theauditor.commands.workflows import workflows
from theauditor.commands.workset import workset

# Hidden/System Commands
init.hidden = True
index.hidden = True
cli.add_command(init)
cli.add_command(index)
cli.add_command(_archive)
cli.add_command(init_js)
cli.add_command(init_config)

# Setup & Core
cli.add_command(setup_ai)
cli.add_command(tools)
cli.add_command(full)
cli.add_command(workset)
cli.add_command(manual)

# Security
cli.add_command(detect_patterns)
cli.add_command(detect_frameworks)
cli.add_command(taint_analyze)
cli.add_command(boundaries)
cli.add_command(rules_command)
cli.add_command(docker_analyze)
cli.add_command(terraform)
cli.add_command(cdk)
cli.add_command(workflows)

# Dependencies & Docs
cli.add_command(deps)
cli.add_command(docs)

# Code Quality & Graph
cli.add_command(lint)
cli.add_command(cfg)
cli.add_command(graph)
cli.add_command(graphql)
cli.add_command(deadcode)

# Data & Reporting
cli.add_command(summary)
cli.add_command(fce)
cli.add_command(structure)
cli.add_command(metadata)
cli.add_command(blueprint)

# Advanced Queries
cli.add_command(query)
cli.add_command(explain)
cli.add_command(impact)
cli.add_command(refactor_command, name="refactor")
cli.add_command(context_command, name="context")

# Insights & ML
cli.add_command(insights_command, name="insights")
cli.add_command(learn)
cli.add_command(suggest)
cli.add_command(learn_feedback)
cli.add_command(session)
cli.add_command(planning)

# Legacy aliases
@click.command("setup-claude", hidden=True)
@click.pass_context
def setup_claude_alias(ctx, **kwargs):
    ctx.invoke(setup_ai, **kwargs)
setup_claude_alias.params = setup_ai.params
cli.add_command(setup_claude_alias)


def main():
    cli()


if __name__ == "__main__":
    main()
