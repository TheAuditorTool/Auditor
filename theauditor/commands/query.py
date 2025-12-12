"""Query command - database query API for code relationships.

Direct SQL queries over TheAuditor's indexed code relationships.
NO file reading, NO parsing, NO inference - just exact database lookups.
"""

import sqlite3
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.error_handler import handle_exceptions


def _normalize_path_filter(path_filter: tuple) -> str | None:
    """Normalize path filter - handle shell expansion and convert wildcards to SQL LIKE."""
    if not path_filter:
        return None

    if len(path_filter) == 1:
        path = path_filter[0]
    else:
        paths = [p.replace("\\", "/") for p in path_filter]
        if paths:
            prefix_parts = paths[0].split("/")
            common_parts = []
            for i, part in enumerate(prefix_parts):
                if all(p.split("/")[i] == part if len(p.split("/")) > i else False for p in paths):
                    common_parts.append(part)
                else:
                    break
            path = "/".join(common_parts) + "/" if common_parts else ""
        else:
            return None

    path = path.replace("\\", "/")
    path = path.replace("**", "%").replace("*", "%").replace("?", "_")
    if not path.endswith("%") and not path.endswith("/"):
        path += "%"
    elif path.endswith("/"):
        path += "%"
    return path


@click.command(cls=RichCommand)
@click.option("--symbol", help="Query symbol by exact name (functions, classes, variables)")
@click.option("--file", help="Query file by path (partial match supported)")
@click.option("--api", help="Query API endpoint by route pattern (supports wildcards)")
@click.option("--component", help="Query React/Vue component by name")
@click.option("--variable", help="Query variable by name (for data flow tracing)")
@click.option("--pattern", help="Search symbol NAMES by pattern (NOT code content). Use % wildcards like 'auth%'")
@click.option(
    "--content",
    is_flag=True,
    help="Search CODE CONTENT (expressions, arguments) instead of symbol names. Use with --pattern",
)
@click.option(
    "--category", help="Search by security category (jwt, oauth, password, sql, xss, auth)"
)
@click.option("--findings", is_flag=True, help="Query findings from all tools (lint, taint, rules, osv)")
@click.option("--severity", help="Filter findings by severity (critical, high, medium, low, warning, error)")
@click.option("--tool", help="Filter findings by tool (ruff, eslint, taint, cfg-analysis, mypy, terraform)")
@click.option("--rule", "rule_filter", help="Filter findings by rule name pattern (e.g., 'unused%', 'SQL%')")
@click.option("--limit", "findings_limit", type=int, default=5000, help="Max findings to return (default 5000, 0=unlimited)")
@click.option("--search", help="Cross-table exploratory search (finds term across all tables)")
@click.option(
    "--list",
    "list_mode",
    help="List all symbols in file (symbols, functions, classes, imports, all)",
)
@click.option(
    "--list-symbols",
    "list_symbols",
    is_flag=True,
    help="Discovery mode: list symbols matching filter pattern",
)
@click.option(
    "--filter",
    "symbol_filter",
    help="Symbol name pattern for --list-symbols (e.g., '*Controller*', '*auth*')",
)
@click.option(
    "--path",
    "path_filter",
    multiple=True,
    help="File path pattern (e.g., 'src/api/*', 'frontend/'). Works with --pattern and --list-symbols.",
)
@click.option(
    "--show-callers", is_flag=True, help="Show who calls this symbol (control flow incoming)"
)
@click.option(
    "--show-callees", is_flag=True, help="Show what this symbol calls (control flow outgoing)"
)
@click.option(
    "--show-dependencies", is_flag=True, help="Show what this file imports (outgoing dependencies)"
)
@click.option(
    "--show-dependents", is_flag=True, help="Show who imports this file (incoming dependencies)"
)
@click.option(
    "--show-incoming", is_flag=True, help="Show who CALLS symbols in this file (incoming calls)"
)
@click.option(
    "--show-tree", is_flag=True, help="Show component hierarchy tree (parent-child relationships)"
)
@click.option("--show-hooks", is_flag=True, help="Show React hooks used by component")
@click.option(
    "--show-data-deps",
    is_flag=True,
    help="Show data dependencies (what vars function reads/writes) - DFG",
)
@click.option(
    "--show-flow",
    is_flag=True,
    help="Show variable flow through assignments (def-use chains) - DFG",
)
@click.option(
    "--show-taint-flow",
    is_flag=True,
    help="Show cross-function taint flow (returns -> assignments) - DFG",
)
@click.option(
    "--show-api-coverage",
    is_flag=True,
    help="Show API security coverage (auth controls per endpoint)",
)
@click.option(
    "--type-filter", help="Filter pattern search by symbol type (function, class, variable)"
)
@click.option(
    "--include-tables",
    help="Comma-separated tables for cross-table search (e.g., 'symbols,findings')",
)
@click.option(
    "--depth", default=1, type=int, help="Traversal depth for transitive queries (1-5, default=1)"
)
@click.option(
    "--format",
    "output_format",
    default="text",
    type=click.Choice(["text", "json", "tree"]),
    help="Output format: text (human), json (AI), tree (visual)",
)
@click.option("--save", type=click.Path(), help="Save output to file (auto-creates parent dirs)")
@click.option(
    "--show-code/--no-code",
    default=False,
    help="Include source code snippets for callers/callees (default: no)",
)
@click.argument("extra_paths", nargs=-1, required=False)
@handle_exceptions
def query(
    symbol,
    file,
    api,
    component,
    variable,
    pattern,
    content,
    category,
    findings,
    severity,
    tool,
    rule_filter,
    findings_limit,
    search,
    list_mode,
    list_symbols,
    symbol_filter,
    path_filter,
    show_callers,
    show_callees,
    show_dependencies,
    show_dependents,
    show_incoming,
    show_tree,
    show_hooks,
    show_data_deps,
    show_flow,
    show_taint_flow,
    show_api_coverage,
    type_filter,
    include_tables,
    depth,
    output_format,
    save,
    show_code,
    extra_paths,
):
    """Query code relationships from indexed database.

    Direct SQL queries over TheAuditor's indexed code relationships.
    Returns exact file:line locations. No file reading, no inference.

    \b
    PREREQUISITE: Run 'aud full' first to build the index.

    \b
    QUERY TARGETS (pick one):
      --symbol NAME       Function/class lookup, combine with --show-callers
      --file PATH         File dependencies, combine with --show-dependents
      --api ROUTE         API endpoint handler lookup
      --component NAME    React/Vue component tree
      --pattern PATTERN   Search symbol NAMES (% wildcard). Add --content for code text.
      --pattern + --content  Search CODE CONTENT (expressions, arguments)
      --list-symbols      Discovery mode with --filter and --path

    \b
    ACTION FLAGS (what to show):
      --show-callers      Who calls this symbol?
      --show-callees      What does this symbol call?
      --show-dependencies What does this file import?
      --show-dependents   Who imports this file?
      --show-data-deps    What variables does function read/write?
      --show-flow         Trace variable through assignments
      --show-api-coverage Which endpoints have auth controls?

    \b
    MODIFIERS:
      --depth N           Transitive depth 1-5 (default=1)
      --format json|text  Output format (default=text)
      --show-code         Include source snippets

    AI ASSISTANT CONTEXT:
      Purpose: Query code relationships from indexed database (symbols, callers, dependencies)
      Input: .pf/repo_index.db (after aud full)
      Output: Structured results (text, JSON, or tree format)
      Prerequisites: aud full (populates symbols, calls, refs tables)
      Integration: Use for precise lookups; use aud explain for comprehensive context

    EXAMPLES:
      # Find callers before refactoring
      aud query --symbol validateUser --show-callers

      # Check file dependencies before moving
      aud query --file src/auth.ts --show-dependents

      # Find API handler
      aud query --api "/users/:id"

      # Pattern search (symbol names)
      aud query --pattern "auth%" --type-filter function

      # CODE CONTENT search (expressions, arguments)
      aud query --pattern "%onClick%" --content
      aud query --pattern "%jwt.sign%" --content --path "backend/%"

      # List functions in file
      aud query --file auth.py --list functions

      # JSON for parsing
      aud query --symbol foo --show-callers --format json

    \b
    ANTI-PATTERNS (Do NOT Do This)
    ------------------------------
      X  aud query --symbol foo.bar
         Methods are stored as ClassName.methodName
         -> First run: aud query --symbol bar (shows canonical name)
         -> Then use exact name from output

      X  aud query --show-callers (without --symbol)
         -> Must specify what to query: --symbol NAME --show-callers

      X  Using 'aud query' for comprehensive context
         -> Use 'aud explain' instead (returns more in one call)

      X  Assuming empty results means bug
         -> Check symbol spelling (case-sensitive)
         -> Re-run 'aud full' if code changed

      X  aud query --pattern "%onClick={() =>%"
         --pattern searches symbol NAMES, not code content
         -> For code text: aud query --pattern "%onClick%" --content
         -> For symbol names: aud query --pattern "%Handler%"

    \b
    OUTPUT FORMAT
    -------------
    Text mode (default):
      Callers (3):
        1. src/api/login.ts:45
           LoginController.handle -> validateUser
        2. src/middleware/auth.ts:23
           authMiddleware -> validateUser

    JSON mode (--format json):
      [{"caller_file": "src/api/login.ts", "caller_line": 45, ...}]

    \b
    TROUBLESHOOTING: aud manual troubleshooting
    DATABASE SCHEMA: aud manual database
    ARCHITECTURE:    aud manual architecture
    """
    from theauditor.context import CodeQueryEngine, format_output

    pf_dir = Path.cwd() / ".pf"
    if not pf_dir.exists():
        err_console.print(
            "\n" + "=" * 60,
        )
        err_console.print(
            "[error]ERROR: No .pf directory found[/error]",
        )
        console.rule()
        err_console.print(
            "[error]\nContext queries require indexed data.[/error]",
        )
        err_console.print(
            "[error]\nPlease run:[/error]",
        )
        err_console.print(
            "[error]    aud full[/error]",
        )
        err_console.print(
            "[error]\nThen try again:[/error]",
        )
        if symbol:
            err_console.print(
                f"[error]    aud query --symbol {symbol} --show-callers\n[/error]",
                highlight=False,
            )
        else:
            err_console.print(
                "[error]    aud query --help\n[/error]",
            )
        raise click.Abort()

    if not any(
        [
            symbol,
            file,
            api,
            component,
            variable,
            pattern,
            category,
            findings,
            search,
            show_api_coverage,
            list_mode,
            list_symbols,
        ]
    ):
        err_console.print(
            "\n" + "=" * 60,
        )
        err_console.print(
            "[error]ERROR: No query target specified[/error]",
        )
        console.rule()
        err_console.print(
            "[error]\nYou must specify what to query:[/error]",
        )
        err_console.print(
            "[error]    --symbol NAME       (query a symbol)[/error]",
        )
        err_console.print(
            "[error]    --file PATH         (query a file)[/error]",
        )
        err_console.print(
            "[error]    --api ROUTE         (query an API endpoint)[/error]",
        )
        err_console.print(
            "[error]    --component NAME    (query a component)[/error]",
        )
        err_console.print(
            "[error]    --variable NAME     (query variable data flow)[/error]",
        )
        err_console.print(
            "[error]    --pattern PATTERN   (search symbols by pattern)[/error]",
        )
        err_console.print(
            "[error]    --category CATEGORY (search by security category)[/error]",
        )
        err_console.print(
            "[error]    --findings          (query findings from all tools)[/error]",
        )
        err_console.print(
            "[error]    --search TERM       (cross-table exploratory search)[/error]",
        )
        err_console.print(
            "[error]    --list TYPE         (list symbols: functions, classes, imports, all)[/error]",
        )
        err_console.print(
            "[error]    --list-symbols      (discovery mode: find symbols by pattern)[/error]",
        )
        err_console.print(
            "[error]    --show-api-coverage (query all API security coverage)[/error]",
        )
        err_console.print(
            "[error]\nExamples:[/error]",
        )
        err_console.print(
            "[error]    aud query --symbol authenticateUser --show-callers[/error]",
        )
        err_console.print(
            "[error]    aud query --file src/auth.ts --show-dependencies[/error]",
        )
        err_console.print(
            "[error]    aud query --api '/users' --format json[/error]",
        )
        err_console.print(
            "[error]    aud query --symbol createApp --show-data-deps[/error]",
        )
        err_console.print(
            "[error]    aud query --variable userToken --show-flow --depth 3[/error]",
        )
        err_console.print(
            "[error]    aud query --pattern 'auth%' --type-filter function[/error]",
        )
        err_console.print(
            "[error]    aud query --category jwt --format json[/error]",
        )
        err_console.print(
            "[error]    aud query --search payment --include-tables symbols,findings[/error]",
        )
        err_console.print(
            "[error]    aud query --file python_impl.py --list functions[/error]",
        )
        err_console.print(
            "[error]    aud query --list-symbols --filter '*Controller*'[/error]",
        )
        err_console.print(
            "[error]    aud query --list-symbols --path 'services/' --filter '*'[/error]",
        )
        err_console.print(
            "[error]    aud query --show-api-coverage\n[/error]",
        )
        raise click.Abort()

    try:
        engine = CodeQueryEngine(Path.cwd())
    except FileNotFoundError as e:
        err_console.print(f"[error]\nERROR: {e}[/error]", highlight=False)
        raise click.Abort() from e

    results = None

    # Validate --symbol doesn't contain wildcards (common AI agent mistake)
    if symbol and any(c in symbol for c in ["%", "*", "?"]):
        err_console.print("\n" + "=" * 60)
        err_console.print("[error]ERROR: --symbol expects exact name, not a pattern[/error]")
        console.rule()
        err_console.print("[error]You passed a wildcard pattern to --symbol.[/error]")
        err_console.print("[error]For wildcard search, use one of these instead:[/error]")
        err_console.print("[error]    aud query --pattern 'auth%'              (SQL LIKE)[/error]")
        err_console.print(
            "[error]    aud query --list-symbols --filter '*auth*'  (glob style)\n[/error]"
        )
        engine.close()
        raise click.Abort()

    all_paths = path_filter + extra_paths if extra_paths else path_filter
    sql_path_filter = _normalize_path_filter(all_paths)

    try:
        if list_symbols:
            name_pattern = "%"
            if symbol_filter:
                name_pattern = symbol_filter.replace("*", "%").replace("?", "_")

            results = engine.pattern_search(
                name_pattern, type_filter=type_filter, path_filter=sql_path_filter, limit=200
            )

            results = {
                "type": "discovery",
                "filter": symbol_filter or "*",
                "path": sql_path_filter or "(all)",
                "type_filter": type_filter,
                "count": len(results),
                "symbols": results,
            }

        elif pattern:
            if content:
                # Search code content (expressions, arguments) instead of symbol names
                raw_results = engine.content_search(pattern, path_filter=sql_path_filter)
                results = {
                    "type": "content_search",
                    "pattern": pattern,
                    "path": sql_path_filter or "(all)",
                    "count": len(raw_results),
                    "matches": raw_results,
                }
            else:
                # Default: search symbol names
                raw_results = engine.pattern_search(
                    pattern, type_filter=type_filter, path_filter=sql_path_filter
                )
                results = {
                    "type": "pattern_search",
                    "pattern": pattern,
                    "path": sql_path_filter or "(all)",
                    "type_filter": type_filter,
                    "count": len(raw_results),
                    "symbols": raw_results,
                }

        elif category:
            results = engine.category_search(category)

        elif findings:
            # Query findings from all tools with optional filters
            file_filter = file or (sql_path_filter.rstrip('%') if sql_path_filter else None)
            raw_findings = engine.get_findings(
                file_path=file_filter,
                tool=tool,
                severity=severity,
                rule=rule_filter,
                limit=findings_limit,
            )

            # Group findings by tool for summary
            tool_counts = {}
            severity_counts = {}
            for f in raw_findings:
                t = f.get("tool", "unknown")
                s = f.get("severity", "unknown")
                tool_counts[t] = tool_counts.get(t, 0) + 1
                severity_counts[s] = severity_counts.get(s, 0) + 1

            results = {
                "type": "findings",
                "count": len(raw_findings),
                "filters": {
                    "file": file_filter,
                    "tool": tool,
                    "severity": severity,
                    "rule": rule_filter,
                },
                "summary": {
                    "by_tool": tool_counts,
                    "by_severity": severity_counts,
                },
                "findings": raw_findings,
            }

        elif search:
            tables = include_tables.split(",") if include_tables else None
            results = engine.cross_table_search(search, include_tables=tables)

        elif symbol:
            if show_callers:
                results = engine.get_callers(symbol, depth=depth)
            elif show_callees:
                results = engine.get_callees(symbol)
            elif show_data_deps:
                results = engine.get_data_dependencies(symbol)
            elif show_taint_flow:
                results = engine.get_cross_function_taint(symbol)
            else:
                symbols = engine.find_symbol(symbol)

                if isinstance(symbols, dict) and "error" in symbols:
                    results = symbols
                else:
                    callers = engine.get_callers(symbol, depth=1)
                    results = {"symbol": symbols, "callers": callers}

        elif list_mode:
            if not file:
                err_console.print(
                    "[error]\nERROR: --list requires --file to be specified[/error]",
                )
                err_console.print(
                    "[error]Example: aud query --file python_impl.py --list functions\n[/error]",
                )
                raise click.Abort()

            db_path = Path.cwd() / ".pf" / "repo_index.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            list_type = list_mode.lower()
            if list_type == "all":
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE path LIKE ?
                    ORDER BY type, line
                """
                cursor.execute(query, (f"%{file}%",))
                rows = cursor.fetchall()

                # Group by category
                declarations = []
                hooks = []
                api_calls = []
                data_access = {}

                for name, sym_type, line in rows:
                    if sym_type in ('function', 'class', 'interface', 'type', 'enum', 'method', 'arrow_function'):
                        declarations.append((name, sym_type, line))
                    elif sym_type == 'call':
                        if 'use' in name.lower() and name[0].islower():
                            hooks.append((name.split('.')[-1].split('"')[-1], line))
                        elif 'api.' in name.lower() or 'axios' in name.lower():
                            api_calls.append((name.split('.')[-1], line))
                    elif sym_type == 'property':
                        # Group properties by base name
                        base = name.split('.')[0] if '.' in name else name
                        if base not in data_access:
                            data_access[base] = []
                        data_access[base].append(line)

                # Build organized output
                output_lines = [f"\n=== {file} ===\n"]

                if declarations:
                    output_lines.append("DECLARATIONS:")
                    for name, sym_type, line in declarations:
                        output_lines.append(f"  {name:40} {sym_type:12} {line}")

                if hooks:
                    output_lines.append("\nHOOKS:")
                    hook_counts = {}
                    for name, line in hooks:
                        if name not in hook_counts:
                            hook_counts[name] = []
                        hook_counts[name].append(line)
                    for name, lines in hook_counts.items():
                        if len(lines) > 1:
                            output_lines.append(f"  {name:40} x{len(lines):3} {lines[0]}-{lines[-1]}")
                        else:
                            output_lines.append(f"  {name:40}      {lines[0]}")

                if api_calls:
                    output_lines.append("\nAPI CALLS:")
                    call_counts = {}
                    for name, line in api_calls:
                        if name not in call_counts:
                            call_counts[name] = []
                        call_counts[name].append(line)
                    for name, lines in call_counts.items():
                        output_lines.append(f"  {name:40} {','.join(map(str, lines[:5]))}")

                if data_access:
                    output_lines.append("\nDATA ACCESS (top 15):")
                    sorted_access = sorted(data_access.items(), key=lambda x: -len(x[1]))[:15]
                    for name, lines in sorted_access:
                        output_lines.append(f"  {name:40} x{len(lines):3} {','.join(map(str, lines[:5]))}")

                conn.close()
                results = {"type": "list_formatted", "output": "\n".join(output_lines)}

            elif list_type in ("functions", "function"):
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE path LIKE ? AND type = 'function'
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("classes", "class"):
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE path LIKE ? AND type = 'class'
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("imports", "import"):
                query = """
                    SELECT module_name, style, line
                    FROM imports
                    WHERE path LIKE ?
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            else:
                conn.close()
                err_console.print(
                    f"[error]\nERROR: Unknown list type: {list_type}[/error]",
                    highlight=False,
                )
                err_console.print(
                    "[error]Valid types: functions, classes, imports, all\n[/error]",
                )
                raise click.Abort()

            if list_type != "all":
                rows = cursor.fetchall()
                conn.close()

                if list_type in ("imports", "import"):
                    results = {
                        "type": "list",
                        "list_mode": list_type,
                        "file": file,
                        "count": len(rows),
                        "items": [{"module": row[0], "style": row[1], "line": row[2]} for row in rows],
                    }
                else:
                    results = {
                        "type": "list",
                        "list_mode": list_type,
                        "file": file,
                        "count": len(rows),
                        "items": [{"name": row[0], "type": row[1], "line": row[2]} for row in rows],
                    }

        elif file:
            if show_dependencies:
                results = engine.get_file_dependencies(file, direction="outgoing")
            elif show_dependents:
                results = engine.get_file_dependencies(file, direction="incoming")
            elif show_incoming:
                results = engine.get_file_incoming_calls(file)
            else:
                results = engine.get_file_dependencies(file, direction="both")

        elif show_api_coverage:
            results = engine.get_api_security_coverage(api if api else None)

        elif api:
            results = engine.get_api_handlers(api)

        elif component:
            results = engine.get_component_tree(component)

        elif variable:
            if show_flow:
                from_file = file or "."
                results = engine.trace_variable_flow(variable, from_file, depth=depth)
            else:
                results = {"error": "Please specify --show-flow with --variable"}

    except ValueError as e:
        err_console.print(f"[error]\nERROR: {e}[/error]", highlight=False)
        raise click.Abort() from e
    finally:
        engine.close()

    if show_code and results:
        from theauditor.utils.code_snippets import CodeSnippetManager

        snippet_manager = CodeSnippetManager(Path.cwd())

        if isinstance(results, list) and results and hasattr(results[0], "caller_file"):
            for call in results:
                snippet = snippet_manager.get_snippet(
                    call.caller_file, call.caller_line, expand_block=False
                )
                if not snippet.startswith("["):
                    call.arguments.append(f"__snippet__:{snippet}")

        elif isinstance(results, dict) and "callers" in results:
            callers = results.get("callers", [])
            if isinstance(callers, list):
                for call in callers:
                    if hasattr(call, "caller_file"):
                        snippet = snippet_manager.get_snippet(
                            call.caller_file, call.caller_line, expand_block=False
                        )
                        if not snippet.startswith("["):
                            call.arguments.append(f"__snippet__:{snippet}")

    # Special handling for findings with Rich output
    if (
        isinstance(results, dict)
        and results.get("type") == "findings"
        and output_format == "text"
        and not save
    ):
        from theauditor.context.findings_formatter import render_findings_rich

        render_findings_rich(results, console)
    else:
        output_str = format_output(results, format=output_format)
        console.print(output_str, markup=False)

        if save:
            save_path = Path(save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            # For findings, use plain text formatter when saving
            if isinstance(results, dict) and results.get("type") == "findings":
                from theauditor.context.findings_formatter import format_findings_plain

                output_str = format_findings_plain(results)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(output_str)
            err_console.print(f"[dim]Saved to: {save_path}[/dim]", highlight=False)
