"""Explain command - comprehensive context for files, symbols, and components.

Provides AI-optimized briefing packet for any code target in a single command.
Replaces the need to run 5-6 separate queries or read entire files.

NO EMOJIS: Windows Command Prompt uses CP1252 encoding which cannot
handle emoji characters. All output uses plain ASCII only.

Usage:
    aud explain src/auth.ts           # File context
    aud explain authenticateUser      # Symbol context
    aud explain Dashboard             # React component context
    aud explain --format json file.py # JSON output for AI
"""

import json
import time
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.context.explain_formatter import ExplainFormatter
from theauditor.context.query import CodeQueryEngine
from theauditor.pipeline.ui import console
from theauditor.utils.code_snippets import CodeSnippetManager
from theauditor.utils.error_handler import handle_exceptions

FILE_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".vue",
    ".rb",
    ".php",
}


def detect_target_type(target: str, engine: CodeQueryEngine) -> str:
    """Detect whether target is a file, symbol, or component.

    Algorithm:
    1. If ends with known extension -> 'file'
    2. If contains '.' with uppercase start -> 'symbol' (Class.method)
    3. If PascalCase and in react_components -> 'component'
    4. Default -> 'symbol'

    Args:
        target: User-provided target string
        engine: CodeQueryEngine for component lookup

    Returns:
        One of: 'file', 'symbol', 'component'
    """

    for ext in FILE_EXTENSIONS:
        if target.endswith(ext):
            return "file"

    if "/" in target or "\\" in target:
        return "file"

    if "." in target and target[0].isupper():
        return "symbol"

    if target and target[0].isupper() and len(target) > 1:
        component = engine.get_component_tree(target)
        if not isinstance(component, dict) or "error" not in component:
            return "component"

    return "symbol"


@click.command(cls=RichCommand)
@click.argument("target")
@click.option(
    "--depth", default=1, type=int, help="Call graph depth for callers/callees (1-5, default=1)"
)
@click.option(
    "--format",
    "output_format",
    default="text",
    type=click.Choice(["text", "json"]),
    help="Output format: text (human), json (AI)",
)
@click.option(
    "--section",
    default="all",
    type=click.Choice(["all", "symbols", "hooks", "deps", "callers", "callees"]),
    help="Show only specific section",
)
@click.option("--no-code", is_flag=True, help="Disable code snippets (faster output)")
@click.option("--limit", default=20, type=int, help="Max items per section (default=20)")
@handle_exceptions
def explain(target: str, depth: int, output_format: str, section: str, no_code: bool, limit: int):
    """Get comprehensive context about a file, symbol, or component.

    Provides a complete "briefing packet" in ONE command, eliminating the need
    to run multiple queries or read entire files. Optimized for AI workflows.

    TARGET can be:

    \b
      File path:     aud explain src/auth.ts
      Symbol:        aud explain authenticateUser
      Class.method:  aud explain UserController.create
      Component:     aud explain Dashboard

    \b
    WHAT IT RETURNS:

      For files:
        - SYMBOLS DEFINED: All functions, classes, variables with line numbers
        - HOOKS USED: React/Vue hooks (if applicable)
        - DEPENDENCIES: Files imported by this file
        - DEPENDENTS: Files that import this file
        - OUTGOING CALLS: Functions called from this file
        - INCOMING CALLS: Functions in this file called elsewhere

      For symbols:
        - DEFINITION: File, line, type, signature
        - CALLERS: Who calls this symbol
        - CALLEES: What this symbol calls

      For components:
        - COMPONENT INFO: Type, props, file location
        - HOOKS USED: React hooks with lines
        - CHILD COMPONENTS: Components rendered by this one

    \b
    WHY USE THIS:
      - Single command replaces 5-6 queries
      - Includes code snippets by default
      - Saves 5,000-10,000 context tokens per task
      - Auto-detects target type (no flags needed)

    \b
    AI ASSISTANT CONTEXT:
      Purpose: Comprehensive code context in one call
      Input: File path, symbol name, or component name
      Output: Structured context with optional code snippets
      Performance: <100ms for files with <50 symbols
      Integration: Use before refactoring, debugging, or code review

    \b
    EXAMPLES:

      # Get full context for a file
      aud explain src/auth/service.ts

      # Get symbol definition and callers
      aud explain validateInput

      # JSON output for AI consumption
      aud explain Dashboard --format json

      # Fast mode without code snippets
      aud explain OrderController.create --no-code

      # Limit output size
      aud explain utils/helpers.py --limit 10

    \b
    ANTI-PATTERNS (Do NOT Do This)
    ------------------------------
      X  aud explain --symbol foo
         -> Just use: aud explain foo (auto-detects target type)

      X  aud explain .
         -> Use 'aud blueprint' for project overview

      X  Running 'aud query' before 'aud explain'
         -> Always try 'explain' first - it returns more comprehensive context

      X  aud explain --format json | jq '.symbols'
         -> JSON structure varies by target type, check OUTPUT FORMAT below

    \b
    OUTPUT FORMAT
    -------------
    Text mode (file target):
      === FILE: src/auth.py ===
      SYMBOLS DEFINED (5):
        - authenticate (function) line 42-58
        - User (class) line 10-40
      DEPENDENCIES (3):
        - src/utils/crypto.py
        - src/db/users.py
      INCOMING CALLS (2):
        - src/api/login.py:15 login_handler() -> authenticate

    JSON mode (--format json):
      {
        "target": "src/auth.py",
        "target_type": "file",
        "symbols": [{"name": "authenticate", "type": "function", "line": 42}],
        "imports": ["src/utils/crypto.py"],
        "incoming_calls": [{"file": "src/api/login.py", "line": 15, ...}]
      }

    SEE ALSO:
      aud manual explain    Learn about the explain command
      aud manual context    Apply business logic rules to findings
    """
    start_time = time.perf_counter()

    depth = max(1, min(5, depth))

    root = Path.cwd()
    engine = CodeQueryEngine(root)
    snippet_manager = CodeSnippetManager(root)
    formatter = ExplainFormatter(snippet_manager, show_code=not no_code, limit=limit)

    try:
        target_type = detect_target_type(target, engine)

        truncated_sections = []

        if target_type == "file":
            data = engine.get_file_context_bundle(target, limit=limit)

            for key in ["symbols", "imports", "importers", "outgoing_calls", "incoming_calls"]:
                if len(data.get(key, [])) > limit:
                    truncated_sections.append(key)

                    data[key] = data[key][:limit]

            if section != "all":
                section_map = {
                    "symbols": ["symbols"],
                    "hooks": ["hooks"],
                    "deps": ["imports", "importers"],
                    "callers": ["incoming_calls"],
                    "callees": ["outgoing_calls"],
                }
                keep_keys = section_map.get(section, [])
                for key in [
                    "symbols",
                    "hooks",
                    "imports",
                    "importers",
                    "outgoing_calls",
                    "incoming_calls",
                    "framework_info",
                ]:
                    if key not in keep_keys:
                        data[key] = [] if isinstance(data.get(key), list) else {}

            output = formatter.format_file_explain(data)

        elif target_type == "symbol":
            data = engine.get_symbol_context_bundle(target, limit=limit, depth=depth)
            if "error" in data:
                console.print(
                    f"[error]Error: {data['error']}[/error]", stderr=True, highlight=False
                )
                return

            for key in ["callers", "callees"]:
                if len(data.get(key, [])) > limit:
                    truncated_sections.append(key)

                    data[key] = data[key][:limit]

            if section != "all":
                section_map = {
                    "callers": ["callers"],
                    "callees": ["callees"],
                }
                keep_keys = section_map.get(section, [])
                for key in ["callers", "callees"]:
                    if key not in keep_keys:
                        data[key] = []

            output = formatter.format_symbol_explain(data)

        else:
            data = engine.get_component_tree(target)
            if isinstance(data, dict) and "error" in data:
                console.print(
                    f"[error]Error: {data['error']}[/error]", stderr=True, highlight=False
                )
                return
            data["target"] = target
            data["target_type"] = "component"
            output = formatter.format_component_explain(data)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        data["metadata"] = {
            "query_time_ms": round(elapsed_ms, 1),
            "truncated_sections": truncated_sections,
        }

        if output_format == "json":
            console.print(json.dumps(data, indent=2, default=str), markup=False)
        else:
            console.print(output, markup=False)
            console.print(f"\n(Query time: {elapsed_ms:.1f}ms)", highlight=False)

    finally:
        engine.close()
