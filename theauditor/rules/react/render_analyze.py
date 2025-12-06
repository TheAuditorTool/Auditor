"""React Render Analyzer - Detects rendering performance issues and anti-patterns.

Checks for:
- Expensive operations (sort/filter/map) in render path
- Direct state/props mutations
- Inline functions causing re-renders
- Missing key props in lists
- Object creation in render path
- Using array index as key
- Unnecessary derived state
- Anonymous functions passed as props
- Components with excessive state/effects
- Inline style objects
"""

from dataclasses import dataclass

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="react_render_issues",
    category="react",
    target_extensions=[".jsx", ".tsx", ".js", ".ts"],
    target_file_patterns=["frontend/", "client/", "src/"],
    exclude_patterns=[
        "node_modules/",
        "__tests__/",
        "*.test.jsx",
        "*.test.tsx",
        "*.spec.jsx",
        "*.spec.tsx",
        "migrations/",
    ],
    execution_scope="database",
    primary_table="react_components",
)


@dataclass(frozen=True)
class ReactRenderPatterns:
    """Immutable pattern definitions for React rendering issues."""

    EXPENSIVE_OPERATIONS: frozenset = frozenset(
        [
            "sort",
            "filter",
            "map",
            "reduce",
            "find",
            "findIndex",
            "forEach",
            "reverse",
            "concat",
            "slice",
            "splice",
        ]
    )

    MUTATING_METHODS: frozenset = frozenset(
        ["push", "pop", "shift", "unshift", "splice", "sort", "reverse", "fill", "copyWithin"]
    )

    OBJECT_CREATORS: frozenset = frozenset(
        [
            "Object.create",
            "Object.assign",
            "Object.freeze",
            "Array.from",
            "Array.of",
            "new Array",
            "new Object",
            "new Map",
            "new Set",
            "new Date",
            "Date.now",
        ]
    )

    EVENT_HANDLERS: frozenset = frozenset(
        [
            "onClick",
            "onChange",
            "onSubmit",
            "onFocus",
            "onBlur",
            "onMouseEnter",
            "onMouseLeave",
            "onKeyDown",
            "onKeyUp",
            "onScroll",
            "onLoad",
            "onError",
            "onDragStart",
            "onDrop",
        ]
    )


class ReactRenderAnalyzer:
    """Analyzer for React rendering performance and optimization."""

    def __init__(self, db: RuleDB):
        """Initialize analyzer with database context."""
        self.db = db
        self.patterns = ReactRenderPatterns()
        self.findings: list[StandardFinding] = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        self._check_expensive_operations()
        self._check_array_mutations()
        self._check_inline_functions()
        self._check_missing_keys()
        self._check_object_creation()
        self._check_index_as_key()
        self._check_derived_state()
        self._check_anonymous_functions_in_props()
        self._check_excessive_renders()
        self._check_style_objects()

        return self.findings

    def _check_expensive_operations(self) -> None:
        """Check for expensive operations in render methods."""
        components = list(
            self.db.query(Q("react_components").select("file", "name", "start_line", "end_line"))
        )

        component_ranges: dict[str, list[tuple]] = {}
        for file, name, start, end in components:
            if file not in component_ranges:
                component_ranges[file] = []
            component_ranges[file].append((name, start or 0, end or 0))

        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "caller_function")
            .limit(1000)
        )

        for file, line, callee, caller in rows:
            if not callee:
                continue

            if caller and ("useMemo" in caller or "useCallback" in caller):
                continue

            operation = None
            for op in self.patterns.EXPENSIVE_OPERATIONS:
                if f".{op}" in callee:
                    operation = op
                    break

            if not operation:
                continue

            component_name = None
            if file in component_ranges:
                for name, start, end in component_ranges[file]:
                    if start <= line <= end:
                        component_name = name
                        break

            if component_name:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-expensive-operation",
                        message=f"Expensive {operation}() operation in render path of {component_name}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="react-performance",
                        snippet=f"{callee} in {component_name}",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1050",
                    )
                )

    def _check_array_mutations(self) -> None:
        """Check for direct array/object mutations."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("argument_expr IS NOT NULL")
            .limit(500)
        )

        for file, line, callee, args in rows:
            if not callee or not args:
                continue

            args_str = str(args)
            if "state" not in args_str and "props" not in args_str:
                continue

            method_found = None
            for method in self.patterns.MUTATING_METHODS:
                if f".{method}" in callee:
                    method_found = method
                    break

            if method_found:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-direct-mutation",
                        message=f"Direct state/props mutation using {method_found}()",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="react-state",
                        snippet=callee,
                        confidence=Confidence.HIGH if "state" in args_str else Confidence.MEDIUM,
                        cwe_id="CWE-682",
                    )
                )

    def _check_inline_functions(self) -> None:
        """Check for inline arrow functions in render."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "argument_expr", "callee_function")
            .where("argument_expr IS NOT NULL")
            .limit(500)
        )

        for file, line, args, callee in rows:
            if callee and callee.startswith("use"):
                continue

            args_str = str(args) if args else ""
            has_inline = (
                "() =>" in args_str
                or "function()" in args_str
                or "function (" in args_str
                or ".bind(" in args_str
            )

            if not has_inline:
                continue

            if any(handler in args_str for handler in self.patterns.EVENT_HANDLERS):
                self.findings.append(
                    StandardFinding(
                        rule_name="react-inline-function",
                        message="Inline function in event handler will cause unnecessary re-renders",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-performance",
                        snippet="Inline arrow function or bind()",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1050",
                    )
                )

    def _check_missing_keys(self) -> None:
        """Check for missing key props in lists rendered with .map()."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function LIKE ?", "%.map%")
            .limit(500)
        )

        for file, line, callee, args in rows:
            args_str = str(args) if args else ""

            if "key=" in args_str or "key:" in args_str:
                continue

            if "<" not in args_str and "return" not in args_str:
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="react-missing-key",
                    message="Array.map() rendering JSX without key prop",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="react-performance",
                    snippet=callee or ".map()",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1050",
                )
            )

    def _check_object_creation(self) -> None:
        """Check for object/array creation in render path."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function")
            .where("callee_function IS NOT NULL")
            .limit(500)
        )

        for file, line, callee in rows:
            if not callee:
                continue

            if "use" in callee.lower():
                continue

            for creator in self.patterns.OBJECT_CREATORS:
                if creator in callee:
                    self.findings.append(
                        StandardFinding(
                            rule_name="react-object-creation",
                            message=f"Creating new object with {creator} in render path",
                            file_path=file,
                            line=line,
                            severity=Severity.LOW,
                            category="react-performance",
                            snippet=callee,
                            confidence=Confidence.LOW,
                            cwe_id="CWE-1050",
                        )
                    )
                    break

    def _check_index_as_key(self) -> None:
        """Check for using array index as key prop."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function LIKE ?", "%.map%")
            .where("argument_expr IS NOT NULL")
            .limit(500)
        )

        for file, line, _callee, args in rows:
            args_str = str(args) if args else ""

            has_index_key = (
                "key={index}" in args_str
                or "key={i}" in args_str
                or "key={idx}" in args_str
                or "key: index" in args_str
                or "key: i," in args_str
            )

            if has_index_key:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-index-key",
                        message="Using array index as key prop can cause rendering issues with list reordering",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="react-performance",
                        snippet="key={index}",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1050",
                    )
                )

    def _check_derived_state(self) -> None:
        """Check for unnecessary derived state from props."""
        use_state_rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "component_name")
            .where("hook_name = ?", "useState")
            .limit(200)
        )

        use_effect_rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "component_name", "dependency_array")
            .where("hook_name = ?", "useEffect")
            .where("dependency_array IS NOT NULL")
            .limit(200)
        )

        effects_by_component: dict[tuple, list[tuple]] = {}
        for file, line, component, deps in use_effect_rows:
            key = (file, component)
            if key not in effects_by_component:
                effects_by_component[key] = []
            effects_by_component[key].append((line, deps))

        for file, line, component in use_state_rows:
            key = (file, component)
            if key not in effects_by_component:
                continue

            for effect_line, deps in effects_by_component[key]:
                if effect_line > line and effect_line < line + 10:
                    deps_str = str(deps) if deps else ""
                    if "props" in deps_str:
                        self.findings.append(
                            StandardFinding(
                                rule_name="react-derived-state",
                                message="Possible unnecessary derived state from props - consider computing during render instead",
                                file_path=file,
                                line=line,
                                severity=Severity.LOW,
                                category="react-state",
                                snippet="useState followed by useEffect with props dependency",
                                confidence=Confidence.LOW,
                                cwe_id="CWE-1066",
                            )
                        )
                        break

    def _check_anonymous_functions_in_props(self) -> None:
        """Check for anonymous functions passed as props to child components."""
        components = list(
            self.db.query(
                Q("react_components")
                .select("file", "name", "start_line", "end_line", "has_jsx")
                .where("has_jsx = ?", 1)
            )
        )

        component_ranges: dict[str, list[tuple]] = {}
        for file, name, start, end, _has_jsx in components:
            if file not in component_ranges:
                component_ranges[file] = []
            component_ranges[file].append((name, start or 0, end or 0))

        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "argument_expr", "callee_function")
            .where("argument_expr IS NOT NULL")
            .limit(500)
        )

        for file, line, args, callee in rows:
            if callee and callee.startswith("use"):
                continue

            args_str = str(args) if args else ""
            has_anonymous = "=>" in args_str or "function" in args_str

            if not has_anonymous or len(args_str) >= 50:
                continue

            component_name = None
            if file in component_ranges:
                for name, start, end in component_ranges[file]:
                    if start <= line <= end:
                        component_name = name
                        break

            if component_name:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-anonymous-prop",
                        message="Anonymous function in props causes child re-renders - extract to useCallback",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-performance",
                        snippet=f"Anonymous function in {component_name}",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1050",
                    )
                )

    def _check_excessive_renders(self) -> None:
        """Check for components that might render too often."""
        rows = self.db.query(Q("react_hooks").select("file", "component_name", "hook_name"))

        component_hooks: dict[tuple, dict] = {}
        for file, component, hook_name in rows:
            key = (file, component)
            if key not in component_hooks:
                component_hooks[key] = {"useState": 0, "useEffect": 0}
            if hook_name == "useState":
                component_hooks[key]["useState"] += 1
            elif hook_name == "useEffect":
                component_hooks[key]["useEffect"] += 1

        for (file, component), counts in component_hooks.items():
            states = counts["useState"]
            effects = counts["useEffect"]

            if states > 5 and effects > 3:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-excessive-renders",
                        message=f"Component with {states} states and {effects} effects may render excessively - consider consolidating state",
                        file_path=file,
                        line=1,
                        severity=Severity.MEDIUM,
                        category="react-performance",
                        snippet=f"{component}: {states} useState, {effects} useEffect",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1050",
                    )
                )

    def _check_style_objects(self) -> None:
        """Check for inline style objects that cause re-renders."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "argument_expr")
            .where("argument_expr IS NOT NULL")
            .limit(500)
        )

        for file, line, args in rows:
            args_str = str(args) if args else ""

            has_inline_style = "style={{" in args_str or "style={ {" in args_str

            if has_inline_style:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-inline-style",
                        message="Inline style object causes unnecessary re-renders - extract to constant or useMemo",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-performance",
                        snippet="style={{ ... }}",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1050",
                    )
                )


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect React rendering performance issues and anti-patterns.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        analyzer = ReactRenderAnalyzer(db)
        findings = analyzer.analyze()
        return RuleResult(findings=findings, manifest=db.get_manifest())
