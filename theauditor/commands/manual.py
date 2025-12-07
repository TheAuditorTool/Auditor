"""Explain TheAuditor concepts and terminology."""

import click
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from theauditor.cli import RichCommand
from theauditor.commands.manual_lib01 import EXPLANATIONS_01
from theauditor.commands.manual_lib02 import EXPLANATIONS_02
from theauditor.commands.manual_lib03 import EXPLANATIONS_03
from theauditor.pipeline.ui import console

EXPLANATIONS: dict[str, dict[str, str]] = {**EXPLANATIONS_01, **EXPLANATIONS_02, **EXPLANATIONS_03}

# Aliases: redirect deprecated/redundant topics to canonical entries
# These won't appear in --list but will work as lookups
ALIASES: dict[str, str] = {
    "cfg": "graph",        # CFG is part of graph analysis
    "callgraph": "graph",  # Call graph is part of graph analysis
    "graphql": "graph",    # GraphQL schema analysis is part of graph
    "deps": "dependencies",  # Short alias
}


def _render_rich_explanation(info: dict) -> None:
    """Render a manual entry with Rich formatting."""
    console.print()

    title_text = Text(info["title"].upper(), style="bold cyan")
    console.print(Panel(title_text, border_style="cyan", padding=(0, 2)))

    console.print(f"\n[bold yellow]Summary:[/bold yellow] {info['summary']}\n")

    explanation = info.get("explanation", "")
    lines = explanation.strip().split("\n")

    current_section = None
    code_block = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped and stripped.endswith(":") and stripped[:-1].isupper():
            if in_code_block and code_block:
                _render_code_block(code_block)
                code_block = []
                in_code_block = False

            current_section = stripped[:-1]
            console.print(f"\n[bold cyan]{current_section}:[/bold cyan]")
            continue

        if stripped.startswith(
            ("aud ", "python ", "import ", "def ", "class ", "$", ">>>", "cursor.", "conn.")
        ):
            if not in_code_block:
                in_code_block = True
            code_block.append(line)
            continue

        if in_code_block and code_block:
            if not stripped or not line.startswith("    "):
                _render_code_block(code_block)
                code_block = []
                in_code_block = False

        if stripped.startswith("- "):
            if ": " in stripped[2:]:
                term, definition = stripped[2:].split(": ", 1)
                console.print(f"  [yellow]{term}:[/yellow] {definition}")
            else:
                console.print(f"  [dim]-[/dim] {stripped[2:]}")
            continue

        if stripped and stripped[0].isdigit() and ". " in stripped[:4]:
            num, rest = stripped.split(". ", 1)
            console.print(f"  [bold]{num}.[/bold] {rest}")
            continue

        if "# " in stripped and stripped.strip().startswith("aud "):
            parts = stripped.split("# ", 1)
            cmd = parts[0].strip()
            comment = parts[1] if len(parts) > 1 else ""
            console.print(f"    [green]{cmd}[/green]  [dim]# {comment}[/dim]")
            continue

        if stripped.startswith("aud "):
            console.print(f"    [green]{stripped}[/green]")
            continue

        if stripped:
            console.print(f"  {stripped}")
        elif not in_code_block:
            console.print()

    if in_code_block and code_block:
        _render_code_block(code_block)

    console.print()


def _render_code_block(lines: list[str]) -> None:
    """Render a code block with syntax highlighting."""
    code = "\n".join(line.strip() for line in lines if line.strip())

    if any(
        line.strip().startswith(("def ", "import ", "class ", "cursor.", "conn.")) for line in lines
    ):
        lang = "python"
    elif any(line.strip().startswith("aud ") for line in lines):
        lang = "bash"
    else:
        lang = "text"

    try:
        syntax = Syntax(code, lang, theme="monokai", line_numbers=False, padding=1)
        console.print(syntax)
    except Exception:
        for line in lines:
            console.print(f"    [green]{line.strip()}[/green]")


@click.command("manual", cls=RichCommand)
@click.argument("concept", required=False)
@click.option("--list", "list_concepts", is_flag=True, help="List all available concepts")
def manual(concept, list_concepts):
    """Interactive documentation for TheAuditor concepts, terminology, and security analysis techniques.

    Built-in reference system that explains security concepts, analysis methodologies, and tool-specific
    terminology through detailed, example-rich explanations optimized for learning. Covers 10 core topics
    from taint analysis to Rust language support, each with practical examples and related commands.

    AI ASSISTANT CONTEXT:
      Purpose: Provide interactive documentation for TheAuditor concepts
      Input: Concept name (taint, workset, fce, cfg, etc.)
      Output: Terminal-formatted explanation with examples
      Prerequisites: None (standalone documentation)
      Integration: Referenced throughout other command help texts
      Performance: Instant (no I/O, pure string formatting)

    AVAILABLE CONCEPTS (10 topics):
      taint:
        - Data flow tracking from untrusted sources to dangerous sinks
        - Detects SQL injection, XSS, command injection
        - Example: user_input -> query string -> database execution

      workset:
        - Focused file subset for targeted analysis (10-100x faster)
        - Git diff integration for PR review workflows
        - Dependency expansion algorithm

      fce:
        - Feed-forward Correlation Engine for compound risk detection
        - Combines static analysis + git churn + test coverage
        - Identifies hot spots (high churn + low coverage + vulnerabilities)

      cfg:
        - Control Flow Graphs for complexity and reachability analysis
        - Cyclomatic complexity calculation
        - Dead code detection via unreachable blocks

      impact:
        - Change impact analysis (blast radius)
        - Transitive dependency tracking
        - PR risk assessment

      pipeline:
        - Execution stages (index -> analyze -> correlate -> report)
        - Tool orchestration and data flow
        - .pf/ directory structure

      severity:
        - Finding classification (CRITICAL/HIGH/MEDIUM/LOW)
        - CVSS scoring integration
        - Severity promotion rules

      patterns:
        - Pattern detection system architecture
        - 2000+ built-in security rules
        - Custom pattern authoring

      insights:
        - ML-powered risk prediction
        - Historical learning from audit runs
        - Root cause vs symptom classification

      rust:
        - Rust language analysis (20 tables)
        - Module resolution (crate::, super::, use aliases)
        - Unsafe code detection and operation cataloging

    HOW IT WORKS (Documentation Lookup):
      1. Concept Validation:
         - Checks if concept exists in EXPLANATIONS dict
         - Shows available concepts if not found

      2. Explanation Retrieval:
         - Loads detailed explanation from internal database
         - Includes: title, summary, full explanation, examples

      3. Formatting:
         - Terminal-optimized layout with sections
         - Syntax highlighting for code examples
         - Links to related commands

    EXAMPLES:
      # Use Case 1: Learn about taint analysis
      aud manual taint

      # Use Case 2: Understand workset concept
      aud manual workset

      # Use Case 3: List all available topics
      aud manual --list

      # Use Case 4: Understand FCE correlation
      aud manual fce

    COMMON WORKFLOWS:
      Before First Analysis:
        aud manual pipeline      # Understand execution flow
        aud manual taint         # Learn security analysis
        aud full                 # Run complete audit (creates .pf/)

      Understanding Command Output:
        aud taint
        aud manual taint         # Learn what taint findings mean

      Troubleshooting Performance:
        aud manual workset       # Learn optimization techniques
        aud workset --diff HEAD

    OUTPUT FORMAT (Terminal Display):
      CONCEPT: Taint Analysis
      ----------------------------------------
      SUMMARY: Tracks untrusted data flow from sources to dangerous sinks

      EXPLANATION:
      Taint analysis is a security technique that tracks how untrusted data...
      [Detailed multi-paragraph explanation with examples]

      USE THE COMMAND:
        aud taint
        aud taint --severity high

    PERFORMANCE EXPECTATIONS:
      Instant: <1ms (pure string formatting, no I/O)

    FLAG INTERACTIONS:
      --list: Shows all 9 available concepts with one-line summaries

    PREREQUISITES:
      None (standalone documentation, works offline)

    EXIT CODES:
      0 = Success, explanation displayed
      1 = Unknown concept (use --list to see available)

    RELATED COMMANDS:
      All commands reference specific concepts in their help text
      Use 'aud <command> --help' for command-specific documentation

    SEE ALSO:
      TheAuditor documentation: docs/
      Online docs: https://github.com/user/theauditor

    TROUBLESHOOTING:
      Concept not found:
        -> Use 'aud manual --list' to see all available concepts
        -> Check spelling (case-sensitive: 'taint' not 'Taint')
        -> Some advanced concepts may not have explanations yet

      Output formatting issues:
        -> Terminal width <80 chars may cause wrapping
        -> Use terminal with proper UTF-8 support
        -> Pipe to 'less' for scrolling: aud manual fce | less

    NOTE: Explanations are embedded in the CLI for offline use. They cover
    core concepts but not every command detail - use --help on specific commands
    for comprehensive usage information.
    """

    if list_concepts:
        # Group concepts by category for organized display
        categories = {
            "Security Analysis": ["taint", "patterns", "boundaries", "fce", "rules"],
            "Architecture": ["blueprint", "graph", "dependencies", "deadcode", "explain"],
            "Workflows": ["pipeline", "workset", "severity", "impact", "session"],
            "Infrastructure": ["terraform", "cdk", "docker", "lint", "tools"],
            "Language Support": ["rust", "frameworks"],
            "Data & ML": ["database", "metadata", "ml", "insights"],
            "Configuration": ["refactor", "context", "planning", "setup", "env-vars"],
            "Reference": ["overview", "architecture", "gitflows", "exit-codes", "troubleshooting"],
        }

        console.print()
        console.print(
            Panel.fit(
                "[bold cyan]TheAuditor Manual[/bold cyan]\n"
                "[dim]Use 'aud manual <topic>' for detailed documentation[/dim]",
                border_style="cyan",
            )
        )

        # Build categorized display
        for cat_name, topic_keys in categories.items():
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Topic", style="green", width=16)
            table.add_column("Description", style="dim")
            for key in topic_keys:
                if key in EXPLANATIONS:
                    table.add_row(key, EXPLANATIONS[key]["summary"])
            if table.row_count > 0:
                console.print(Panel(table, title=f"[bold]{cat_name}[/bold]", border_style="blue"))

        # Show any uncategorized topics (excluding aliased entries)
        all_categorized = set(k for keys in categories.values() for k in keys)
        uncategorized = [k for k in EXPLANATIONS if k not in all_categorized and k not in ALIASES]
        if uncategorized:
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Topic", style="green", width=16)
            table.add_column("Description", style="dim")
            for key in sorted(uncategorized):
                table.add_row(key, EXPLANATIONS[key]["summary"])
            console.print(Panel(table, title="[bold]Other[/bold]", border_style="blue"))

        topic_count = len([k for k in EXPLANATIONS if k not in ALIASES])
        console.print(f"\n[dim]Total: {topic_count} topics available (plus {len(ALIASES)} aliases)[/dim]")
        console.print()
        return

    if not concept:
        console.print()
        console.print(
            Panel.fit(
                "[bold cyan]TheAuditor Manual[/bold cyan]\n"
                "[dim]Interactive documentation for security analysis concepts[/dim]",
                border_style="cyan",
            )
        )
        console.print()

        categories = {
            "SECURITY ANALYSIS": [
                ("taint", "Data flow from sources to sinks"),
                ("patterns", "Vulnerability pattern detection"),
                ("boundaries", "Entry point to control distance"),
                ("fce", "Multi-vector correlation engine"),
            ],
            "ARCHITECTURE": [
                ("blueprint", "Codebase structure overview"),
                ("graph", "Import, call graph, and CFG analysis"),
                ("dependencies", "Package dependency analysis"),
                ("deadcode", "Unused code detection"),
            ],
            "WORKFLOWS": [
                ("pipeline", "Multi-phase execution pipeline"),
                ("workset", "Targeted file subsets"),
                ("severity", "Finding classification levels"),
                ("rules", "Detection rule inventory"),
            ],
        }

        for cat_name, topics in categories.items():
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Topic", style="green", width=14)
            table.add_column("Description", style="dim")
            for topic, desc in topics:
                table.add_row(topic, desc)
            console.print(Panel(table, title=f"[bold]{cat_name}[/bold]", border_style="blue"))

        console.print()
        console.print(
            "[dim]Usage:[/dim]  aud manual <topic>     [dim]Example:[/dim] aud manual taint"
        )
        console.print("[dim]List all:[/dim] aud manual --list")
        console.print()
        return

    concept = concept.lower().strip()

    # Resolve aliases (cfg -> graph, deps -> dependencies, etc.)
    if concept in ALIASES:
        canonical = ALIASES[concept]
        console.print(f"[dim]'{concept}' redirects to '{canonical}'[/dim]\n")
        concept = canonical

    if concept not in EXPLANATIONS:
        console.print(f"Unknown concept: '{concept}'", highlight=False)
        console.print("\nAvailable concepts:")
        for key in sorted(EXPLANATIONS.keys()):
            console.print(f"  - {key}", highlight=False)
        console.print("\nAliases:")
        for alias, target in ALIASES.items():
            console.print(f"  - {alias} -> {target}", highlight=False)
        return

    info = EXPLANATIONS[concept]
    _render_rich_explanation(info)
