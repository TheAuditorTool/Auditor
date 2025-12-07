"""TheAuditor CLI - Main entry point and command registration hub."""
# ruff: noqa: E402 - Intentional lazy loading: commands imported after cli group definition

import platform
import subprocess
import sys

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from theauditor import __version__
from theauditor.pipeline.ui import console

if platform.system() == "Windows":
    try:
        subprocess.run(["cmd", "/c", "chcp", "65001"], shell=False, capture_output=True, timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        pass
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
            "commands": ["detect-patterns", "taint", "boundaries", "detect-frameworks"],
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
        # Detect if this is a nested group (subcommand of another group)
        # If so, render subcommands list instead of the dashboard layout
        if ctx.parent is not None and self.commands:
            self._format_subgroup_help(ctx)
            return

        # Original dashboard rendering for top-level CLI
        console.print()
        console.rule(f"[bold]TheAuditor Security Platform v{__version__}[/bold]", characters="-")
        console.print(
            "[center]Local-first | Air-gapped | Polyglot Static Analysis[/center]", style="dim"
        )
        console.print()

        registered = {
            name: cmd
            for name, cmd in self.commands.items()
            if not name.startswith("_") and not getattr(cmd, "hidden", False)
        }

        for _cat_id, cat_data in self.COMMAND_CATEGORIES.items():
            table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
            table.add_column("Command", style="bold white", width=20)
            table.add_column("Description", style="dim")

            has_commands = False
            for cmd_name in cat_data["commands"]:
                if cmd_name in registered:
                    cmd = registered[cmd_name]

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
                    border_style=cat_data["style"],
                    box=box.ASCII,
                )
                console.print(panel)

        console.print()
        console.print(
            "[dim]Run [bold]aud <command> --help[/bold] for detailed usage options.[/dim]",
            justify="center",
        )
        console.print(
            "[dim]Run [bold]aud manual --list[/bold] for concept documentation.[/dim]",
            justify="center",
        )
        console.print()

    def _format_subgroup_help(self, ctx):
        """Render help for nested command groups (e.g., aud planning --help)."""
        group_name = ctx.info_name

        console.print()
        console.rule(f"[bold]aud {group_name}[/bold]", characters="-")

        # Show group docstring summary
        if self.help:
            # Extract first paragraph as summary
            lines = self.help.strip().split("\n\n")[0].split("\n")
            summary = " ".join(line.strip() for line in lines if line.strip())
            if summary:
                console.print(f"\n{summary}\n")

        # List all subcommands
        registered = {
            name: cmd
            for name, cmd in self.commands.items()
            if not name.startswith("_") and not getattr(cmd, "hidden", False)
        }

        if registered:
            table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
            table.add_column("Command", style="bold green", width=24)
            table.add_column("Description", style="dim")

            for cmd_name in sorted(registered.keys()):
                cmd = registered[cmd_name]
                help_text = (cmd.help or "").split("\n")[0].strip()
                if len(help_text) > 55:
                    help_text = help_text[:52] + "..."
                table.add_row(f"aud {group_name} {cmd_name}", help_text)

            panel = Panel(
                table,
                title="[bold cyan]SUBCOMMANDS[/bold cyan]",
                border_style="cyan",
                box=box.ASCII,
            )
            console.print(panel)

        console.print()
        console.print(
            f"[dim]Run [bold]aud {group_name} <command> --help[/bold] for detailed usage.[/dim]",
            justify="center",
        )
        console.print(
            f"[dim]Run [bold]aud manual {group_name}[/bold] for concept documentation.[/dim]",
            justify="center",
        )
        console.print()


class RichCommand(click.Command):
    """Rich-enabled help formatter for individual commands."""

    SECTIONS = [
        "AI ASSISTANT CONTEXT",
        "DESCRIPTION",
        "EXAMPLES",
        "COMMON WORKFLOWS",
        "OUTPUT FILES",
        "PERFORMANCE",
        "EXIT CODES",
        "RELATED COMMANDS",
        "SEE ALSO",
        "TROUBLESHOOTING",
        "NOTE",
        "WHAT IT DETECTS",
        "DATA FLOW ANALYSIS METHOD",
    ]

    def format_help(self, ctx, formatter):
        """Render help with Rich components."""

        console.print()
        console.rule(f"[bold]aud {ctx.info_name}[/bold]", characters="-")

        if self.help:
            sections = self._parse_docstring(self.help)
            self._render_sections(console, sections)

        self._render_options(console, ctx)

        console.print()

    def _parse_docstring(self, docstring: str) -> dict[str, str]:
        """Parse docstring into named sections."""
        sections = {"summary": ""}
        current_section = "summary"
        lines = docstring.strip().split("\n")

        for line in lines:
            stripped = line.strip()

            section_found = False
            for section_name in self.SECTIONS:
                if stripped.upper().startswith(section_name.upper()):
                    current_section = section_name.lower().replace(" ", "_")
                    sections[current_section] = ""
                    section_found = True
                    break

            if not section_found:
                if current_section in sections:
                    sections[current_section] += line + "\n"
                else:
                    sections[current_section] = line + "\n"

        return sections

    def _render_sections(self, console: Console, sections: dict):
        """Render parsed sections with Rich formatting."""

        if sections.get("summary"):
            summary = sections["summary"].strip()
            if summary:
                console.print(f"\n{summary}\n")

        if sections.get("ai_assistant_context"):
            panel = Panel(
                sections["ai_assistant_context"].strip(),
                title="[bold cyan]AI Assistant Context[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED,
            )
            console.print(panel)

        if sections.get("what_it_detects"):
            console.print("\n[bold]What It Detects:[/bold]")
            for line in sections["what_it_detects"].strip().split("\n"):
                if line.strip():
                    console.print(f"  {line}")

        if sections.get("data_flow_analysis_method"):
            console.print("\n[bold]Data Flow Analysis Method:[/bold]")
            for line in sections["data_flow_analysis_method"].strip().split("\n"):
                if line.strip():
                    console.print(f"  {line}")

        if sections.get("examples"):
            console.print("\n[bold]Examples:[/bold]")
            for line in sections["examples"].strip().split("\n"):
                stripped = line.strip()
                if stripped.startswith("aud "):
                    console.print(f"  [green]{stripped}[/green]")
                elif stripped.startswith("#"):
                    console.print(f"  [dim]{stripped}[/dim]")
                elif stripped:
                    console.print(f"  {line}")

        if sections.get("common_workflows"):
            console.print("\n[bold]Common Workflows:[/bold]")
            for line in sections["common_workflows"].strip().split("\n"):
                stripped = line.strip()
                if stripped.endswith(":") and not stripped.startswith("aud"):
                    console.print(f"\n  [cyan]{stripped}[/cyan]")
                elif stripped.startswith("aud "):
                    console.print(f"    [green]{stripped}[/green]")
                elif stripped:
                    console.print(f"    {line}")

        if sections.get("output_files"):
            console.print("\n[bold]Output Files:[/bold]")
            for line in sections["output_files"].strip().split("\n"):
                if line.strip():
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2 and ("/" in parts[0] or "." in parts[0]):
                        console.print(f"  [cyan]{parts[0]}[/cyan]  {parts[1]}")
                    else:
                        console.print(f"  {line}")

        if sections.get("performance"):
            console.print("\n[bold]Performance:[/bold]")
            for line in sections["performance"].strip().split("\n"):
                if line.strip():
                    console.print(f"  [dim]{line.strip()}[/dim]")

        if sections.get("exit_codes"):
            console.print("\n[bold]Exit Codes:[/bold]")
            for line in sections["exit_codes"].strip().split("\n"):
                stripped = line.strip()
                if stripped:
                    if "=" in stripped:
                        code, desc = stripped.split("=", 1)
                        console.print(f"  [yellow]{code.strip()}[/yellow] = {desc.strip()}")
                    else:
                        console.print(f"  {stripped}")

        if sections.get("related_commands"):
            console.print("\n[bold]Related Commands:[/bold]")
            for line in sections["related_commands"].strip().split("\n"):
                if line.strip():
                    console.print(f"  [dim]{line.strip()}[/dim]")

        if sections.get("see_also"):
            console.print("\n[bold]See Also:[/bold]")
            for line in sections["see_also"].strip().split("\n"):
                if line.strip():
                    console.print(f"  [cyan]{line.strip()}[/cyan]")

        if sections.get("troubleshooting"):
            console.print("\n[bold]Troubleshooting:[/bold]")
            for line in sections["troubleshooting"].strip().split("\n"):
                stripped = line.strip()
                if stripped.startswith("->"):
                    console.print(f"    [green]{stripped}[/green]")
                elif stripped:
                    console.print(f"  [yellow]{stripped}[/yellow]")

        if sections.get("note"):
            console.print()
            console.print(
                Panel(
                    sections["note"].strip(),
                    title="[bold yellow]Note[/bold yellow]",
                    border_style="yellow",
                    box=box.ROUNDED,
                )
            )

    def _render_options(self, console: Console, ctx):
        """Render options in a clean format."""
        params = self.get_params(ctx)
        options = [p for p in params if isinstance(p, click.Option)]

        if not options:
            return

        console.print("\n[bold]Options:[/bold]")

        for param in options:
            opts = ", ".join(param.opts)
            help_text = param.help or ""

            console.print(f"  [cyan]{opts}[/cyan]")

            if help_text:
                console.print(f"      {help_text}")

    def make_context(self, info_name, args, parent=None, **extra):
        """Override to show --help instead of ugly 'Missing argument' errors."""
        try:
            return super().make_context(info_name, args, parent, **extra)
        except click.MissingParameter as e:
            ctx = click.Context(self, info_name=info_name, parent=parent)
            self.format_help(ctx, None)
            console.print(f"\n[yellow]Required:[/yellow] {e.param.name}")
            console.print(f"[dim]Run 'aud {info_name} --help' for full details[/dim]\n")
            ctx.exit(0)


@click.group(cls=RichGroup)
@click.version_option(version=__version__, prog_name="aud")
@click.help_option("-h", "--help")
def cli():
    """TheAuditor - Security & Code Intelligence Platform"""
    pass


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
from theauditor.commands.taint import taint_analyze
from theauditor.commands.terraform import terraform
from theauditor.commands.tools import tools
from theauditor.commands.workflows import workflows
from theauditor.commands.workset import workset

cli.add_command(_archive)


cli.add_command(setup_ai)
cli.add_command(tools)
cli.add_command(full)
cli.add_command(workset)
cli.add_command(manual)


cli.add_command(detect_patterns)
cli.add_command(detect_frameworks)
cli.add_command(taint_analyze)
cli.add_command(boundaries)
cli.add_command(rules_command)
cli.add_command(docker_analyze)
cli.add_command(terraform)
cli.add_command(cdk)
cli.add_command(workflows)


cli.add_command(deps)
cli.add_command(docs)


cli.add_command(lint)
cli.add_command(cfg)
cli.add_command(graph)
cli.add_command(graphql)
cli.add_command(deadcode)


cli.add_command(fce)
cli.add_command(metadata)
cli.add_command(blueprint)


cli.add_command(query)
cli.add_command(explain)
cli.add_command(impact)
cli.add_command(refactor_command, name="refactor")
cli.add_command(context_command, name="context")


cli.add_command(learn)
cli.add_command(suggest)
cli.add_command(learn_feedback)
cli.add_command(session)
cli.add_command(planning)


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
