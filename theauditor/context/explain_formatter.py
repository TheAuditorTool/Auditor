"""Explain command output formatter."""

import json

from theauditor.utils.code_snippets import CodeSnippetManager


class ExplainFormatter:
    """Format explain output for text and JSON modes."""

    SEPARATOR = "=" * 80

    def __init__(
        self, snippet_manager: CodeSnippetManager, show_code: bool = True, limit: int = 20
    ):
        """Initialize formatter."""
        self.snippet_manager = snippet_manager
        self.show_code = show_code
        self.limit = limit

    def format_file_explain(self, data: dict) -> str:
        """Format file explain output."""
        lines = []
        target = data.get("target", "(unknown)")

        lines.append(self.SEPARATOR)
        lines.append(f"EXPLAIN: {target}")
        lines.append(self.SEPARATOR)
        lines.append("")

        symbols = data.get("symbols", [])
        lines.append(
            self._format_section(
                f"SYMBOLS DEFINED ({len(symbols)})", symbols, self._format_symbol_item
            )
        )

        hooks = data.get("hooks", [])
        if hooks:
            lines.append(
                self._format_section(f"HOOKS USED ({len(hooks)})", hooks, self._format_hook_item)
            )

        framework_info = data.get("framework_info", {})

        if framework_info and framework_info.get("framework"):
            lines.append(self._format_framework_section(framework_info))

        imports = data.get("imports", [])
        lines.append(
            self._format_section(
                f"DEPENDENCIES ({len(imports)} imports)", imports, self._format_import_item
            )
        )

        importers = data.get("importers", [])
        lines.append(
            self._format_section(
                f"DEPENDENTS ({len(importers)} files import this)",
                importers,
                self._format_importer_item,
            )
        )

        outgoing = data.get("outgoing_calls", [])
        lines.append(
            self._format_section(
                f"OUTGOING CALLS ({len(outgoing)})", outgoing, self._format_outgoing_call_item
            )
        )

        incoming = data.get("incoming_calls", [])
        lines.append(
            self._format_section(
                f"INCOMING CALLS ({len(incoming)})", incoming, self._format_incoming_call_item
            )
        )

        # Add findings section (from findings_consolidated)
        findings = data.get("findings", [])
        if findings:
            lines.append(self._format_findings_section(findings))

        # Add taint flows section
        taint_flows = data.get("taint_flows", [])
        if taint_flows:
            lines.append(self._format_taint_flows_section(taint_flows, data.get("target", "")))

        lines.append(self.SEPARATOR)
        return "\n".join(lines)

    def format_symbol_explain(self, data: dict) -> str:
        """Format symbol explain output."""
        lines = []
        target = data.get("target", "(unknown)")
        resolved = data.get("resolved_as", [target])

        lines.append(self.SEPARATOR)
        lines.append(f"EXPLAIN: {target}")
        if resolved and resolved[0] != target:
            lines.append(f"  (resolved as: {resolved[0]})")
        lines.append(self.SEPARATOR)
        lines.append("")

        definition = data.get("definition")
        if definition and definition.get("file"):
            lines.append("DEFINITION:")
            file_path = definition.get("file", "")
            line_num = definition.get("line", 0)
            end_line = definition.get("end_line", line_num)
            sym_type = definition.get("type", "symbol")
            signature = definition.get("signature", "")

            lines.append(f"  Type: {sym_type}")
            lines.append(f"  Location: {file_path}:{line_num}")
            if end_line and end_line != line_num:
                lines.append(f"  Span: lines {line_num}-{end_line}")
            if signature:
                lines.append(f"  Signature: {signature}")

            if self.show_code and file_path and line_num:
                snippet = self.snippet_manager.get_snippet(file_path, line_num, expand_block=True)
                if not snippet.startswith("["):
                    lines.append("")
                    for snippet_line in snippet.split("\n"):
                        lines.append(f"      {snippet_line}")
            lines.append("")
        else:
            lines.append("DEFINITION: Not found in index")
            lines.append("")

        callers = data.get("callers", [])
        lines.append(
            self._format_section(f"CALLERS ({len(callers)})", callers, self._format_caller_item)
        )

        callees = data.get("callees", [])
        lines.append(
            self._format_section(f"CALLEES ({len(callees)})", callees, self._format_callee_item)
        )

        lines.append(self.SEPARATOR)
        return "\n".join(lines)

    def format_component_explain(self, data: dict) -> str:
        """Format React/Vue component explain output."""
        lines = []
        target = data.get("target", data.get("name", "(unknown)"))

        lines.append(self.SEPARATOR)
        lines.append(f"EXPLAIN COMPONENT: {target}")
        lines.append(self.SEPARATOR)
        lines.append("")

        lines.append("COMPONENT INFO:")
        lines.append(f"  Name: {data.get('name', target)}")
        lines.append(f"  Type: {data.get('type', 'unknown')}")
        lines.append(f"  File: {data.get('file', '(unknown)')}")

        start_line = data.get("start_line", data.get("line"))
        if start_line:
            lines.append(f"  Line: {start_line}")

        props_type = data.get("props_type")
        if props_type:
            lines.append(f"  Props Type: {props_type}")

        has_jsx = data.get("has_jsx", False)
        lines.append(f"  Has JSX: {'Yes' if has_jsx else 'No'}")
        lines.append("")

        hooks = data.get("hooks", [])
        if isinstance(hooks, list) and hooks:
            if isinstance(hooks[0], str):
                lines.append(f"HOOKS USED ({len(hooks)}):")
                for hook in hooks[: self.limit]:
                    lines.append(f"  - {hook}")
                if len(hooks) > self.limit:
                    lines.append(f"  (and {len(hooks) - self.limit} more)")
            else:
                lines.append(
                    self._format_section(
                        f"HOOKS USED ({len(hooks)})", hooks, self._format_hook_item
                    )
                )
        else:
            lines.append("HOOKS USED (0):")
            lines.append("  (none)")
        lines.append("")

        children = data.get("children", [])
        lines.append(f"CHILD COMPONENTS ({len(children)}):")
        if children:
            for i, child in enumerate(children[: self.limit], 1):
                if isinstance(child, dict):
                    child_name = child.get("child_component", child.get("name", "(unknown)"))
                    child_line = child.get("line", "?")
                    lines.append(f"  {i}. {child_name} (line {child_line})")
                else:
                    lines.append(f"  {i}. {child}")
            if len(children) > self.limit:
                lines.append(f"  (and {len(children) - self.limit} more)")
        else:
            lines.append("  (none)")
        lines.append("")

        lines.append(self.SEPARATOR)
        return "\n".join(lines)

    def format_json(self, data: dict) -> str:
        """Format data as JSON for AI consumption."""
        return json.dumps(data, indent=2, default=str)

    def _format_section(self, title: str, items: list, format_fn) -> str:
        """Format a section with limit and count."""
        lines = [f"{title}:"]

        if not items:
            lines.append("  (none)")
        else:
            displayed = items[: self.limit]
            for i, item in enumerate(displayed, 1):
                formatted = format_fn(item, i)
                lines.append(formatted)

            remaining = len(items) - self.limit
            if remaining > 0:
                lines.append(f"  (and {remaining} more)")

        lines.append("")
        return "\n".join(lines)

    def _format_framework_section(self, framework_info: dict) -> str:
        """Format framework-specific information section."""
        lines = []
        framework = framework_info.get("framework", "unknown")
        lines.append(f"FRAMEWORK INFO ({framework}):")

        routes = framework_info.get("routes", [])
        if routes:
            lines.append(f"  Routes ({len(routes)}):")
            for route in routes[:5]:
                method = route.get("method", "?")
                path = route.get("pattern", route.get("path", "?"))
                lines.append(f"    {method} {path}")
            if len(routes) > 5:
                lines.append(f"    (and {len(routes) - 5} more)")

        middleware = framework_info.get("middleware", [])
        if middleware:
            lines.append(f"  Middleware ({len(middleware)}):")
            for mw in middleware[:5]:
                lines.append(f"    - {mw.get('handler_expr', mw.get('name', '?'))}")
            if len(middleware) > 5:
                lines.append(f"    (and {len(middleware) - 5} more)")

        models = framework_info.get("models", [])
        if models:
            lines.append(f"  ORM Models ({len(models)}):")
            for model in models[:5]:
                lines.append(f"    - {model.get('model_name', '?')}")
            if len(models) > 5:
                lines.append(f"    (and {len(models) - 5} more)")

        lines.append("")
        return "\n".join(lines)

    def _format_symbol_item(self, sym: dict, index: int) -> str:
        """Format a single symbol item."""
        name = sym.get("name", "(unknown)")
        sym_type = sym.get("type", "symbol")
        line_num = sym.get("line", 0)
        end_line = sym.get("end_line", line_num)
        file_path = sym.get("file", sym.get("path", ""))

        result = f"  {index}. {name} ({sym_type}) - line {line_num}"
        if end_line and end_line != line_num:
            result += f"-{end_line}"

        if self.show_code and file_path and line_num:
            snippet = self.snippet_manager.get_snippet(file_path, line_num, expand_block=False)
            if not snippet.startswith("["):
                result += f"\n      {snippet}"

        return result

    def _format_hook_item(self, hook: dict, index: int) -> str:
        """Format a single hook item."""
        if isinstance(hook, str):
            return f"  - {hook}"
        hook_name = hook.get("hook_name", "(unknown)")
        line_num = hook.get("line", "?")
        return f"  - {hook_name} (line {line_num})"

    def _format_import_item(self, imp: dict, index: int) -> str:
        """Format a single import item."""
        module = imp.get("module", imp.get("value", "(unknown)"))
        line_num = imp.get("line", "?")

        is_internal = (
            module.startswith(".") or module.startswith("/") or module.startswith("theauditor")
        )
        scope = "internal" if is_internal else "external"

        return f"  {index}. {module} ({scope}) - line {line_num}"

    def _format_importer_item(self, imp: dict, index: int) -> str:
        """Format a single importer (dependent) item."""
        source = imp.get("source_file", imp.get("source", "(unknown)"))
        line_num = imp.get("line", "")
        loc = f":{line_num}" if line_num else ""
        return f"  {index}. {source}{loc}"

    def _format_outgoing_call_item(self, call: dict, index: int) -> str:
        """Format a single outgoing call item."""
        callee = call.get("callee_function", "(unknown)")
        line_num = call.get("line", 0)
        args = call.get("arguments", "")
        file_path = call.get("file", "")

        result = (
            f"  {index}. line {line_num}: {callee}({args[:30]}{'...' if len(args) > 30 else ''})"
        )

        if self.show_code and file_path and line_num:
            snippet = self.snippet_manager.get_snippet(file_path, line_num, expand_block=False)
            if not snippet.startswith("["):
                result += f"\n      {snippet}"

        return result

    def _format_incoming_call_item(self, call: dict, index: int) -> str:
        """Format a single incoming call item."""
        caller_file = call.get("caller_file", "(unknown)")
        caller_line = call.get("caller_line", "?")
        caller_func = call.get("caller_function", "(top-level)")
        callee_func = call.get("callee_function", "?")

        result = f"  {index}. {caller_file}:{caller_line} - {caller_func}() calls {callee_func}"

        if self.show_code and caller_file and caller_line and caller_line != "?":
            snippet = self.snippet_manager.get_snippet(caller_file, caller_line, expand_block=False)
            if not snippet.startswith("["):
                result += f"\n      {snippet}"

        return result

    def _format_caller_item(self, call: dict, index: int) -> str:
        """Format a single caller item (for symbol explain)."""
        caller_file = call.get("file", call.get("caller_file", "(unknown)"))
        caller_line = call.get("line", call.get("caller_line", "?"))
        caller_func = call.get("caller_function", "(top-level)")

        result = f"  {index}. {caller_file}:{caller_line}"
        result += f"\n     Called from: {caller_func}()"

        if self.show_code and caller_file and caller_line and caller_line != "?":
            snippet = self.snippet_manager.get_snippet(
                caller_file, int(caller_line), expand_block=False
            )
            if not snippet.startswith("["):
                result += f"\n      {snippet}"

        return result

    def _format_callee_item(self, call: dict, index: int) -> str:
        """Format a single callee item (for symbol explain)."""
        callee = call.get("callee_function", "(unknown)")
        file_path = call.get("file", call.get("caller_file", ""))
        line_num = call.get("line", call.get("caller_line", "?"))

        result = f"  {index}. {callee}"
        if file_path:
            result += f" at {file_path}:{line_num}"

        if self.show_code and file_path and line_num and line_num != "?":
            snippet = self.snippet_manager.get_snippet(file_path, int(line_num), expand_block=False)
            if not snippet.startswith("["):
                result += f"\n      {snippet}"

        return result

    def _format_findings_section(self, findings: list[dict]) -> str:
        """Format findings from findings_consolidated.

        Groups by severity, shows most critical first.
        """
        lines = []

        # Count by severity
        severity_counts = {}
        for f in findings:
            sev = f.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Build header with counts
        count_parts = []
        for sev in ["critical", "high", "medium", "low"]:
            if sev in severity_counts:
                count_parts.append(f"{severity_counts[sev]} {sev}")

        header = f"KNOWN ISSUES ({len(findings)})"
        if count_parts:
            header += f" - {', '.join(count_parts)}"

        lines.append(f"{header}:")

        # Show findings (already sorted by severity from query)
        displayed = findings[: self.limit]
        for i, f in enumerate(displayed, 1):
            severity = f.get("severity", "?").upper()
            category = f.get("category", "")
            rule = f.get("rule", "")
            line_num = f.get("line", "?")
            message = f.get("message", "")
            tool = f.get("tool", "")

            # Truncate message
            if len(message) > 60:
                message = message[:57] + "..."

            lines.append(f"  {i}. [{severity}] {category}: {rule}")
            lines.append(f"     Line {line_num} ({tool}): {message}")

        remaining = len(findings) - self.limit
        if remaining > 0:
            lines.append(f"  (and {remaining} more)")

        lines.append("")
        return "\n".join(lines)

    def _format_taint_flows_section(self, flows: list[dict], target_file: str) -> str:
        """Format taint flows involving this file.

        Shows source->sink paths with vulnerability type.
        """
        lines = []
        lines.append(f"TAINT FLOWS ({len(flows)}):")

        if not flows:
            lines.append("  (none)")
            lines.append("")
            return "\n".join(lines)

        displayed = flows[: self.limit]
        for i, flow in enumerate(displayed, 1):
            vuln_type = flow.get("vulnerability_type", "Unknown")
            source_file = flow.get("source_file", "?")
            source_line = flow.get("source_line", "?")
            source_pattern = flow.get("source_pattern", "?")
            sink_file = flow.get("sink_file", "?")
            sink_line = flow.get("sink_line", "?")
            sink_pattern = flow.get("sink_pattern", "?")
            path_length = flow.get("path_length", "?")

            # Indicate direction relative to target file
            if source_file == target_file:
                direction = "SOURCE"
            elif sink_file == target_file:
                direction = "SINK"
            else:
                direction = "PASS-THROUGH"

            lines.append(f"  {i}. [{vuln_type}] ({direction})")
            lines.append(f"     Source: {source_file}:{source_line} ({source_pattern})")
            lines.append(f"     Sink:   {sink_file}:{sink_line} ({sink_pattern})")
            lines.append(f"     Path:   {path_length} hops")

        remaining = len(flows) - self.limit
        if remaining > 0:
            lines.append(f"  (and {remaining} more)")

        lines.append("")
        return "\n".join(lines)
