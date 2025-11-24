"""Query command - database query API for code relationships.

Direct SQL queries over TheAuditor's indexed code relationships.
NO file reading, NO parsing, NO inference - just exact database lookups.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional

import click

from theauditor.utils.error_handler import handle_exceptions


@click.command()
@click.option("--symbol", help="Query symbol by exact name (functions, classes, variables)")
@click.option("--file", help="Query file by path (partial match supported)")
@click.option("--api", help="Query API endpoint by route pattern (supports wildcards)")
@click.option("--component", help="Query React/Vue component by name")
@click.option("--variable", help="Query variable by name (for data flow tracing)")
@click.option("--pattern", help="Search symbols by pattern (supports % wildcards like 'auth%')")
@click.option("--category", help="Search by security category (jwt, oauth, password, sql, xss, auth)")
@click.option("--search", help="Cross-table exploratory search (finds term across all tables)")
@click.option("--list", "list_mode", help="List all symbols in file (symbols, functions, classes, imports, all)")
@click.option("--list-symbols", "list_symbols", is_flag=True, help="Discovery mode: list symbols matching filter pattern")
@click.option("--filter", "symbol_filter", help="Symbol name pattern for --list-symbols (e.g., '*Controller*', '*auth*')")
@click.option("--path", "path_filter", help="File path pattern for --list-symbols (e.g., 'src/api/*', 'services/')")
@click.option("--show-callers", is_flag=True, help="Show who calls this symbol (control flow incoming)")
@click.option("--show-callees", is_flag=True, help="Show what this symbol calls (control flow outgoing)")
@click.option("--show-dependencies", is_flag=True, help="Show what this file imports (outgoing dependencies)")
@click.option("--show-dependents", is_flag=True, help="Show who imports this file (incoming dependencies)")
@click.option("--show-tree", is_flag=True, help="Show component hierarchy tree (parent-child relationships)")
@click.option("--show-hooks", is_flag=True, help="Show React hooks used by component")
@click.option("--show-data-deps", is_flag=True, help="Show data dependencies (what vars function reads/writes) - DFG")
@click.option("--show-flow", is_flag=True, help="Show variable flow through assignments (def-use chains) - DFG")
@click.option("--show-taint-flow", is_flag=True, help="Show cross-function taint flow (returns -> assignments) - DFG")
@click.option("--show-api-coverage", is_flag=True, help="Show API security coverage (auth controls per endpoint)")
@click.option("--type-filter", help="Filter pattern search by symbol type (function, class, variable)")
@click.option("--include-tables", help="Comma-separated tables for cross-table search (e.g., 'symbols,findings')")
@click.option("--depth", default=1, type=int, help="Traversal depth for transitive queries (1-5, default=1)")
@click.option("--format", "output_format", default="text",
              type=click.Choice(['text', 'json', 'tree']),
              help="Output format: text (human), json (AI), tree (visual)")
@click.option("--save", type=click.Path(), help="Save output to file (auto-creates parent dirs)")
@click.option("--show-code/--no-code", default=False,
              help="Include source code snippets for callers/callees (default: no)")
@handle_exceptions
def query(symbol, file, api, component, variable, pattern, category, search, list_mode,
          list_symbols, symbol_filter, path_filter,
          show_callers, show_callees, show_dependencies, show_dependents,
          show_tree, show_hooks, show_data_deps, show_flow, show_taint_flow,
          show_api_coverage, type_filter, include_tables,
          depth, output_format, save, show_code):
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
      --pattern PATTERN   SQL LIKE search (use % wildcard)
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

    \b
    EXAMPLES (Copy These Patterns)
    ------------------------------
      # Find callers before refactoring
      aud query --symbol validateUser --show-callers

      # Check file dependencies before moving
      aud query --file src/auth.ts --show-dependents

      # Find API handler
      aud query --api "/users/:id"

      # Pattern search
      aud query --pattern "auth%" --type-filter function

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
    from pathlib import Path
    from theauditor.context import CodeQueryEngine, format_output

    # Validate .pf directory exists
    pf_dir = Path.cwd() / ".pf"
    if not pf_dir.exists():
        click.echo("\n" + "="*60, err=True)
        click.echo("ERROR: No .pf directory found", err=True)
        click.echo("="*60, err=True)
        click.echo("\nContext queries require indexed data.", err=True)
        click.echo("\nPlease run:", err=True)
        click.echo("    aud full", err=True)
        click.echo("\nThen try again:", err=True)
        if symbol:
            click.echo(f"    aud query --symbol {symbol} --show-callers\n", err=True)
        else:
            click.echo("    aud query --help\n", err=True)
        raise click.Abort()

    # Validate at least one query target provided
    if not any([symbol, file, api, component, variable, pattern, category, search, show_api_coverage, list_mode, list_symbols]):
        click.echo("\n" + "="*60, err=True)
        click.echo("ERROR: No query target specified", err=True)
        click.echo("="*60, err=True)
        click.echo("\nYou must specify what to query:", err=True)
        click.echo("    --symbol NAME       (query a symbol)", err=True)
        click.echo("    --file PATH         (query a file)", err=True)
        click.echo("    --api ROUTE         (query an API endpoint)", err=True)
        click.echo("    --component NAME    (query a component)", err=True)
        click.echo("    --variable NAME     (query variable data flow)", err=True)
        click.echo("    --pattern PATTERN   (search symbols by pattern)", err=True)
        click.echo("    --category CATEGORY (search by security category)", err=True)
        click.echo("    --search TERM       (cross-table exploratory search)", err=True)
        click.echo("    --list TYPE         (list symbols: functions, classes, imports, all)", err=True)
        click.echo("    --list-symbols      (discovery mode: find symbols by pattern)", err=True)
        click.echo("    --show-api-coverage (query all API security coverage)", err=True)
        click.echo("\nExamples:", err=True)
        click.echo("    aud query --symbol authenticateUser --show-callers", err=True)
        click.echo("    aud query --file src/auth.ts --show-dependencies", err=True)
        click.echo("    aud query --api '/users' --format json", err=True)
        click.echo("    aud query --symbol createApp --show-data-deps", err=True)
        click.echo("    aud query --variable userToken --show-flow --depth 3", err=True)
        click.echo("    aud query --pattern 'auth%' --type-filter function", err=True)
        click.echo("    aud query --category jwt --format json", err=True)
        click.echo("    aud query --search payment --include-tables symbols,findings", err=True)
        click.echo("    aud query --file python_impl.py --list functions", err=True)
        click.echo("    aud query --list-symbols --filter '*Controller*'", err=True)
        click.echo("    aud query --list-symbols --path 'services/' --filter '*'", err=True)
        click.echo("    aud query --show-api-coverage\n", err=True)
        raise click.Abort()

    # Initialize query engine
    try:
        engine = CodeQueryEngine(Path.cwd())
    except FileNotFoundError as e:
        click.echo(f"\nERROR: {e}", err=True)
        raise click.Abort()

    # Route query based on target
    results = None

    try:
        if list_symbols:
            # DISCOVERY MODE: List symbols matching filter pattern
            # Converts shell glob (*) to SQL LIKE (%)
            name_pattern = '%'  # Default: match all
            if symbol_filter:
                # Convert glob to SQL LIKE: * -> %, ? -> _
                name_pattern = symbol_filter.replace('*', '%').replace('?', '_')

            # Convert path filter glob to SQL LIKE
            sql_path_filter = None
            if path_filter:
                sql_path_filter = path_filter.replace('*', '%').replace('?', '_')
                # Ensure trailing % for directory patterns
                if not sql_path_filter.endswith('%'):
                    sql_path_filter += '%'

            results = engine.pattern_search(
                name_pattern,
                type_filter=type_filter,
                path_filter=sql_path_filter,
                limit=200
            )

            # Wrap in discovery result format
            results = {
                'type': 'discovery',
                'filter': symbol_filter or '*',
                'path': path_filter or '(all)',
                'type_filter': type_filter,
                'count': len(results),
                'symbols': results
            }

        elif pattern:
            # NEW: Pattern search - SQL LIKE pattern matching (NO ML, NO CUDA)
            results = engine.pattern_search(pattern, type_filter=type_filter)

        elif category:
            # NEW: Category search - query security pattern tables (NO embeddings)
            results = engine.category_search(category)

        elif search:
            # NEW: Cross-table exploratory search (better than Compass's vector search)
            tables = include_tables.split(',') if include_tables else None
            results = engine.cross_table_search(search, include_tables=tables)

        elif symbol:
            # Symbol queries
            if show_callers:
                results = engine.get_callers(symbol, depth=depth)
            elif show_callees:
                results = engine.get_callees(symbol)
            elif show_data_deps:
                # NEW: Data flow query - what does this function read/write?
                results = engine.get_data_dependencies(symbol)
            elif show_taint_flow:
                # NEW: Cross-function taint flow
                results = engine.get_cross_function_taint(symbol)
            else:
                # Default: symbol info + direct callers
                symbols = engine.find_symbol(symbol)
                # Handle error dict from find_symbol (fuzzy suggestions)
                if isinstance(symbols, dict) and 'error' in symbols:
                    results = symbols  # Pass error dict directly
                else:
                    callers = engine.get_callers(symbol, depth=1)
                    results = {'symbol': symbols, 'callers': callers}

        elif list_mode:
            # NEW: List symbols in file (enumeration mode)
            if not file:
                click.echo("\nERROR: --list requires --file to be specified", err=True)
                click.echo("Example: aud query --file python_impl.py --list functions\n", err=True)
                raise click.Abort()

            # Directly query symbols table for enumeration
            db_path = Path.cwd() / ".pf" / "repo_index.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Build query based on list_mode type
            list_type = list_mode.lower()
            if list_type == "all":
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE file LIKE ?
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("functions", "function"):
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE file LIKE ? AND type = 'function'
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("classes", "class"):
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE file LIKE ? AND type = 'class'
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("imports", "import"):
                query = """
                    SELECT module_name, style, line
                    FROM imports
                    WHERE file LIKE ?
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            else:
                conn.close()
                click.echo(f"\nERROR: Unknown list type: {list_type}", err=True)
                click.echo("Valid types: functions, classes, imports, all\n", err=True)
                raise click.Abort()

            rows = cursor.fetchall()
            conn.close()

            # Format results
            if list_type in ("imports", "import"):
                results = {
                    'type': 'list',
                    'list_mode': list_type,
                    'file': file,
                    'count': len(rows),
                    'items': [{'module': row[0], 'style': row[1], 'line': row[2]} for row in rows]
                }
            else:
                results = {
                    'type': 'list',
                    'list_mode': list_type,
                    'file': file,
                    'count': len(rows),
                    'items': [{'name': row[0], 'type': row[1], 'line': row[2]} for row in rows]
                }

        elif file:
            # File dependency queries
            if show_dependencies:
                results = engine.get_file_dependencies(file, direction='outgoing')
            elif show_dependents:
                results = engine.get_file_dependencies(file, direction='incoming')
            else:
                # Default: both directions
                results = engine.get_file_dependencies(file, direction='both')

        elif show_api_coverage:
            # NEW: API security coverage (standalone query) - checked before 'elif api' to take precedence
            results = engine.get_api_security_coverage(api if api else None)

        elif api:
            # API endpoint queries
            results = engine.get_api_handlers(api)

        elif component:
            # Component tree queries
            results = engine.get_component_tree(component)

        elif variable:
            # NEW: Variable data flow queries
            if show_flow:
                # Trace variable through def-use chains
                from_file = file or '.'  # Use --file if provided, else current dir
                results = engine.trace_variable_flow(variable, from_file, depth=depth)
            else:
                # Default: show variable info (future enhancement)
                results = {'error': 'Please specify --show-flow with --variable'}

    except ValueError as e:
        click.echo(f"\nERROR: {e}", err=True)
        raise click.Abort()
    finally:
        engine.close()

    # Add code snippets if requested and results are caller/callee lists
    if show_code and results:
        from theauditor.utils.code_snippets import CodeSnippetManager
        snippet_manager = CodeSnippetManager(Path.cwd())

        # Handle list of CallSite objects (from get_callers/get_callees)
        if isinstance(results, list) and results and hasattr(results[0], 'caller_file'):
            for call in results:
                snippet = snippet_manager.get_snippet(call.caller_file, call.caller_line, expand_block=False)
                if not snippet.startswith('['):
                    call.arguments.append(f"__snippet__:{snippet}")

        # Handle dict with 'symbol' + 'callers' (default symbol query)
        elif isinstance(results, dict) and 'callers' in results:
            callers = results.get('callers', [])
            if isinstance(callers, list):
                for call in callers:
                    if hasattr(call, 'caller_file'):
                        snippet = snippet_manager.get_snippet(call.caller_file, call.caller_line, expand_block=False)
                        if not snippet.startswith('['):
                            call.arguments.append(f"__snippet__:{snippet}")

    # Format output
    output_str = format_output(results, format=output_format)

    # Print to stdout
    click.echo(output_str)

    # Save if requested
    if save:
        save_path = Path(save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(output_str)
        click.echo(f"\nSaved to: {save_path}", err=True)


# This is now a standalone command, not a subcommand
# Export for CLI registration (no need for alias)
