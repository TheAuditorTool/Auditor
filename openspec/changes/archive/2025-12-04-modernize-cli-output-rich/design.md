# Design: Rich CLI Help Modernization

## Technical Architecture

### Current State Analysis

**Main Help (cli.py:24-138) - Already Rich:**
```python
class RichGroup(click.Group):
    def format_help(self, ctx, formatter):
        console = Console(force_terminal=sys.stdout.isatty())
        # Renders beautiful panels with Rich
```

**Subcommand Help - Click Default:**
Click uses `HelpFormatter` which:
1. Extracts docstring as plain text
2. Word-wraps at terminal width (often badly)
3. Renders options in basic format
4. No color, no structure, no love

### Solution: RichCommand Class

Create `RichCommand(click.Command)` that overrides `format_help()` to render with Rich.

```python
class RichCommand(click.Command):
    """Rich-enabled help formatter for individual commands."""

    # Section markers in docstrings
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
    ]

    def format_help(self, ctx, formatter):
        """Render help with Rich components."""
        console = Console(theme=AUDITOR_THEME, force_terminal=sys.stdout.isatty())

        # 1. Header with command name
        console.print()
        console.rule(f"[bold]aud {ctx.info_name}[/bold]")

        # 2. Parse docstring into sections
        if self.help:
            sections = self._parse_docstring(self.help)
            self._render_sections(console, sections)

        # 3. Render options
        self._render_options(console, ctx)

        console.print()

    def _parse_docstring(self, docstring: str) -> dict[str, str]:
        """Parse docstring into named sections."""
        sections = {"summary": "", "description": ""}
        current_section = "summary"
        lines = docstring.strip().split("\n")

        for line in lines:
            stripped = line.strip()

            # Check for section header
            for section_name in self.SECTIONS:
                if stripped.upper().startswith(section_name):
                    current_section = section_name.lower().replace(" ", "_")
                    sections[current_section] = ""
                    break
            else:
                # Add to current section
                if current_section in sections:
                    sections[current_section] += line + "\n"
                else:
                    sections[current_section] = line + "\n"

        return sections

    def _render_sections(self, console: Console, sections: dict):
        """Render parsed sections with Rich formatting."""

        # Summary (first line, prominent)
        if sections.get("summary"):
            console.print(f"\n{sections['summary'].strip()}\n")

        # Description (expanded paragraph)
        if sections.get("description"):
            console.print(sections["description"].strip())
            console.print()

        # AI Assistant Context (panel - key section for AI tools)
        if sections.get("ai_assistant_context"):
            panel = Panel(
                sections["ai_assistant_context"].strip(),
                title="[bold cyan]AI Assistant Context[/bold cyan]",
                border_style="cyan",
            )
            console.print(panel)

        # Examples (code block style with syntax highlighting)
        if sections.get("examples"):
            console.print("\n[bold]Examples:[/bold]")
            for line in sections["examples"].strip().split("\n"):
                if line.strip().startswith("aud "):
                    console.print(f"  [green]{line.strip()}[/green]")
                elif line.strip().startswith("#"):
                    console.print(f"  [dim]{line.strip()}[/dim]")
                else:
                    console.print(f"  {line}")

        # Common Workflows (named scenarios)
        if sections.get("common_workflows"):
            console.print("\n[bold]Common Workflows:[/bold]")
            for line in sections["common_workflows"].strip().split("\n"):
                if line.strip().endswith(":") and not line.strip().startswith("aud"):
                    console.print(f"\n  [cyan]{line.strip()}[/cyan]")
                elif line.strip().startswith("aud "):
                    console.print(f"    [green]{line.strip()}[/green]")
                else:
                    console.print(f"    {line}")

        # Output Files (file paths with descriptions)
        if sections.get("output_files"):
            console.print("\n[bold]Output Files:[/bold]")
            for line in sections["output_files"].strip().split("\n"):
                if line.strip():
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2:
                        console.print(f"  [cyan]{parts[0]}[/cyan]  {parts[1]}")
                    else:
                        console.print(f"  {line}")

        # Performance (timing expectations)
        if sections.get("performance"):
            console.print("\n[bold]Performance:[/bold]")
            for line in sections["performance"].strip().split("\n"):
                if line.strip():
                    console.print(f"  [dim]{line.strip()}[/dim]")

        # Exit Codes (meaningful codes for scripting)
        if sections.get("exit_codes"):
            console.print("\n[bold]Exit Codes:[/bold]")
            for line in sections["exit_codes"].strip().split("\n"):
                if line.strip():
                    if "=" in line:
                        code, desc = line.split("=", 1)
                        console.print(f"  [yellow]{code.strip()}[/yellow] = {desc.strip()}")
                    else:
                        console.print(f"  {line}")

        # Related Commands (cross-references)
        if sections.get("related_commands"):
            console.print("\n[bold]Related Commands:[/bold]")
            for line in sections["related_commands"].strip().split("\n"):
                if line.strip():
                    console.print(f"  [dim]{line.strip()}[/dim]")

        # See Also (manual references)
        if sections.get("see_also"):
            console.print("\n[bold]See Also:[/bold]")
            for line in sections["see_also"].strip().split("\n"):
                if line.strip():
                    console.print(f"  [cyan]{line.strip()}[/cyan]")

        # Troubleshooting (problem -> solution format)
        if sections.get("troubleshooting"):
            console.print("\n[bold]Troubleshooting:[/bold]")
            for line in sections["troubleshooting"].strip().split("\n"):
                if line.strip().startswith("->"):
                    console.print(f"    [green]{line.strip()}[/green]")
                elif line.strip():
                    console.print(f"  [yellow]{line.strip()}[/yellow]")

        # Note (important caveats)
        if sections.get("note"):
            console.print()
            console.print(Panel(
                sections["note"].strip(),
                title="[bold yellow]Note[/bold yellow]",
                border_style="yellow",
            ))

    def _render_options(self, console: Console, ctx):
        """Render options in a clean table format."""
        console.print("\n[bold]Options:[/bold]")

        for param in self.get_params(ctx):
            if isinstance(param, click.Option):
                opts = ", ".join(param.opts)
                help_text = param.help or ""
                console.print(f"  [cyan]{opts}[/cyan]")
                if help_text:
                    console.print(f"      {help_text}")
```

### Integration Points

**1. cli.py Registration:**
Commands using RichCommand must be decorated:
```python
@click.command(cls=RichCommand)
def taint_analyze(...):
    """One-line summary.

    AI ASSISTANT CONTEXT:
      Purpose: Detects injection vulnerabilities
      ...
    """
```

**2. Group Commands:**
For group commands like `aud graph`, use `RichGroup` for the group and `RichCommand` for subcommands:
```python
@click.group(cls=RichGroup)
def graph():
    """Graph analysis group."""

@graph.command(cls=RichCommand)
def build():
    """Build import and call graphs."""
```

---

## Docstring Format Specification

### Canonical Structure

```python
"""One-line summary (appears in main aud --help).

DESCRIPTION:
  2-3 sentences expanding on the summary. Explains what
  the command does in plain language.

AI ASSISTANT CONTEXT:
  Purpose: What this command accomplishes
  Input: Required files, databases, or prior commands
  Output: What files/data are produced
  Prerequisites: Commands that must run first
  Integration: How this fits in the pipeline
  Performance: Typical execution time

EXAMPLES:
  aud command --basic                  # Basic usage
  aud command --option value           # With options
  aud command --flag | other-tool      # Pipeline example

COMMON WORKFLOWS:
  Before deployment:
    aud full && aud command --strict

  PR review:
    aud workset --diff main && aud command --workset

OUTPUT FILES:
  .pf/raw/output.json    Analysis results
  .pf/report.md          Human-readable summary

PERFORMANCE:
  Small (<5K LOC):   ~10 seconds
  Medium (20K LOC):  ~30 seconds
  Large (100K+ LOC): ~5 minutes

EXIT CODES:
  0 = Success
  1 = Findings detected
  2 = Critical issues
  3 = Analysis failed

RELATED COMMANDS:
  aud other-command    Brief description of relationship
  aud another          Why you might use this instead

SEE ALSO:
  aud manual concept   Learn about underlying concepts

TROUBLESHOOTING:
  Error: "Database not found"
    -> Run 'aud full' first to create index

  Slow performance:
    -> Use --workset to limit scope

NOTE:
  Important caveats or warnings about usage.
"""
```

### Section Formatting Rules

| Section | Format | Required |
|---------|--------|----------|
| Summary | Single line, no period | YES |
| DESCRIPTION | 2-3 sentences, paragraph | NO |
| AI ASSISTANT CONTEXT | Key-value pairs, indented | YES for main commands |
| EXAMPLES | Code lines with comments | YES |
| COMMON WORKFLOWS | Named scenarios with commands | NO |
| OUTPUT FILES | File paths with descriptions | NO |
| PERFORMANCE | Size categories with times | NO |
| EXIT CODES | Number = Description format | YES for commands with meaningful codes |
| RELATED COMMANDS | Command + description | NO |
| SEE ALSO | Manual references | NO |
| TROUBLESHOOTING | Problem -> Solution format | NO |
| NOTE | Single important caveat | NO |

---

## Manual Entry Rich Format

### Current Format (manual.py)
```python
EXPLANATIONS = {
    "taint": {
        "title": "Taint Analysis",
        "summary": "Tracks untrusted data flow...",
        "explanation": """
Taint analysis is a security technique...

CONCEPTS:
- Source: Where untrusted data enters
- Sink: Dangerous operations
...
"""
    }
}
```

### Target Format
```python
EXPLANATIONS = {
    "taint": {
        "title": "Taint Analysis",
        "summary": "Tracks untrusted data flow...",
        "sections": [
            {
                "name": "Concepts",
                "style": "panel",
                "content": """
[yellow]Source[/yellow]: Where untrusted data enters (user input, network, files)
[yellow]Sink[/yellow]: Dangerous operations (SQL queries, system commands)
[yellow]Taint[/yellow]: The property of being untrusted/contaminated
[yellow]Propagation[/yellow]: How taint spreads through assignments
"""
            },
            {
                "name": "How It Works",
                "style": "numbered",
                "content": """
1. Identify taint sources (request.body, input())
2. Track data flow through variables and functions
3. Check if tainted data reaches dangerous sinks
4. Report potential vulnerabilities
"""
            },
            {
                "name": "Example Vulnerability",
                "style": "code",
                "language": "python",
                "content": """
user_input = request.body.get('name')  # SOURCE
query = f"SELECT * WHERE name = '{user_input}'"  # Taint propagates
db.execute(query)  # SINK: SQL injection!
"""
            },
            {
                "name": "What TheAuditor Detects",
                "style": "bullets",
                "content": """
- SQL Injection (tainted data -> SQL query)
- Command Injection (tainted data -> system command)
- XSS (tainted data -> HTML output)
- Path Traversal (tainted data -> file path)
"""
            }
        ]
    }
}
```

### Render Function
```python
def _render_explanation(console: Console, entry: dict):
    """Render a manual entry with Rich formatting."""

    # Title
    console.rule(f"[bold]{entry['title'].upper()}[/bold]")

    for section in entry.get("sections", []):
        style = section.get("style", "text")
        name = section.get("name", "")
        content = section.get("content", "")

        if name:
            console.print(f"\n[bold cyan]{name}[/bold cyan]")

        if style == "panel":
            console.print(Panel(content.strip()))
        elif style == "code":
            lang = section.get("language", "")
            console.print(Syntax(content.strip(), lang, theme="monokai"))
        elif style == "numbered":
            for line in content.strip().split("\n"):
                console.print(f"  {line}")
        elif style == "bullets":
            for line in content.strip().split("\n"):
                if line.strip().startswith("-"):
                    console.print(f"  [dim]-[/dim] {line.strip()[1:].strip()}")
        else:
            console.print(content)

    console.rule()
```

---

## Migration Checklist Per File

For each command file:

1. [ ] Read current docstring
2. [ ] Identify sections that exist vs missing
3. [ ] Reformat into canonical structure
4. [ ] Update outdated content
5. [ ] Fix grammar/style issues
6. [ ] Add `cls=RichCommand` to decorator
7. [ ] Test with `aud command --help`
8. [ ] Verify output looks correct

---

## Content Modernization Guidelines

### Outdated Patterns to Fix

| Pattern | Outdated | Modern |
|---------|----------|--------|
| Index command | "Run `aud index` first" | "Run `aud full` (includes indexing)" |
| Database path | "repo_index.db" | ".pf/repo_index.db" |
| Pipeline stages | 10 phases | 20+ phases (4 stages) |
| Languages | "Python and JavaScript" | "Python, JavaScript, TypeScript, Go, Rust, Bash" |
| Output location | Various | "All output in .pf/ directory" |

### Sterile Language to Fix

| Sterile | Human |
|---------|-------|
| "Performs inter-procedural data flow analysis" | "Traces data from user input to dangerous functions" |
| "Detects injection vulnerabilities via taint propagation" | "Finds where hackers could inject malicious code" |
| "Computes transitive closure of dependency graph" | "Shows everything affected by a code change" |
| "Implements IFDS algorithm for path-sensitive analysis" | "Smart enough to know if input was validated first" |

### Terminology Consistency

| Use This | Not This |
|----------|----------|
| TheAuditor | theauditor, the auditor |
| finding | issue, vulnerability, problem |
| .pf/ directory | output directory, working directory |
| aud full | aud index (deprecated) |
| workset | file subset, target files |
