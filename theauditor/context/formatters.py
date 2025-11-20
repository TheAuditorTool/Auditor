"""Output formatters for query results.

Supports three formats:
- text: Human-readable (default)
- json: AI-consumable structured data
- tree: Visual hierarchy (for transitive queries)

NO EMOJIS: Windows Command Prompt uses CP1252 encoding which cannot
handle emoji characters. All output uses plain ASCII only.

Usage:
    from theauditor.context.formatters import format_output

    results = engine.get_callers("authenticateUser")
    text = format_output(results, format='text')
    json_str = format_output(results, format='json')
"""


import json
from typing import Any, List, Dict
from dataclasses import asdict, is_dataclass


def format_output(results: Any, format: str = 'text') -> str:
    """Format query results in specified format.

    Args:
        results: Query results (varies by query type)
        format: 'text', 'json', or 'tree'

    Returns:
        Formatted string ready for output

    Example:
        text = format_output(symbols, format='text')
        print(text)
    """
    if format == 'json':
        return _format_json(results)
    elif format == 'tree':
        return _format_tree(results)
    else:
        return _format_text(results)


def _format_text(results: Any) -> str:
    """Format as human-readable text.

    Handles different result types:
    - Dict with 'symbol' + 'callers' keys (find_symbol + get_callers)
    - List[CallSite] (callers/callees)
    - Dict with 'incoming'/'outgoing' keys (file dependencies)
    - List[Dict] (API endpoints)
    - Dict with 'name' key (component tree)
    - Dict with 'error' key (error response)
    """
    # Error responses
    if isinstance(results, dict) and 'error' in results:
        return f"ERROR: {results['error']}"

    # Symbol info + callers (combined query)
    if isinstance(results, dict) and 'symbol' in results and 'callers' in results:
        lines = []

        # Symbol definitions
        symbols = results['symbol']
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
                    lines.append(f"     Exported: Yes")
                lines.append("")
        else:
            lines.append("No symbol definitions found.")
            lines.append("")

        # Callers
        callers = results['callers']
        lines.append(f"Callers ({len(callers)}):")
        if callers:
            for i, call in enumerate(callers, 1):
                caller = call.caller_function or '(top-level)'
                lines.append(f"  {i}. {call.caller_file}:{call.caller_line}")
                lines.append(f"     {caller} -> {call.callee_function}")
                if call.arguments and call.arguments[0]:
                    args_str = call.arguments[0]
                    if len(args_str) > 60:
                        args_str = args_str[:57] + "..."
                    lines.append(f"     Args: {args_str}")
        else:
            lines.append("  (none)")

        return "\n".join(lines)

    # List of call sites (callers or callees)
    if isinstance(results, list) and results and hasattr(results[0], 'caller_file'):
        lines = [f"Results ({len(results)}):"]
        if results:
            for i, call in enumerate(results, 1):
                caller = call.caller_function or '(top-level)'
                lines.append(f"  {i}. {call.caller_file}:{call.caller_line}")
                lines.append(f"     {caller} -> {call.callee_function}")
                if call.arguments and call.arguments[0]:
                    args_str = call.arguments[0]
                    if len(args_str) > 60:
                        args_str = args_str[:57] + "..."
                    lines.append(f"     Args: {args_str}")
        else:
            lines.append("  (none)")
        return "\n".join(lines)

    # File dependencies (incoming/outgoing)
    if isinstance(results, dict) and ('incoming' in results or 'outgoing' in results):
        lines = []

        if 'incoming' in results:
            incoming = results['incoming']
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

        if 'outgoing' in results:
            outgoing = results['outgoing']
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

    # API endpoints
    if isinstance(results, list) and results and isinstance(results[0], dict) and 'method' in results[0]:
        lines = [f"API Endpoints ({len(results)}):"]
        if results:
            for i, ep in enumerate(results, 1):
                method = ep.get('method', 'UNKNOWN')
                path = ep.get('path') or ep.get('pattern', '(unknown)')
                has_auth = ep.get('has_auth', False)
                auth_marker = "[AUTH]" if has_auth else "[OPEN]"

                lines.append(f"  {i}. {method:6s} {path:40s} {auth_marker}")

                handler = ep.get('handler_function', '(unknown)')
                file_path = ep.get('file', '')
                line_num = ep.get('line', '')

                if file_path:
                    location = f"{file_path[-40:]}:{line_num}" if line_num else file_path[-40:]
                    lines.append(f"     Handler: {handler} ({location})")
                else:
                    lines.append(f"     Handler: {handler}")
        else:
            lines.append("  (none)")

        return "\n".join(lines)

    # Component tree
    if isinstance(results, dict) and 'name' in results and 'file' in results:
        lines = []
        lines.append(f"Component: {results['name']}")
        lines.append(f"  Type: {results.get('type', 'unknown')}")

        file_path = results['file']
        start_line = results.get('start_line', results.get('line', '?'))
        lines.append(f"  File: {file_path}:{start_line}")

        has_jsx = results.get('has_jsx', False)
        lines.append(f"  Has JSX: {'Yes' if has_jsx else 'No'}")

        lines.append("")

        # Hooks
        hooks = results.get('hooks', [])
        lines.append(f"Hooks Used ({len(hooks)}):")
        if hooks:
            for hook in hooks:
                lines.append(f"  - {hook}")
        else:
            lines.append("  (none)")

        lines.append("")

        # Children
        children = results.get('children', [])
        lines.append(f"Child Components ({len(children)}):")
        if children:
            for child in children:
                child_name = child.get('child_component', '(unknown)')
                child_line = child.get('line', '?')
                lines.append(f"  - {child_name} (line {child_line})")
        else:
            lines.append("  (none)")

        return "\n".join(lines)

    # Data dependencies (reads/writes) - DFG
    if isinstance(results, dict) and 'reads' in results and 'writes' in results:
        lines = []

        reads = results['reads']
        writes = results['writes']

        lines.append(f"Data Dependencies:")
        lines.append("")
        lines.append(f"  Reads ({len(reads)}):")
        if reads:
            for read in reads:
                var = read['variable']
                lines.append(f"    - {var}")
        else:
            lines.append("    (none)")

        lines.append("")
        lines.append(f"  Writes ({len(writes)}):")
        if writes:
            for write in writes:
                var = write['variable']
                expr = write['expression']
                loc = f"{write['file']}:{write['line']}"
                if len(expr) > 50:
                    expr = expr[:47] + "..."
                lines.append(f"    - {var} = {expr}")
                lines.append(f"      ({loc})")
        else:
            lines.append("    (none)")

        return "\n".join(lines)

    # Variable flow tracing (def-use chains) - DFG
    if isinstance(results, list) and results and isinstance(results[0], dict) and 'from_var' in results[0]:
        lines = [f"Variable Flow ({len(results)} steps):"]
        if results:
            for i, step in enumerate(results, 1):
                from_var = step['from_var']
                to_var = step['to_var']
                loc = f"{step['file']}:{step['line']}"
                depth_level = step.get('depth', 1)
                func = step.get('function', 'global')

                lines.append(f"  {i}. {from_var} -> {to_var}")
                lines.append(f"     Location: {loc}")
                lines.append(f"     Function: {func}")
                lines.append(f"     Depth: {depth_level}")

                expr = step.get('expression', '')
                if expr and len(expr) <= 60:
                    lines.append(f"     Expression: {expr}")
                lines.append("")
        else:
            lines.append("  (no flow found)")
        return "\n".join(lines)

    # Cross-function taint flow - DFG
    if isinstance(results, list) and results and isinstance(results[0], dict) and 'flow_type' in results[0] and results[0]['flow_type'] == 'cross_function_taint':
        lines = [f"Cross-Function Taint Flow ({len(results)} flows):"]
        if results:
            for i, flow in enumerate(results, 1):
                return_var = flow['return_var']
                return_loc = f"{flow['return_file']}:{flow['return_line']}"
                assign_var = flow['assignment_var']
                assign_loc = f"{flow['assignment_file']}:{flow['assignment_line']}"
                assign_func = flow['assigned_in_function']

                lines.append(f"  {i}. Return: {return_var} at {return_loc}")
                lines.append(f"     Assigned: {assign_var} at {assign_loc}")
                lines.append(f"     In function: {assign_func}")
                lines.append("")
        else:
            lines.append("  (no cross-function flows found)")
        return "\n".join(lines)

    # API security coverage - DFG
    if isinstance(results, list) and results and isinstance(results[0], dict) and 'controls' in results[0] and 'has_auth' in results[0]:
        lines = [f"API Security Coverage ({len(results)} endpoints):"]
        if results:
            for i, ep in enumerate(results, 1):
                method = ep.get('method', 'UNKNOWN')
                path = ep.get('path', '(unknown)')
                controls = ep.get('controls', [])
                control_count = ep.get('control_count', 0)
                has_auth = ep.get('has_auth', False)

                auth_status = f"{control_count} controls" if has_auth else "NO AUTH"
                lines.append(f"  {i}. {method:6s} {path:40s} [{auth_status}]")

                if controls:
                    controls_str = ", ".join(controls)
                    lines.append(f"     Controls: {controls_str}")

                handler = ep.get('handler_function', '')
                if handler:
                    loc = f"{ep.get('file', '')}:{ep.get('line', '')}"
                    lines.append(f"     Handler: {handler} ({loc})")
                lines.append("")
        else:
            lines.append("  (no endpoints found)")
        return "\n".join(lines)

    # Fallback: JSON dump for unknown types
    return json.dumps(_to_dict(results), indent=2, default=str)


def _format_json(results: Any) -> str:
    """Format as JSON.

    Converts dataclasses to dicts recursively and serializes as JSON.

    Args:
        results: Any query result type

    Returns:
        JSON string with 2-space indentation
    """
    return json.dumps(_to_dict(results), indent=2, default=str)


def _format_tree(results: Any) -> str:
    """Format as visual tree (for transitive queries).

    Currently a placeholder - falls back to text format.
    Full tree visualization will be implemented in future phase.

    Args:
        results: Query results

    Returns:
        Tree-formatted string (currently text format)
    """
    # TODO: Implement proper tree visualization
    # For now, fall back to text format
    return _format_text(results)


def _to_dict(obj: Any) -> Any:
    """Convert dataclass to dict recursively.

    Handles:
    - Dataclasses (convert with asdict)
    - Lists (recurse on each item)
    - Dicts (recurse on values)
    - Other types (return as-is)

    Args:
        obj: Object to convert

    Returns:
        Dict representation suitable for JSON serialization
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        # Convert dataclass to dict
        return asdict(obj)
    elif isinstance(obj, list):
        # Recurse on list items
        return [_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        # Recurse on dict values
        return {k: _to_dict(v) for k, v in obj.items()}
    else:
        # Return as-is (primitives, None, etc.)
        return obj
