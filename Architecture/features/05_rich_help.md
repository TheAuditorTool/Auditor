# TheAuditor Rich Help System

## Overview

TheAuditor implements a sophisticated, **Rich-formatted help system** that transforms standard `--help` output into an interactive, color-coded dashboard. The system uses Rich panels, tables, and semantic formatting across 9 command categories with 13 recognized help sections.

---

## Two-Tier Architecture

### Tier 1: RichGroup (Main Dashboard)
**Command**: `aud --help`

Displays TheAuditor version and 9 command categories as colored panels:

```
┌─ [BOLD GREEN]CORE ANALYSIS[/] ──────────────────────┐
│ Command              Description                    │
│ aud full             Run comprehensive audit        │
│ aud workset          Create targeted file list      │
└─ [dim]Essential indexing commands[/] ───────────────┘
```

### Tier 2: RichCommand (Individual Help)
**Command**: `aud <command> --help`

Per-command help with Rich components, structured docstring parsing, and 13 semantic sections.

---

## 9 Command Categories

| Category | Color | Commands |
|----------|-------|----------|
| **PROJECT SETUP** | bold cyan | `setup-ai`, `tools` |
| **CORE ANALYSIS** | bold green | `full`, `workset` |
| **SECURITY SCANNING** | bold red | `detect-patterns`, `taint`, `boundaries` |
| **DEPENDENCIES** | bold yellow | `deps`, `docs` |
| **CODE QUALITY** | bold magenta | `lint`, `cfg`, `graph`, `graphql` |
| **DATA & REPORTING** | bold blue | `fce`, `metadata`, `blueprint` |
| **ADVANCED QUERIES** | bold white | `explain`, `query`, `impact`, `refactor` |
| **INSIGHTS & ML** | bold purple | `insights`, `learn`, `suggest`, `session` |
| **UTILITIES** | dim white | `manual`, `planning` |

---

## 13 Recognized Help Sections

| Section | Rendering |
|---------|-----------|
| **SUMMARY** | Plain text at top |
| **AI ASSISTANT CONTEXT** | Cyan rounded panel |
| **DESCRIPTION** | Multi-paragraph text |
| **EXAMPLES** | Green command text |
| **COMMON WORKFLOWS** | Cyan workflow headers |
| **OUTPUT FILES** | Cyan file paths |
| **PERFORMANCE** | Dim timing estimates |
| **EXIT CODES** | Yellow status codes |
| **WHAT IT DETECTS** | Bold section headers |
| **DATA FLOW ANALYSIS METHOD** | Numbered steps |
| **RELATED COMMANDS** | Dim references |
| **TROUBLESHOOTING** | Yellow problems, green solutions |
| **NOTE** | Yellow rounded panel |

---

## Example: taint Command Help

```
─ aud taint ─────────────────────────────────────────────────

Trace data flow from untrusted sources to dangerous sinks...

┌─ [bold cyan]AI Assistant Context[/bold cyan] ─────────────┐
│ Purpose: Detects injection vulnerabilities via       │
│ taint propagation analysis                           │
│ Input: .pf/repo_index.db                             │
│ Output: .pf/raw/taint_analysis.json                  │
└─────────────────────────────────────────────────────┘

[bold]What It Detects:[/bold]
  SQL Injection: cursor.execute("... {user_input}")
  Command Injection: os.system(f"ping {user_input}")

[bold]Examples:[/bold]
  [green]aud full[/green]
  [green]aud taint --severity high[/green]

[bold]Troubleshooting:[/bold]
  [yellow]Database not found:[/yellow]
    [green]-> Run 'aud full' first[/green]
```

---

## How It Differs from Standard --help

| Aspect | Standard | Rich |
|--------|----------|------|
| Colors | None | 9+ semantic colors |
| Panels | None | AI Context, Notes |
| Sections | Options only | 13 named sections |
| Examples | In description | Dedicated green section |
| Workflows | Not shown | Cyan headers |
| Troubleshooting | Not shown | Problem/solution pairs |
| Dashboard | Lists commands | Categorized panels |

---

## Implementation

### RichGroup (`cli.py:28-141`)
```python
class RichGroup(click.Group):
    """Rich-enabled help formatter for dashboard."""

    def format_help(self, ctx, formatter):
        # Render 9 category panels with Table + Panel
```

### RichCommand (`cli.py:143-340`)
```python
class RichCommand(click.Command):
    SECTIONS = [
        "AI ASSISTANT CONTEXT",
        "EXAMPLES",
        "COMMON WORKFLOWS",
        ...
    ]

    def _parse_docstring(self):
        # Split docstring by section headers

    def _render_sections(self):
        # Apply Rich formatting per section type
```

---

## Color Theme

```python
AUDITOR_THEME = {
    "info": "bold cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "success": "bold green",
    "critical": "bold red",
    "high": "bold yellow",
    "medium": "bold blue",
    "low": "cyan",
    "cmd": "bold magenta",
    "path": "bold cyan",
    "dim": "dim white",
}
```
