"""React Hooks Analyzer - Detects hooks violations and anti-patterns.

Checks for:
- Missing dependencies in useEffect/useCallback/useMemo
- Memory leaks from missing cleanup functions
- Conditional hooks (called inside conditions/loops)
- Empty dependency arrays with used variables
- Async functions passed directly to useEffect
- Stale closure issues
- Inconsistent cleanup patterns
- Incorrect hook ordering
- Custom hook naming violations
- Potential race conditions in effects
"""

import json
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
    name="react_hooks_issues",
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
class ReactHooksPatterns:
    """Immutable pattern definitions for React hooks violations."""

    HOOKS_WITH_DEPS: frozenset = frozenset(
        ["useEffect", "useCallback", "useMemo", "useLayoutEffect", "useImperativeHandle"]
    )

    HOOKS_WITHOUT_DEPS: frozenset = frozenset(
        [
            "useState",
            "useReducer",
            "useRef",
            "useContext",
            "useId",
            "useDebugValue",
            "use",
            "useActionState",
            "useOptimistic",
            "useFormStatus",
        ]
    )

    CLEANUP_REQUIRED: frozenset = frozenset(
        [
            "addEventListener",
            "setInterval",
            "setTimeout",
            "requestAnimationFrame",
            "subscribe",
            "on",
            "addListener",
            "observe",
            "observeIntersection",
            "WebSocket",
            "EventSource",
            "MutationObserver",
            "ResizeObserver",
        ]
    )

    CLEANUP_FUNCTIONS: frozenset = frozenset(
        [
            "removeEventListener",
            "clearInterval",
            "clearTimeout",
            "cancelAnimationFrame",
            "unsubscribe",
            "off",
            "removeListener",
            "disconnect",
            "close",
            "abort",
        ]
    )

    TOP_LEVEL_HOOKS: frozenset = frozenset(
        [
            "useState",
            "useEffect",
            "useContext",
            "useReducer",
            "useCallback",
            "useMemo",
            "useRef",
            "useLayoutEffect",
            "useImperativeHandle",
            "useDebugValue",
        ]
    )

    BUILTIN_HOOKS: frozenset = frozenset(
        [
            "useState",
            "useEffect",
            "useContext",
            "useReducer",
            "useCallback",
            "useMemo",
            "useRef",
            "useLayoutEffect",
            "useImperativeHandle",
            "useDebugValue",
            "useId",
            "useTransition",
            "useDeferredValue",
            "useSyncExternalStore",
            "use",
            "useActionState",
            "useOptimistic",
            "useFormStatus",
        ]
    )

    GLOBAL_VARS: frozenset = frozenset(
        [
            "console",
            "window",
            "document",
            "Math",
            "JSON",
            "Object",
            "Array",
            "undefined",
            "null",
            "Promise",
            "Error",
            "Date",
        ]
    )


class ReactHooksAnalyzer:
    """Analyzer for React hooks violations and best practices."""

    def __init__(self, db: RuleDB):
        """Initialize analyzer with database context."""
        self.db = db
        self.patterns = ReactHooksPatterns()
        self.findings: list[StandardFinding] = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        self._check_missing_dependencies()
        self._check_memory_leaks()
        self._check_conditional_hooks()
        self._check_exhaustive_deps()
        self._check_async_useeffect()
        self._check_stale_closures()
        self._check_cleanup_consistency()
        self._check_hook_order()
        self._check_custom_hook_naming()
        self._check_effect_race_conditions()

        return self.findings

    def _check_missing_dependencies(self) -> None:
        """Check for missing dependencies in hooks."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "hook_name", "component_name", "dependency_array")
            .where("hook_name IN (?, ?, ?)", "useEffect", "useCallback", "useMemo")
            .where("dependency_array IS NOT NULL")
        )

        for file, line, hook_name, component, deps_array_json in rows:
            try:
                declared_deps = json.loads(deps_array_json) if deps_array_json else []
            except json.JSONDecodeError:
                continue

            if declared_deps == []:
                continue

            dep_rows = self.db.query(
                Q("react_hook_dependencies")
                .select("dependency_name")
                .where("hook_file = ?", file)
                .where("hook_line = ?", line)
                .where("hook_component = ?", component)
            )

            used_vars = [r[0] for r in dep_rows if r[0]]
            missing = []

            for var in used_vars:
                var_clean = var.split(".")[0] if "." in var else var
                if (
                    var_clean
                    and var_clean not in declared_deps
                    and var_clean not in self.patterns.GLOBAL_VARS
                ):
                    missing.append(var_clean)

            if missing:
                unique_missing = list(dict.fromkeys(missing))[:5]
                self.findings.append(
                    StandardFinding(
                        rule_name="react-missing-dependency",
                        message=f"{hook_name} is missing dependencies: {', '.join(unique_missing)}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="react-hooks",
                        snippet=f"{hook_name}(..., [{', '.join(declared_deps[:3])}])",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-670",
                    )
                )

    def _check_memory_leaks(self) -> None:
        """Check for potential memory leaks from missing cleanup."""
        rows = self.db.query(
            Q("react_hooks")
            .select(
                "file",
                "line",
                "hook_name",
                "component_name",
                "callback_body",
                "has_cleanup",
                "cleanup_type",
            )
            .where("hook_name = ?", "useEffect")
            .where("callback_body IS NOT NULL")
        )

        for file, line, _hook, _component, callback, has_cleanup, _cleanup_type in rows:
            needs_cleanup = False
            subscription_type = None

            for pattern in self.patterns.CLEANUP_REQUIRED:
                if pattern in callback:
                    needs_cleanup = True
                    subscription_type = pattern
                    break

            if needs_cleanup and not has_cleanup:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-memory-leak",
                        message=f"useEffect with {subscription_type} is missing cleanup function",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="react-hooks",
                        snippet=f"useEffect with {subscription_type}",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-401",
                    )
                )

    def _check_conditional_hooks(self) -> None:
        """Check for hooks called conditionally (inside conditions/loops)."""
        hooks_rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "hook_name", "component_name")
            .where(
                "hook_name IN (?, ?, ?, ?, ?, ?, ?)",
                "useState",
                "useEffect",
                "useContext",
                "useReducer",
                "useCallback",
                "useMemo",
                "useRef",
            )
        )

        hooks_by_file: dict[str, list[tuple]] = {}
        for file, line, hook_name, component_name in hooks_rows:
            if file not in hooks_by_file:
                hooks_by_file[file] = []
            hooks_by_file[file].append((line, hook_name, component_name))

        for file, hooks in hooks_by_file.items():
            cfg_rows = self.db.query(
                Q("cfg_blocks")
                .select("block_type", "start_line", "end_line", "condition_expr")
                .where("file = ?", file)
                .where("block_type IN (?, ?)", "condition", "loop")
            )

            blocks = list(cfg_rows)
            for hook_line, hook_name, _component_name in hooks:
                for block_type, start_line, end_line, _condition_expr in blocks:
                    if start_line <= hook_line <= end_line:
                        self.findings.append(
                            StandardFinding(
                                rule_name="react-conditional-hook",
                                message=f"{hook_name} is called inside a {block_type} block",
                                file_path=file,
                                line=hook_line,
                                severity=Severity.CRITICAL,
                                category="react-hooks",
                                snippet=f"{hook_name} inside {block_type}",
                                confidence=Confidence.HIGH,
                                cwe_id="CWE-670",
                            )
                        )
                        break

    def _check_exhaustive_deps(self) -> None:
        """Check for effects with empty dependencies that should have some."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "hook_name", "component_name", "callback_body")
            .where("hook_name IN (?, ?, ?)", "useEffect", "useCallback", "useMemo")
            .where("dependency_array = ?", "[]")
        )

        for file, line, hook_name, component, _callback in rows:
            dep_rows = self.db.query(
                Q("react_hook_dependencies")
                .select("dependency_name")
                .where("hook_file = ?", file)
                .where("hook_line = ?", line)
                .where("hook_component = ?", component)
            )

            used_vars = [r[0] for r in dep_rows if r[0] and r[0] not in self.patterns.GLOBAL_VARS]

            if used_vars:
                unique_vars = list(dict.fromkeys(used_vars))[:3]
                self.findings.append(
                    StandardFinding(
                        rule_name="react-exhaustive-deps",
                        message=f"{hook_name} has empty dependency array but uses: {', '.join(unique_vars)}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="react-hooks",
                        snippet=f"{hook_name}(..., [])",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-670",
                    )
                )

    def _check_async_useeffect(self) -> None:
        """Check for async functions passed directly to useEffect."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "component_name", "callback_body")
            .where("hook_name = ?", "useEffect")
            .where("callback_body IS NOT NULL")
        )

        for file, line, _component, callback in rows:
            if callback and callback.strip().startswith("async"):
                self.findings.append(
                    StandardFinding(
                        rule_name="react-async-useeffect",
                        message="useEffect cannot accept async functions directly - wrap in IIFE or use inner async function",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="react-hooks",
                        snippet="useEffect(async () => {...})",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-670",
                    )
                )

    def _check_stale_closures(self) -> None:
        """Check for potential stale closure issues."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "line", "hook_name", "component_name", "callback_body")
            .where("hook_name = ?", "useCallback")
            .where("dependency_array = ?", "[]")
            .where("callback_body IS NOT NULL")
        )

        for file, line, _hook, _component, callback in rows:
            if "setState" in callback or "set" in callback.lower():
                self.findings.append(
                    StandardFinding(
                        rule_name="react-stale-closure",
                        message="useCallback with setState and empty deps may cause stale closures",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="react-hooks",
                        snippet="useCallback with setState and []",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-367",
                    )
                )

    def _check_cleanup_consistency(self) -> None:
        """Check for inconsistent cleanup patterns within components."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "component_name", "has_cleanup")
            .where("hook_name = ?", "useEffect")
        )

        component_effects: dict[tuple, dict] = {}
        for file, component, has_cleanup in rows:
            key = (file, component)
            if key not in component_effects:
                component_effects[key] = {"total": 0, "with_cleanup": 0}
            component_effects[key]["total"] += 1
            if has_cleanup:
                component_effects[key]["with_cleanup"] += 1

        for (file, component), stats in component_effects.items():
            total = stats["total"]
            with_cleanup = stats["with_cleanup"]
            if total > 1 and with_cleanup > 0 and with_cleanup < total:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-inconsistent-cleanup",
                        message=f"Component has {with_cleanup}/{total} effects with cleanup - inconsistent pattern",
                        file_path=file,
                        line=1,
                        severity=Severity.LOW,
                        category="react-hooks",
                        snippet=f"{component}: mixed cleanup pattern",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-398",
                    )
                )

    def _check_hook_order(self) -> None:
        """Check for hooks called in incorrect order (state hooks after effects)."""
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "component_name", "hook_name", "line")
            .order_by("file, component_name, line")
        )

        current_key: tuple | None = None
        hooks_order: list[tuple] = []

        for file, component, hook, line in rows:
            key = (file, component)

            if key != current_key:
                if hooks_order and current_key:
                    self._check_order_issue(current_key[0], current_key[1], hooks_order)
                current_key = key
                hooks_order = []

            hooks_order.append((hook, line))

        if hooks_order and current_key:
            self._check_order_issue(current_key[0], current_key[1], hooks_order)

    def _check_order_issue(self, file: str, component: str, hooks: list[tuple]) -> None:
        """Check if hooks have ordering issues."""
        effect_seen = False
        for hook, line in hooks:
            if hook in ("useState", "useReducer", "useRef"):
                if effect_seen:
                    self.findings.append(
                        StandardFinding(
                            rule_name="react-hooks-order",
                            message=f"State hook {hook} called after effect hooks in {component}",
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category="react-hooks",
                            snippet=f"{hook} after useEffect",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-670",
                        )
                    )
                    return
            elif hook in ("useEffect", "useLayoutEffect"):
                effect_seen = True

    def _check_custom_hook_naming(self) -> None:
        """Check custom hooks for naming violations."""
        rows = self.db.query(Q("react_hooks").select("file", "hook_name", "component_name", "line"))

        seen: set[tuple] = set()
        for file, hook, _component, line in rows:
            if not hook or not hook.startswith("use"):
                continue

            if hook in self.patterns.BUILTIN_HOOKS:
                continue

            key = (file, hook, line)
            if key in seen:
                continue
            seen.add(key)

            if len(hook) > 3 and hook[3].islower():
                self.findings.append(
                    StandardFinding(
                        rule_name="react-custom-hook-naming",
                        message=f'Custom hook {hook} should use PascalCase after "use" (e.g., useMyHook)',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-hooks",
                        snippet=f"{hook}()",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1078",
                    )
                )

    def _check_effect_race_conditions(self) -> None:
        """Check for potential race conditions in effects.

        Only flags effects that lack cleanup functions - proper cleanup
        (AbortController, cancelled flag) prevents race conditions.
        """
        rows = self.db.query(
            Q("react_hooks")
            .select("file", "component_name", "dependency_array", "has_cleanup")
            .where("hook_name = ?", "useEffect")
            .where("dependency_array IS NOT NULL")
        )

        component_effects: dict[tuple, list[tuple[str, bool]]] = {}
        for file, component, deps_array, has_cleanup in rows:
            key = (file, component)
            if key not in component_effects:
                component_effects[key] = []
            component_effects[key].append((deps_array or "", bool(has_cleanup)))

        for (file, component), effects in component_effects.items():
            if len(effects) <= 2:
                continue

            unsafe_id_effects = sum(
                1
                for deps, has_cleanup in effects
                if not has_cleanup and ("[id]" in deps or '["id"]' in deps or "id" in deps)
            )

            if unsafe_id_effects > 1:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-effect-race",
                        message=f"Component has {unsafe_id_effects} effects with ID deps lacking cleanup - use AbortController or cancelled flag",
                        file_path=file,
                        line=1,
                        severity=Severity.MEDIUM,
                        category="react-hooks",
                        snippet=f"{component}: {unsafe_id_effects} useEffect calls without cleanup",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-362",
                    )
                )


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect React hooks violations and anti-patterns.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        analyzer = ReactHooksAnalyzer(db)
        findings = analyzer.analyze()
        return RuleResult(findings=findings, manifest=db.get_manifest())
