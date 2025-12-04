"""Explain TheAuditor concepts and terminology."""

import click
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from theauditor.cli import RichCommand
from theauditor.commands.manual_lib01 import EXPLANATIONS_01
from theauditor.commands.manual_lib02 import EXPLANATIONS_02
from theauditor.pipeline.ui import console

# Merge both explanation libraries into single dict
EXPLANATIONS: dict[str, dict[str, str]] = {**EXPLANATIONS_01, **EXPLANATIONS_02}


def _render_rich_explanation(info: dict) -> None:
    """Render a manual entry with Rich formatting."""
    console.print()

    # Title panel
    title_text = Text(info["title"].upper(), style="bold cyan")
    console.print(Panel(title_text, border_style="cyan", padding=(0, 2)))

    # Summary
    console.print(f"\n[bold yellow]Summary:[/bold yellow] {info['summary']}\n")

    # Parse and render explanation with Rich markup
    explanation = info.get("explanation", "")
    lines = explanation.strip().split("\n")

    current_section = None
    code_block = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Detect section headers (UPPERCASE followed by colon)
        if stripped and stripped.endswith(":") and stripped[:-1].isupper():
            # Flush any pending code block
            if in_code_block and code_block:
                _render_code_block(code_block)
                code_block = []
                in_code_block = False

            current_section = stripped[:-1]
            console.print(f"\n[bold cyan]{current_section}:[/bold cyan]")
            continue

        # Detect code blocks (indented lines starting with common code patterns)
        if stripped.startswith(("aud ", "python ", "import ", "def ", "class ", "$", ">>>", "cursor.", "conn.")):
            if not in_code_block:
                in_code_block = True
            code_block.append(line)
            continue

        # If we were in a code block but this line doesn't look like code
        if in_code_block and code_block:
            if not stripped or not line.startswith("    "):
                _render_code_block(code_block)
                code_block = []
                in_code_block = False

        # Handle bullet points
        if stripped.startswith("- "):
            # Check for term:definition pattern
            if ": " in stripped[2:]:
                term, definition = stripped[2:].split(": ", 1)
                console.print(f"  [yellow]{term}:[/yellow] {definition}")
            else:
                console.print(f"  [dim]-[/dim] {stripped[2:]}")
            continue

        # Handle numbered lists
        if stripped and stripped[0].isdigit() and ". " in stripped[:4]:
            num, rest = stripped.split(". ", 1)
            console.print(f"  [bold]{num}.[/bold] {rest}")
            continue

        # Handle example commands with comments
        if "# " in stripped and stripped.strip().startswith("aud "):
            parts = stripped.split("# ", 1)
            cmd = parts[0].strip()
            comment = parts[1] if len(parts) > 1 else ""
            console.print(f"    [green]{cmd}[/green]  [dim]# {comment}[/dim]")
            continue

        # Handle standalone commands
        if stripped.startswith("aud "):
            console.print(f"    [green]{stripped}[/green]")
            continue

        # Regular text
        if stripped:
            console.print(f"  {stripped}")
        elif not in_code_block:
            console.print()

    # Flush any remaining code block
    if in_code_block and code_block:
        _render_code_block(code_block)

    console.print()


def _render_code_block(lines: list[str]) -> None:
    """Render a code block with syntax highlighting."""
    code = "\n".join(line.strip() for line in lines if line.strip())

    # Detect language
    if any(line.strip().startswith(("def ", "import ", "class ", "cursor.", "conn.")) for line in lines):
        lang = "python"
    elif any(line.strip().startswith("aud ") for line in lines):
        lang = "bash"
    else:
        lang = "text"

    try:
        syntax = Syntax(code, lang, theme="monokai", line_numbers=False, padding=1)
        console.print(syntax)
    except Exception:
        # Fallback to plain text
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
        aud init && aud full

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
        console.print("\nAvailable concepts to explain:\n")
        for key, info in EXPLANATIONS.items():
            console.print(f"  {key:12} - {info['summary']}", highlight=False)
        console.print("\nUse 'aud manual <concept>' for detailed information.")
        return

    if not concept:
        console.print("Please specify a concept to explain or use --list to see available topics.")
        console.print("\nExample: aud manual taint")
        return

    concept = concept.lower().strip()

    if concept not in EXPLANATIONS:
        console.print(f"Unknown concept: '{concept}'", highlight=False)
        console.print("\nAvailable concepts:")
        for key in EXPLANATIONS:
            console.print(f"  - {key}", highlight=False)
        return

    info = EXPLANATIONS[concept]
    _render_rich_explanation(info)
