"""React State Analyzer - Detects state management issues and anti-patterns.

Checks for:
- Excessive useState hooks per component
- Missing useReducer for complex state
- Poor state variable naming
- Multiple state updates in single function
- Prop drilling patterns
- Global state candidates
- Unnecessary derived state
- Expensive state initialization
- Complex state objects
- Unbatched state updates
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
    name="react_state_issues",
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
    primary_table="react_hooks",
)


@dataclass(frozen=True)
class ReactStatePatterns:
    """Immutable pattern definitions for React state management."""

    MAX_USESTATE_PER_COMPONENT: int = 7
    MAX_STATE_UPDATES_PER_FUNCTION: int = 3
    REDUCER_THRESHOLD: int = 5

    STATE_PREFIXES: frozenset = frozenset(["is", "has", "should", "can", "will", "did"])

    COMMON_STATE: frozenset = frozenset(
        [
            "loading",
            "error",
            "data",
            "isLoading",
            "isError",
            "isOpen",
            "isVisible",
            "isActive",
            "isDisabled",
        ]
    )

    CONTEXT_PATTERNS: frozenset = frozenset(
        [
            "context",
            "store",
            "provider",
            "global",
            "app",
            "theme",
            "auth",
            "user",
            "session",
            "config",
        ]
    )

    DRILL_PROPS: frozenset = frozenset(
        [
            "user",
            "auth",
            "theme",
            "config",
            "settings",
            "data",
            "state",
            "dispatch",
            "actions",
        ]
    )

    EXPENSIVE_INIT_PATTERNS: frozenset = frozenset(
        [
            "fetch",
            "localStorage",
            "sessionStorage",
            "JSON.parse",
            "indexedDB",
            "WebSocket",
            "new XMLHttpRequest",
        ]
    )


class ReactStateAnalyzer:
    """Analyzer for React state management patterns and issues."""

    def __init__(self, db: RuleDB):
        """Initialize analyzer with database context."""
        self.db = db
        self.patterns = ReactStatePatterns()
        self.findings: list[StandardFinding] = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        self._check_excessive_usestate()
        self._check_missing_usereducer()
        self._check_state_naming()
        self._check_multiple_state_updates()
        self._check_prop_drilling()
        self._check_global_state_candidates()
        self._check_unnecessary_state()
        self._check_state_initialization()
        self._check_complex_state_objects()
        self._check_state_batching()

        return self.findings

    def _check_excessive_usestate(self) -> None:
        """Check for components with too many useState hooks."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "component_name", "hook_name")
            .where("hook_name = ?", "useState")
        )

        component_counts: dict[tuple, int] = {}
        for file, component, _hook_name in rows:
            key = (file, component)
            component_counts[key] = component_counts.get(key, 0) + 1

        for (file, component), count in component_counts.items():
            if count > self.patterns.MAX_USESTATE_PER_COMPONENT:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-excessive-state",
                        message=f"Component {component} has {count} useState hooks (max: {self.patterns.MAX_USESTATE_PER_COMPONENT})",
                        file_path=file,
                        line=1,
                        severity=Severity.MEDIUM,
                        category="react-state",
                        snippet=f"{count} useState calls - consider useReducer or splitting component",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1066",
                    )
                )

    def _check_missing_usereducer(self) -> None:
        """Check for components that should use useReducer instead of multiple useState."""
        rows = self.db.query(Q("react_hooks").select("file", "component_name", "hook_name"))

        component_hooks: dict[tuple, dict] = {}
        for file, component, hook_name in rows:
            key = (file, component)
            if key not in component_hooks:
                component_hooks[key] = {"useState": 0, "useReducer": 0}
            if hook_name == "useState":
                component_hooks[key]["useState"] += 1
            elif hook_name == "useReducer":
                component_hooks[key]["useReducer"] += 1

        for (file, component), counts in component_hooks.items():
            if counts["useState"] >= self.patterns.REDUCER_THRESHOLD and counts["useReducer"] == 0:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-missing-reducer",
                        message=f"Component with {counts['useState']} useState hooks should consider useReducer",
                        file_path=file,
                        line=1,
                        severity=Severity.LOW,
                        category="react-state",
                        snippet=f"{component}: {counts['useState']} useState hooks",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1066",
                    )
                )

    def _check_state_naming(self) -> None:
        """Check for poor state variable naming conventions."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("source_expr IS NOT NULL")
            .where("target_var IS NOT NULL")
            .limit(500)
        )

        for file, line, var_name, source in rows:
            if not var_name or not source:
                continue

            source_str = str(source)
            if "useState" not in source_str:
                continue

            source_lower = source_str.lower()
            is_boolean_state = "true" in source_lower or "false" in source_lower

            if is_boolean_state and not any(
                var_name.startswith(prefix) for prefix in self.patterns.STATE_PREFIXES
            ):
                self.findings.append(
                    StandardFinding(
                        rule_name="react-state-naming",
                        message=f"Boolean state '{var_name}' should use is/has/should/can/will/did prefix",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-state",
                        snippet=f"const [{var_name}, ...] = useState",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1078",
                    )
                )

    def _check_multiple_state_updates(self) -> None:
        """Check for multiple state updates in single function."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "caller_function", "callee_function")
            .where("callee_function IS NOT NULL")
            .where("caller_function IS NOT NULL")
            .where("caller_function != ?", "global")
            .limit(1000)
        )

        updates_by_function: dict[tuple, list[str]] = {}
        for file, caller, callee in rows:
            if not callee or not callee.startswith("set"):
                continue

            key = (file, caller)
            if key not in updates_by_function:
                updates_by_function[key] = []
            updates_by_function[key].append(callee)

        for (file, function), setters in updates_by_function.items():
            count = len(setters)
            if count > self.patterns.MAX_STATE_UPDATES_PER_FUNCTION:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-multiple-updates",
                        message=f"Function '{function}' updates state {count} times - consider batching or useReducer",
                        file_path=file,
                        line=1,
                        severity=Severity.LOW,
                        category="react-state",
                        snippet=f"{count} setState calls: {', '.join(setters[:3])}...",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1050",
                    )
                )

    def _check_prop_drilling(self) -> None:
        """Check for potential prop drilling patterns."""
        rows = self.db.query(
            Q("react_components")
            .select("file", "name", "props_type")
            .where("props_type IS NOT NULL")
        )

        prop_usage: dict[tuple, set] = {}
        for file, component, props_type in rows:
            props_str = str(props_type) if props_type else ""
            for prop in self.patterns.DRILL_PROPS:
                if prop in props_str.lower():
                    key = (file, prop)
                    if key not in prop_usage:
                        prop_usage[key] = set()
                    prop_usage[key].add(component)

        for (file, prop), components in prop_usage.items():
            count = len(components)
            if count > 2:
                comp_list = list(components)[:3]
                self.findings.append(
                    StandardFinding(
                        rule_name="react-prop-drilling",
                        message=f"Prop '{prop}' passed through {count} components - consider Context or state management",
                        file_path=file,
                        line=1,
                        severity=Severity.LOW,
                        category="react-state",
                        snippet=f"Components: {', '.join(comp_list)}{'...' if count > 3 else ''}",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1066",
                    )
                )

    def _check_global_state_candidates(self) -> None:
        """Check for state that should be global/context."""
        rows = self.db.query(
            Q("variable_usage")
            .select("variable_name", "in_component")
            .where("variable_name IS NOT NULL")
            .where("in_component != ?", "")
            .limit(1000)
        )

        var_usage: dict[str, set] = {}
        for var_name, component in rows:
            if not var_name:
                continue

            for pattern in self.patterns.CONTEXT_PATTERNS:
                if pattern in var_name.lower():
                    if var_name not in var_usage:
                        var_usage[var_name] = set()
                    var_usage[var_name].add(component)
                    break

        for var, components in var_usage.items():
            count = len(components)
            if count > 3:
                comp_list = list(components)[:3]
                self.findings.append(
                    StandardFinding(
                        rule_name="react-global-state",
                        message=f"Variable '{var}' used in {count} components - candidate for Context or global state",
                        file_path="",
                        line=1,
                        severity=Severity.LOW,
                        category="react-state",
                        snippet=f"Used in: {', '.join(comp_list)}...",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1066",
                    )
                )

    def _check_unnecessary_state(self) -> None:
        """Check for state that could be derived or computed."""
        use_state_rows = list(
            self.db.query(
                Q("react_hooks")
                .select("file", "line", "component_name")
                .where("hook_name = ?", "useState")
                .limit(200)
            )
        )

        use_effect_rows = list(
            self.db.query(
                Q("react_hooks")
                .select("file", "line", "component_name", "dependency_array")
                .where("hook_name = ?", "useEffect")
                .where("dependency_array IS NOT NULL")
                .where("dependency_array != ?", "[]")
                .limit(200)
            )
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

            for effect_line, _deps in effects_by_component[key]:
                if effect_line > line and effect_line < line + 5:
                    self.findings.append(
                        StandardFinding(
                            rule_name="react-unnecessary-state",
                            message="State immediately updated in useEffect - may be unnecessary derived state",
                            file_path=file,
                            line=line,
                            severity=Severity.LOW,
                            category="react-state",
                            snippet="useState followed by immediate useEffect update",
                            confidence=Confidence.LOW,
                            cwe_id="CWE-1066",
                        )
                    )
                    break

    def _check_state_initialization(self) -> None:
        """Check for expensive state initialization."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "hook_name", "callback_body")
            .where("hook_name = ?", "useState")
            .where("callback_body IS NOT NULL")
            .limit(200)
        )

        for file, line, _hook, callback in rows:
            if not callback or len(callback) <= 50:
                continue

            callback_str = str(callback)
            for pattern in self.patterns.EXPENSIVE_INIT_PATTERNS:
                if pattern in callback_str:
                    self.findings.append(
                        StandardFinding(
                            rule_name="react-expensive-init",
                            message=f"Expensive operation ({pattern}) in useState initialization - use lazy initializer",
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category="react-state",
                            snippet=f"useState with {pattern}",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-1050",
                        )
                    )
                    break

    def _check_complex_state_objects(self) -> None:
        """Check for overly complex state objects."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "component_name", "callback_body")
            .where("hook_name = ?", "useState")
            .where("callback_body IS NOT NULL")
            .limit(200)
        )

        for file, line, _component, callback in rows:
            callback_str = str(callback) if callback else ""

            if "{" not in callback_str or len(callback_str) <= 200:
                continue

            prop_count = callback_str.count(":")
            if prop_count > 5:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-complex-state",
                        message=f"Complex state object with ~{prop_count} properties - consider splitting or using useReducer",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-state",
                        snippet=f"useState with {prop_count}+ nested properties",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1066",
                    )
                )

    def _check_state_batching(self) -> None:
        """Check for consecutive state updates that should be batched."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "caller_function")
            .where("callee_function IS NOT NULL")
            .where("caller_function IS NOT NULL")
            .limit(1000)
        )

        calls_by_location: dict[str, dict[tuple, list[str]]] = {}
        for file, line, callee, caller in rows:
            if not callee or not callee.startswith("set"):
                continue

            if file not in calls_by_location:
                calls_by_location[file] = {}

            line_key = (line, caller)
            if line_key not in calls_by_location[file]:
                calls_by_location[file][line_key] = []
            calls_by_location[file][line_key].append(callee)

        for file, line_data in calls_by_location.items():
            sorted_lines = sorted(line_data.keys())
            for i in range(len(sorted_lines) - 1):
                (line1, caller1) = sorted_lines[i]
                (line2, caller2) = sorted_lines[i + 1]

                if line2 == line1 + 1 and caller1 == caller2:
                    setter1 = line_data[(line1, caller1)][0]
                    setter2 = line_data[(line2, caller2)][0]

                    self.findings.append(
                        StandardFinding(
                            rule_name="react-unbatched-updates",
                            message=f"Consecutive state updates ({setter1}, {setter2}) - React 18+ batches automatically, consider useReducer for related state",
                            file_path=file,
                            line=line1,
                            severity=Severity.INFO,
                            category="react-state",
                            snippet=f"{setter1}(); {setter2}()",
                            confidence=Confidence.LOW,
                            cwe_id="CWE-1050",
                        )
                    )


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect React state management issues and anti-patterns.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        analyzer = ReactStateAnalyzer(db)
        findings = analyzer.analyze()
        return RuleResult(findings=findings, manifest=db.get_manifest())
