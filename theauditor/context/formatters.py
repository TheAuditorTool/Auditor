"""Output formatters for query results."""

import json
from dataclasses import asdict, is_dataclass
from typing import Any


def format_output(results: Any, format: str = "text") -> str:
    """Format query results in specified format."""
    if format == "json":
        return _format_json(results)
    elif format == "tree":
        return _format_tree(results)
    else:
        return _format_text(results)


def _format_text(results: Any) -> str:
    """Format as human-readable text."""

    if isinstance(results, dict) and "error" in results:
        return f"ERROR: {results['error']}"

    if isinstance(results, dict) and results.get("type") == "list_formatted":
        return results.get("output", "")

    if isinstance(results, dict) and results.get("type") == "discovery":
        lines = []
        filter_str = results.get("filter", "*")
        path_str = results.get("path", "(all)")
        type_str = results.get("type_filter") or "(all types)"
        count = results.get("count", 0)
        symbols = results.get("symbols", [])

        lines.append("Symbol Discovery Results")
        lines.append(f"  Filter: {filter_str}")
        lines.append(f"  Path:   {path_str}")
        lines.append(f"  Type:   {type_str}")
        lines.append(f"  Found:  {count} symbols")
        lines.append("")

        if symbols:
            by_file = {}
            for sym in symbols:
                file_path = sym.file if hasattr(sym, "file") else sym.get("file", "?")
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(sym)

            for file_path in sorted(by_file.keys()):
                file_symbols = by_file[file_path]

                display_path = file_path[-60:] if len(file_path) > 60 else file_path
                if len(file_path) > 60:
                    display_path = "..." + display_path
                lines.append(f"{display_path}:")
                for sym in file_symbols:
                    name = sym.name if hasattr(sym, "name") else sym.get("name", "?")
                    sym_type = sym.type if hasattr(sym, "type") else sym.get("type", "?")
                    line_num = sym.line if hasattr(sym, "line") else sym.get("line", "?")
                    lines.append(f"  :{line_num:<5} {sym_type:<12} {name}")
                lines.append("")
        else:
            lines.append("No symbols found matching criteria.")

        return "\n".join(lines)

    if isinstance(results, dict) and results.get("type") == "pattern_search":
        lines = []
        pattern = results.get("pattern", "?")
        path_str = results.get("path", "(all)")
        type_str = results.get("type_filter") or "(all types)"
        count = results.get("count", 0)
        symbols = results.get("symbols", [])

        lines.append("Pattern Search Results")
        lines.append(f"  Pattern: {pattern}  (searches symbol NAMES, not code content)")
        lines.append(f"  Path:    {path_str}")
        lines.append(f"  Type:    {type_str}")
        lines.append(f"  Found:   {count} symbols")
        lines.append("")

        if symbols:
            by_file = {}
            for sym in symbols:
                file_path = sym.file if hasattr(sym, "file") else sym.get("file", "?")
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(sym)

            for file_path in sorted(by_file.keys()):
                file_symbols = by_file[file_path]

                display_path = file_path[-60:] if len(file_path) > 60 else file_path
                if len(file_path) > 60:
                    display_path = "..." + display_path
                lines.append(f"{display_path}:")
                for sym in file_symbols:
                    name = sym.name if hasattr(sym, "name") else sym.get("name", "?")
                    sym_type = sym.type if hasattr(sym, "type") else sym.get("type", "?")
                    line_num = sym.line if hasattr(sym, "line") else sym.get("line", "?")
                    lines.append(f"  :{line_num:<5} {sym_type:<12} {name}")
                lines.append("")
        else:
            lines.append("No symbols found matching pattern.")
            lines.append("")
            lines.append("Suggestions:")
            lines.append("  - Pattern searches symbol NAMES (functions, classes, variables)")
            lines.append("  - Use % for wildcards: '%auth%', 'User%', '%Controller%'")
            lines.append("  - For code TEXT search, use: grep -r 'your pattern' .")
            lines.append("  - Verify path: aud query --list-symbols --path 'your/path/'")
            lines.append("  - Re-index if code changed: aud full --index")

        return "\n".join(lines)

    if isinstance(results, dict) and "symbol" in results and "callers" in results:
        lines = []

        symbols = results["symbol"]
        if symbols:
            lines.append(f"Symbol Definitions ({len(symbols)}):")
            for i, sym in enumerate(symbols, 1):
                lines.append(f"  {i}. {sym.name}")
                lines.append(f"     Type: {sym.type}")
                lines.append(f"     File: {sym.file}:{sym.line}")
                if sym.end_line != sym.line:
                    lines[-1] += f"-{sym.end_line}"
                if sym.signature:
                    lines.append(f"     Signature: {sym.signature}")
                if sym.is_exported:
                    lines.append("     Exported: Yes")
                lines.append("")
        else:
            lines.append("No symbol definitions found.")
            lines.append("")

        callers = results["callers"]

        if isinstance(callers, dict) and "error" in callers:
            lines.append(f"Callers: {callers['error']}")
        else:
            lines.append(f"Callers ({len(callers)}):")
            if callers:
                for i, call in enumerate(callers, 1):
                    caller = call.caller_function or "(top-level)"
                    lines.append(f"  {i}. {call.caller_file}:{call.caller_line}")
                    lines.append(f"     {caller} -> {call.callee_function}")

                    regular_args = [
                        a for a in (call.arguments or []) if not a.startswith("__snippet__:")
                    ]
                    if regular_args and regular_args[0]:
                        args_str = regular_args[0]
                        if len(args_str) > 60:
                            args_str = args_str[:57] + "..."
                        lines.append(f"     Args: {args_str}")

                    snippet_args = [
                        a for a in (call.arguments or []) if a.startswith("__snippet__:")
                    ]
                    if snippet_args:
                        snippet = snippet_args[0].replace("__snippet__:", "", 1)
                        lines.append(f"     {snippet}")
            else:
                lines.append("  (none)")

        return "\n".join(lines)

    if isinstance(results, list) and results and hasattr(results[0], "caller_file"):
        lines = [f"Results ({len(results)}):"]
        if results:
            for i, call in enumerate(results, 1):
                caller = call.caller_function or "(top-level)"
                lines.append(f"  {i}. {call.caller_file}:{call.caller_line}")
                lines.append(f"     {caller} -> {call.callee_function}")

                regular_args = [
                    a for a in (call.arguments or []) if not a.startswith("__snippet__:")
                ]
                if regular_args and regular_args[0]:
                    args_str = regular_args[0]
                    if len(args_str) > 60:
                        args_str = args_str[:57] + "..."
                    lines.append(f"     Args: {args_str}")

                snippet_args = [a for a in (call.arguments or []) if a.startswith("__snippet__:")]
                if snippet_args:
                    snippet = snippet_args[0].replace("__snippet__:", "", 1)
                    lines.append(f"     {snippet}")
        else:
            lines.append("  (none)")
        return "\n".join(lines)

    if isinstance(results, dict) and ("incoming" in results or "outgoing" in results):
        lines = []

        if "incoming" in results:
            incoming = results["incoming"]
            lines.append(f"Incoming Dependencies ({len(incoming)}):")
            if incoming:
                lines.append("  (Files that import this file)")
                for i, dep in enumerate(incoming, 1):
                    source = dep.source_file[-50:] if len(dep.source_file) > 50 else dep.source_file
                    lines.append(f"  {i}. {source}")
                    lines.append(f"     Type: {dep.import_type}")
            else:
                lines.append("  (none)")
            lines.append("")

        if "outgoing" in results:
            outgoing = results["outgoing"]
            lines.append(f"Outgoing Dependencies ({len(outgoing)}):")
            if outgoing:
                lines.append("  (Files imported by this file)")
                for i, dep in enumerate(outgoing, 1):
                    target = dep.target_file[-50:] if len(dep.target_file) > 50 else dep.target_file
                    lines.append(f"  {i}. {target}")
                    lines.append(f"     Type: {dep.import_type}")
            else:
                lines.append("  (none)")

        return "\n".join(lines)

    if (
        isinstance(results, list)
        and results
        and isinstance(results[0], dict)
        and "method" in results[0]
    ):
        lines = [f"API Endpoints ({len(results)}):"]
        if results:
            for i, ep in enumerate(results, 1):
                method = ep.get("method", "UNKNOWN")
                path = ep.get("path") or ep.get("pattern", "(unknown)")
                has_auth = ep.get("has_auth", False)
                auth_marker = "[AUTH]" if has_auth else "[OPEN]"

                lines.append(f"  {i}. {method:6s} {path:40s} {auth_marker}")

                handler = ep.get("handler_function", "(unknown)")
                file_path = ep.get("file", "")
                line_num = ep.get("line", "")

                if file_path:
                    location = f"{file_path[-40:]}:{line_num}" if line_num else file_path[-40:]
                    lines.append(f"     Handler: {handler} ({location})")
                else:
                    lines.append(f"     Handler: {handler}")
        else:
            lines.append("  (none)")

        return "\n".join(lines)

    if isinstance(results, dict) and "name" in results and "file" in results:
        lines = []
        lines.append(f"Component: {results['name']}")
        lines.append(f"  Type: {results.get('type', 'unknown')}")

        file_path = results["file"]
        start_line = results.get("start_line", results.get("line", "?"))
        lines.append(f"  File: {file_path}:{start_line}")

        has_jsx = results.get("has_jsx", False)
        lines.append(f"  Has JSX: {'Yes' if has_jsx else 'No'}")

        lines.append("")

        hooks = results.get("hooks", [])
        lines.append(f"Hooks Used ({len(hooks)}):")
        if hooks:
            for hook in hooks:
                lines.append(f"  - {hook}")
        else:
            lines.append("  (none)")

        lines.append("")

        children = results.get("children", [])
        lines.append(f"Child Components ({len(children)}):")
        if children:
            for child in children:
                child_name = child.get("child_component", "(unknown)")
                child_line = child.get("line", "?")
                lines.append(f"  - {child_name} (line {child_line})")
        else:
            lines.append("  (none)")

        return "\n".join(lines)

    if isinstance(results, dict) and "reads" in results and "writes" in results:
        lines = []

        reads = results["reads"]
        writes = results["writes"]

        lines.append("Data Dependencies:")
        lines.append("")
        lines.append(f"  Reads ({len(reads)}):")
        if reads:
            for read in reads:
                var = read["variable"]
                lines.append(f"    - {var}")
        else:
            lines.append("    (none)")

        lines.append("")
        lines.append(f"  Writes ({len(writes)}):")
        if writes:
            for write in writes:
                var = write["variable"]
                expr = write["expression"]
                loc = f"{write['file']}:{write['line']}"
                if len(expr) > 50:
                    expr = expr[:47] + "..."
                lines.append(f"    - {var} = {expr}")
                lines.append(f"      ({loc})")
        else:
            lines.append("    (none)")

        return "\n".join(lines)

    if (
        isinstance(results, list)
        and results
        and isinstance(results[0], dict)
        and "from_var" in results[0]
    ):
        lines = [f"Variable Flow ({len(results)} steps):"]
        if results:
            for i, step in enumerate(results, 1):
                from_var = step["from_var"]
                to_var = step["to_var"]
                loc = f"{step['file']}:{step['line']}"
                depth_level = step.get("depth", 1)
                func = step.get("function", "global")

                lines.append(f"  {i}. {from_var} -> {to_var}")
                lines.append(f"     Location: {loc}")
                lines.append(f"     Function: {func}")
                lines.append(f"     Depth: {depth_level}")

                expr = step.get("expression", "")
                if expr and len(expr) <= 60:
                    lines.append(f"     Expression: {expr}")
                lines.append("")
        else:
            lines.append("  (no flow found)")
        return "\n".join(lines)

    if (
        isinstance(results, list)
        and results
        and isinstance(results[0], dict)
        and "flow_type" in results[0]
        and results[0]["flow_type"] == "cross_function_taint"
    ):
        lines = [f"Cross-Function Taint Flow ({len(results)} flows):"]
        if results:
            for i, flow in enumerate(results, 1):
                return_var = flow["return_var"]
                return_loc = f"{flow['return_file']}:{flow['return_line']}"
                assign_var = flow["assignment_var"]
                assign_loc = f"{flow['assignment_file']}:{flow['assignment_line']}"
                assign_func = flow["assigned_in_function"]

                lines.append(f"  {i}. Return: {return_var} at {return_loc}")
                lines.append(f"     Assigned: {assign_var} at {assign_loc}")
                lines.append(f"     In function: {assign_func}")
                lines.append("")
        else:
            lines.append("  (no cross-function flows found)")
        return "\n".join(lines)

    if (
        isinstance(results, list)
        and results
        and isinstance(results[0], dict)
        and "controls" in results[0]
        and "has_auth" in results[0]
    ):
        lines = [f"API Security Coverage ({len(results)} endpoints):"]
        if results:
            for i, ep in enumerate(results, 1):
                method = ep.get("method", "UNKNOWN")
                path = ep.get("path", "(unknown)")
                controls = ep.get("controls", [])
                control_count = ep.get("control_count", 0)
                has_auth = ep.get("has_auth", False)

                auth_status = f"{control_count} controls" if has_auth else "NO AUTH"
                lines.append(f"  {i}. {method:6s} {path:40s} [{auth_status}]")

                if controls:
                    controls_str = ", ".join(controls)
                    lines.append(f"     Controls: {controls_str}")

                handler = ep.get("handler_function", "")
                if handler:
                    loc = f"{ep.get('file', '')}:{ep.get('line', '')}"
                    lines.append(f"     Handler: {handler} ({loc})")
                lines.append("")
        else:
            lines.append("  (no endpoints found)")
        return "\n".join(lines)

    # Handle findings results
    if isinstance(results, dict) and results.get("type") == "findings":
        from theauditor.context.findings_formatter import format_findings_plain

        return format_findings_plain(results)

    return json.dumps(_to_dict(results), indent=2, default=str)


def _format_json(results: Any) -> str:
    """Format as JSON."""
    return json.dumps(_to_dict(results), indent=2, default=str)


def _format_tree(results: Any) -> str:
    """Format as visual tree (for transitive queries)."""

    return _format_text(results)


def _to_dict(obj: Any) -> Any:
    """Convert dataclass to dict recursively."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    elif isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    else:
        return obj
