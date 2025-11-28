"""TheAuditor CLI - Main entry point and command registration hub."""
# ruff: noqa: E402 - Intentional lazy loading: commands imported after cli group definition

import platform
import subprocess
import sys

import click
from rich.table import Table

from theauditor import __version__
from theauditor.pipeline.ui import console

if platform.system() == "Windows":
    subprocess.run(["cmd", "/c", "chcp", "65001"], shell=False, capture_output=True, timeout=1)
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


class VerboseGroup(click.Group):
    """AI-First help system - dynamically generates help from registered commands."""

    def format_commands(self, ctx, formatter):
        """Override to suppress default command listing (we use categorized format in format_help)."""
        pass

    COMMAND_CATEGORIES = {
        "PROJECT_SETUP": {
            "title": "PROJECT SETUP",
            "description": "Initial configuration and environment setup",
            "commands": ["setup-ai", "tools"],
            "ai_context": "Run these FIRST in new projects. Creates .pf/ structure, installs tools.",
            "command_meta": {
                "setup-ai": {
                    "run_when": "Once per project, before first aud full",
                },
                "tools": {
                    "use_when": "Verify tool installation, check versions",
                    "gives": "Tool availability status, version report",
                },
            },
        },
        "CORE_ANALYSIS": {
            "title": "CORE ANALYSIS",
            "description": "Essential indexing and workset commands",
            "commands": ["full", "workset"],
            "ai_context": "Foundation commands. full runs complete audit, workset filters scope.",
            "command_meta": {
                "full": {
                    "run_when": "First time, or after major code changes",
                },
                "workset": {
                    "use_when": "Need incremental analysis on file subset",
                    "gives": "Filtered file list for targeted scans",
                },
            },
        },
        "SECURITY_SCANNING": {
            "title": "SECURITY SCANNING",
            "description": "Vulnerability detection and taint analysis",
            "commands": [
                "detect-patterns",
                "taint-analyze",
                "boundaries",
                "docker-analyze",
                "detect-frameworks",
                "rules",
                "context",
                "workflows",
                "cdk",
                "terraform",
                "deadcode",
            ],
            "ai_context": "Security-focused analysis. detect-patterns=rules, taint-analyze=data flow, boundaries=control distance.",
            "command_meta": {
                "detect-patterns": {
                    "use_when": "Need security vulnerability scan",
                    "gives": "200+ rule findings with file:line",
                },
                "taint-analyze": {
                    "use_when": "Need data flow analysis (source to sink)",
                    "gives": "Taint paths with vulnerability type",
                },
                "boundaries": {
                    "use_when": "Checking trust boundary enforcement",
                    "gives": "Trust boundary violations",
                },
            },
        },
        "DEPENDENCIES": {
            "title": "DEPENDENCIES",
            "description": "Package analysis and documentation",
            "commands": ["deps", "docs"],
            "ai_context": "deps checks CVEs and versions, docs fetches/summarizes package documentation.",
            "command_meta": {
                "deps": {
                    "use_when": "Need CVE check or dependency analysis",
                    "gives": "Vulnerability report, outdated packages",
                },
                "docs": {
                    "use_when": "Need package documentation summary",
                    "gives": "AI-summarized docs for dependencies",
                },
            },
        },
        "CODE_QUALITY": {
            "title": "CODE QUALITY",
            "description": "Linting and complexity analysis",
            "commands": ["lint", "cfg", "graph", "graphql"],
            "ai_context": "Quality checks. lint=linters, cfg=complexity, graph=architecture, graphql=schema analysis.",
            "command_meta": {
                "lint": {
                    "use_when": "Need code quality check",
                    "gives": "Linter findings with file:line",
                },
                "cfg": {
                    "use_when": "Need complexity analysis",
                    "gives": "Cyclomatic complexity, dead code",
                },
                "graph": {
                    "run_when": "After aud full, for dependency visualization",
                    "gives": "Import graph, circular dependencies",
                },
            },
        },
        "DATA_REPORTING": {
            "title": "DATA & REPORTING",
            "description": "Analysis aggregation and report generation",
            "commands": ["fce", "structure", "summary", "metadata", "blueprint"],
            "ai_context": "fce correlates findings, structure maps codebase, query reads from database.",
            "command_meta": {
                "fce": {
                    "use_when": "Need correlated findings across tools",
                    "gives": "Compound vulnerabilities, evidence chains",
                },
                "structure": {
                    "use_when": "Need project architecture overview",
                    "gives": "Module map, entry points, tech stack",
                },
            },
        },
        "ADVANCED_QUERIES": {
            "title": "ADVANCED QUERIES",
            "description": "Direct database queries and impact analysis",
            "commands": ["explain", "query", "impact", "refactor"],
            "ai_context": "explain=comprehensive context, query=SQL-like symbol lookup, impact=blast radius, refactor=migration analysis.",
            "command_meta": {
                "explain": {
                    "use_when": "Need to understand code before editing",
                    "gives": "Definitions, dependencies, callers, callees",
                },
                "query": {
                    "use_when": "Need specific facts (Who calls X?, Where is Y?)",
                    "gives": "Exact file:line locations and relationships",
                },
                "impact": {
                    "use_when": "Assessing blast radius of changes",
                    "gives": "Upstream/downstream dependency counts",
                },
                "refactor": {
                    "use_when": "Detecting incomplete migrations",
                    "gives": "Broken imports, orphan code locations",
                },
            },
        },
        "INSIGHTS_ML": {
            "title": "INSIGHTS & ML",
            "description": "Machine learning and risk predictions",
            "commands": ["insights", "learn", "suggest", "learn-feedback", "session"],
            "ai_context": "Optional ML layer. learn trains models, suggest predicts risky files, session analyzes AI agent behavior.",
            "command_meta": {
                "insights": {
                    "use_when": "Need ML-powered risk predictions",
                    "gives": "Health scores, risk rankings",
                },
                "suggest": {
                    "use_when": "Need AI file review suggestions",
                    "gives": "Prioritized list of risky files",
                },
            },
        },
        "UTILITIES": {
            "title": "UTILITIES",
            "description": "Educational and helper commands",
            "commands": ["manual", "planning"],
            "ai_context": "manual teaches concepts (taint, workset, fce), planning tracks work.",
            "command_meta": {
                "manual": {
                    "use_when": "Need concept explanation or troubleshooting",
                    "gives": "Detailed docs for taint, workset, fce, etc.",
                },
                "planning": {
                    "use_when": "Need to track analysis work",
                    "gives": "Task tracking and planning output",
                },
            },
        },
    }

    def format_help(self, ctx, formatter):
        """Generate Rich-styled categorized help with AI routing annotations."""
        # Let Click handle the basic header (Usage, Options)
        super().format_help(ctx, formatter)

        registered = {
            name: cmd
            for name, cmd in self.commands.items()
            if not name.startswith("_") and not getattr(cmd, "hidden", False)
        }

        # Build Rich output
        console.print()
        console.rule("[bold]COMMANDS[/bold]")

        for _category_id, category_data in self.COMMAND_CATEGORIES.items():
            # Category header
            console.print(f"\n[bold cyan]{category_data['title']}[/bold cyan]")
            console.print(f"[dim]{category_data['description']}[/dim]")

            # Build table for this category
            table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
            table.add_column("Command", style="cmd", width=18)
            table.add_column("Description", style="white")
            table.add_column("AI Context", style="dim", width=40)

            for cmd_name in category_data["commands"]:
                if cmd_name not in registered:
                    continue
                cmd = registered[cmd_name]

                # Extract short description
                first_line = (cmd.help or "").split("\n")[0].strip()
                period_idx = first_line.find(".")
                short_help = first_line[:period_idx] if period_idx > 0 else first_line
                if len(short_help) > 45:
                    short_help = short_help[:45].rsplit(" ", 1)[0] + "..."

                # Get AI context
                cmd_meta = category_data.get("command_meta", {}).get(cmd_name, {})
                ai_hint = ""
                if "use_when" in cmd_meta:
                    ai_hint = f"USE: {cmd_meta['use_when']}"
                elif "run_when" in cmd_meta:
                    ai_hint = f"RUN: {cmd_meta['run_when']}"

                table.add_row(cmd_name, short_help, ai_hint)

            console.print(table)

        console.print()
        console.rule()
        console.print("For detailed options: [cmd]aud <command> --help[/cmd]")
        console.print("For concepts: [cmd]aud manual --list[/cmd]")


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

init.hidden = True
index.hidden = True
cli.add_command(init)
cli.add_command(index)
cli.add_command(workset)
cli.add_command(lint)
cli.add_command(deps)
cli.add_command(summary)
cli.add_command(full)
cli.add_command(fce)
cli.add_command(impact)
cli.add_command(taint_analyze)
cli.add_command(boundaries)
cli.add_command(setup_ai)


@click.command("setup-claude", hidden=True)
@click.pass_context
def setup_claude_alias(ctx, **kwargs):
    """Deprecated: Use setup-ai instead."""
    ctx.invoke(setup_ai, **kwargs)


setup_claude_alias.params = setup_ai.params
cli.add_command(setup_claude_alias)
cli.add_command(manual)


cli.add_command(detect_patterns)
cli.add_command(detect_frameworks)
cli.add_command(docs)
cli.add_command(tools)
cli.add_command(init_js)
cli.add_command(init_config)


cli.add_command(learn)
cli.add_command(suggest)
cli.add_command(learn_feedback)


cli.add_command(_archive)


cli.add_command(rules_command)


cli.add_command(refactor_command, name="refactor")
cli.add_command(insights_command, name="insights")
cli.add_command(context_command, name="context")
cli.add_command(query)
cli.add_command(explain)
cli.add_command(blueprint)


cli.add_command(docker_analyze)
cli.add_command(structure)


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


def main():
    """Main entry point for console script."""
    cli()


if __name__ == "__main__":
    main()
