"""Central UI handler for TheAuditor."""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

AUDITOR_THEME = Theme(
    {
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
)


console = Console(theme=AUDITOR_THEME, force_terminal=sys.stdout.isatty())
err_console = Console(theme=AUDITOR_THEME, stderr=True, force_terminal=sys.stderr.isatty())


def print_header(title: str) -> None:
    """Print a styled section header with horizontal rules."""
    console.rule(f"[bold]{title}[/bold]")


def print_error(msg: str) -> None:
    """Print an error message in red."""
    console.print(f"[error]ERROR:[/error] {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message in yellow."""
    console.print(f"[warning]WARNING:[/warning] {msg}")


def print_success(msg: str) -> None:
    """Print a success message in green."""
    console.print(f"[success]OK:[/success] {msg}")


def print_status_panel(status: str, message: str, detail: str, level: str = "info") -> None:
    """Print a status panel with colored border."""
    style_map = {
        "critical": ("bold red", "red"),
        "high": ("bold yellow", "yellow"),
        "medium": ("bold blue", "blue"),
        "low": ("cyan", "cyan"),
        "success": ("bold green", "green"),
        "info": ("bold cyan", "cyan"),
    }
    text_style, border_style = style_map.get(level, ("white", "white"))

    panel = Panel(
        Text.assemble(
            (f"STATUS: [{status}]\n", text_style),
            (f"{message}\n", border_style),
            (detail, border_style),
        ),
        border_style=border_style,
        expand=False,
    )
    console.print(panel)
