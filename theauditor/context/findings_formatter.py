"""Rich formatter for findings output."""

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Severity styling
SEVERITY_STYLES = {
    "critical": ("bold red", "red"),
    "high": ("bold yellow", "yellow"),
    "medium": ("bold blue", "blue"),
    "warning": ("dim yellow", "yellow"),
    "low": ("dim cyan", "cyan"),
    "info": ("dim white", "white"),
    "error": ("bold red", "red"),
}


def render_findings_rich(results: dict, console: Console) -> None:
    """Render findings with Rich formatting directly to console."""
    findings = results.get("findings", [])
    summary = results.get("summary", {})
    filters = results.get("filters", {})
    total_count = results.get("count", len(findings))

    # Header panel
    header_text = Text()
    header_text.append("FINDINGS REPORT\n", style="bold white")

    active_filters = [f"{k}={v}" for k, v in filters.items() if v]
    if active_filters:
        header_text.append(f"Filters: {', '.join(active_filters)}\n", style="dim")

    header_text.append(f"Total: {total_count:,} findings", style="bold cyan")

    console.print(Panel(header_text, box=box.DOUBLE, border_style="cyan"))

    # Summary tables side by side
    by_severity = summary.get("by_severity", {})
    by_tool = summary.get("by_tool", {})

    if by_severity or by_tool:
        summary_group = []

        if by_severity:
            sev_table = Table(
                title="By Severity",
                box=box.SIMPLE,
                show_header=True,
                header_style="bold",
                title_style="bold",
            )
            sev_table.add_column("Severity", style="bold")
            sev_table.add_column("Count", justify="right")

            severity_order = ["critical", "high", "medium", "warning", "low", "error", "info"]
            for sev in severity_order:
                if sev in by_severity:
                    count = by_severity[sev]
                    style, _ = SEVERITY_STYLES.get(sev, ("white", "white"))
                    sev_table.add_row(sev.upper(), str(count), style=style)

            # Any other severities
            for sev, count in sorted(by_severity.items()):
                if sev not in severity_order:
                    sev_table.add_row(sev, str(count))

            summary_group.append(sev_table)

        if by_tool:
            tool_table = Table(
                title="By Tool",
                box=box.SIMPLE,
                show_header=True,
                header_style="bold",
                title_style="bold",
            )
            tool_table.add_column("Tool")
            tool_table.add_column("Count", justify="right")

            for tool_name, count in sorted(by_tool.items(), key=lambda x: -x[1]):
                tool_table.add_row(tool_name, str(count))

            summary_group.append(tool_table)

        # Print summary tables
        if len(summary_group) == 2:
            # Side by side using columns
            from rich.columns import Columns

            console.print(Columns(summary_group, equal=True, expand=True))
        elif summary_group:
            console.print(summary_group[0])

    if not findings:
        console.print("\n[dim]No findings match the specified criteria.[/dim]")
        return

    # Group findings by severity
    by_sev: dict[str, list] = {
        "critical": [],
        "high": [],
        "medium": [],
        "warning": [],
        "low": [],
        "other": [],
    }
    for f in findings:
        sev = str(f.get("severity", "other")).lower()
        if sev in by_sev:
            by_sev[sev].append(f)
        else:
            by_sev["other"].append(f)

    # CRITICAL - full detail table
    if by_sev["critical"]:
        console.print()
        _render_severity_section(console, "CRITICAL", by_sev["critical"], "red", show_all=True)

    # HIGH - full detail table
    if by_sev["high"]:
        console.print()
        _render_severity_section(console, "HIGH", by_sev["high"], "yellow", show_all=True)

    # MEDIUM - show first 20, then summary
    if by_sev["medium"]:
        console.print()
        _render_severity_section(console, "MEDIUM", by_sev["medium"], "blue", show_limit=20)

    # WARNING/LOW/OTHER - grouped summary only
    low_tier = by_sev["warning"] + by_sev["low"] + by_sev["other"]
    if low_tier:
        console.print()
        _render_grouped_section(console, "WARNING/LOW", low_tier, "dim")

    # Footer with filter hints
    console.print()
    hints = Table(box=None, show_header=False, padding=(0, 2))
    hints.add_column("Option", style="bold cyan")
    hints.add_column("Description", style="dim")
    hints.add_row("--findings --severity medium", "Show only medium severity")
    hints.add_row("--findings --tool eslint", "Show only eslint findings")
    hints.add_row("--findings --rule unused", "Filter by rule name pattern")
    hints.add_row("--findings --path backend/", "Limit to path prefix")
    hints.add_row("--findings --format json", "Machine-readable output")

    console.print(Panel(hints, title="Filter Options", box=box.ROUNDED, border_style="dim"))


def _render_severity_section(
    console: Console,
    title: str,
    findings: list,
    color: str,
    show_all: bool = False,
    show_limit: int = 0,
) -> None:
    """Render a severity section with findings in a clean format."""
    console.print(f"\n[bold {color}]{title} ({len(findings)})[/bold {color}]")
    console.print(f"[{color}]{'─' * 60}[/{color}]")

    display_findings = findings if show_all else findings[:show_limit] if show_limit else []

    for f in display_findings:
        file_path = f.get("file", "?")
        line_num = f.get("line", "?")
        loc = f"{file_path}:{line_num}"

        tool = f.get("tool", "?")
        rule = f.get("rule", "?")
        message = f.get("message", "")
        cwe = f.get("cwe")

        # Location line
        console.print(f"\n[cyan]{loc}[/cyan]")
        # Tool + Rule
        console.print(f"  [dim]{tool}[/dim] [bold]{rule}[/bold]", end="")
        if cwe:
            console.print(f" [red](CWE-{cwe})[/red]", end="")
        console.print()
        # Message (truncated if needed) - use highlight=False to avoid CP1252 crash
        if message:
            if len(message) > 100:
                message = message[:97] + "..."
            console.print(f"  {message}", style="dim", highlight=False, markup=False)

    console.print()

    # Show remaining count and grouped summary
    remaining = len(findings) - len(display_findings)
    if remaining > 0:
        console.print(f"  [dim]... and {remaining} more[/dim]")
        console.print()
        _render_rule_summary(console, findings[show_limit:] if show_limit else findings)


def _render_grouped_section(console: Console, title: str, findings: list, style: str) -> None:
    """Render a section as grouped summary only (no individual findings)."""
    console.print(Panel(f"[bold]{title}[/bold] ({len(findings)})", style=style, box=box.SIMPLE))
    _render_rule_summary(console, findings)


def _render_rule_summary(console: Console, findings: list) -> None:
    """Render a summary table grouped by rule."""
    by_rule: dict[str, list] = {}
    for f in findings:
        rule = f.get("rule", "unknown")
        if rule not in by_rule:
            by_rule[rule] = []
        by_rule[rule].append(f)

    if not by_rule:
        return

    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold dim",
        padding=(0, 1),
    )
    table.add_column("Rule", style="bold")
    table.add_column("Count", justify="right", style="cyan")
    table.add_column("Files", justify="right", style="dim")

    # Sort by count descending, limit to top 30
    sorted_rules = sorted(by_rule.items(), key=lambda x: -len(x[1]))[:30]

    for rule, rule_findings in sorted_rules:
        count = len(rule_findings)
        files = len(set(f.get("file", "") for f in rule_findings))
        table.add_row(rule, str(count), f"{files} file(s)")

    if len(by_rule) > 30:
        table.add_row(f"... and {len(by_rule) - 30} more rules", "", "", style="dim")

    console.print(table)


def format_findings_plain(results: dict) -> str:
    """Format findings as plain text (for file save or non-terminal output)."""
    lines = []
    findings = results.get("findings", [])
    summary = results.get("summary", {})
    filters = results.get("filters", {})
    total_count = results.get("count", len(findings))

    lines.append("=" * 60)
    lines.append("FINDINGS REPORT")
    lines.append("=" * 60)
    lines.append("")

    active_filters = [f"{k}={v}" for k, v in filters.items() if v]
    if active_filters:
        lines.append(f"Filters: {', '.join(active_filters)}")
        lines.append("")

    lines.append(f"Total: {total_count:,} findings")
    lines.append("")

    by_severity = summary.get("by_severity", {})
    if by_severity:
        lines.append("By Severity:")
        severity_order = ["critical", "high", "medium", "warning", "low", "error", "info"]
        for sev in severity_order:
            if sev in by_severity:
                lines.append(f"  {sev:12} {by_severity[sev]:>5}")
        lines.append("")

    by_tool = summary.get("by_tool", {})
    if by_tool:
        lines.append("By Tool:")
        for tool_name, count in sorted(by_tool.items(), key=lambda x: -x[1]):
            lines.append(f"  {tool_name:16} {count:>5}")
        lines.append("")

    if not findings:
        lines.append("No findings match the specified criteria.")
        return "\n".join(lines)

    # Group by severity
    by_sev: dict[str, list] = {
        "critical": [],
        "high": [],
        "medium": [],
        "warning": [],
        "low": [],
        "other": [],
    }
    for f in findings:
        sev = str(f.get("severity", "other")).lower()
        if sev in by_sev:
            by_sev[sev].append(f)
        else:
            by_sev["other"].append(f)

    for sev_name in ["critical", "high"]:
        if by_sev[sev_name]:
            lines.append("")
            lines.append(f"=== {sev_name.upper()} ({len(by_sev[sev_name])}) ===")
            for f in by_sev[sev_name]:
                lines.append("")
                lines.append(f"{f.get('file', '?')}:{f.get('line', '?')}")
                lines.append(f"  [{f.get('tool', '?')}] {f.get('rule', '?')}")
                msg = f.get("message", "")
                if msg:
                    lines.append(f"  {msg[:100]}")

    if by_sev["medium"]:
        lines.append("")
        lines.append(f"=== MEDIUM ({len(by_sev['medium'])}) ===")
        for f in by_sev["medium"][:20]:
            lines.append(f"  {f.get('file', '?')}:{f.get('line', '?')} [{f.get('rule', '?')}]")
        if len(by_sev["medium"]) > 20:
            lines.append(f"  ... and {len(by_sev['medium']) - 20} more")

    low_tier = by_sev["warning"] + by_sev["low"] + by_sev["other"]
    if low_tier:
        lines.append("")
        lines.append(f"=== WARNING/LOW ({len(low_tier)}) - grouped ===")
        by_rule: dict[str, int] = {}
        for f in low_tier:
            rule = f.get("rule", "unknown")
            by_rule[rule] = by_rule.get(rule, 0) + 1
        for rule, count in sorted(by_rule.items(), key=lambda x: -x[1])[:20]:
            lines.append(f"  {rule}: {count}")

    return "\n".join(lines)
