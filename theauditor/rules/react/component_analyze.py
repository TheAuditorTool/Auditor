"""React Component Analyzer - Detects component anti-patterns and best practices violations.

Checks for:
- Large components (>300 lines)
- Multiple components per file (>3)
- Missing memoization for performance-sensitive components
- Inline components (defined inside other components)
- Missing display names for anonymous components
- Poor component naming (non-PascalCase, too short)
- Components that don't return JSX
- Excessive hooks usage (>10)
- Prop complexity (too many props)
- Mixed component hierarchy (pages mixed with components)
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

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
    name="react_component_issues",
    category="react",
    target_extensions=[".jsx", ".tsx", ".js", ".ts"],
    target_file_patterns=["frontend/", "client/", "src/components/", "app/"],
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
class ReactComponentPatterns:
    """Immutable pattern definitions for React component violations."""

    MAX_COMPONENT_LINES: int = 300
    MAX_COMPONENTS_PER_FILE: int = 3
    MAX_PROPS_COUNT: int = 10
    MAX_HOOKS_COUNT: int = 10

    MEMO_CANDIDATES: frozenset = frozenset(["list", "table", "grid", "card", "item", "row", "cell"])
    PERFORMANCE_PROPS: frozenset = frozenset(
        ["data", "items", "list", "rows", "options", "children"]
    )
    COMPONENT_SUFFIXES: frozenset = frozenset(
        [
            "Component",
            "Container",
            "Page",
            "View",
            "Modal",
            "Dialog",
            "Form",
            "List",
            "Table",
            "Card",
            "Button",
        ]
    )
    ANONYMOUS_PATTERNS: frozenset = frozenset(["anonymous", "arrow", "function", "_", "temp"])


class ReactComponentAnalyzer:
    """Analyzer for React component best practices and anti-patterns."""

    def __init__(self, db: RuleDB):
        """Initialize analyzer with database context."""
        self.db = db
        self.patterns = ReactComponentPatterns()
        self.findings: list[StandardFinding] = []
        self.components: list[dict[str, Any]] = []
        self.components_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.component_hooks: dict[tuple, set[str]] = {}
        self.component_dependencies: dict[tuple, set[str]] = {}

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        self._bootstrap_component_metadata()

        self._check_large_components()
        self._check_multiple_components_per_file()
        self._check_missing_memoization()
        self._check_inline_components()
        self._check_missing_display_names()
        self._check_component_naming()
        self._check_no_jsx_components()
        self._check_excessive_hooks()
        self._check_prop_complexity()
        self._check_component_hierarchy()

        return self.findings

    def _check_large_components(self) -> None:
        """Check for components that are too large."""
        rows = self.db.query(
            Q("react_components")
            .select("file", "name", "type", "start_line", "end_line")
            .where("(end_line - start_line) > ?", self.patterns.MAX_COMPONENT_LINES)
            .order_by("(end_line - start_line) DESC")
        )

        for file, name, _comp_type, start, end in rows:
            lines = end - start
            self.findings.append(
                StandardFinding(
                    rule_name="react-large-component",
                    message=f"Component {name} is too large ({lines} lines, max: {self.patterns.MAX_COMPONENT_LINES})",
                    file_path=file,
                    line=start,
                    severity=Severity.MEDIUM,
                    category="react-component",
                    snippet=f"{name}: {lines} lines",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1066",
                )
            )

    def _check_multiple_components_per_file(self) -> None:
        """Check for files with too many components."""
        for file_path, components in self.components_by_file.items():
            count = len(components)
            if count <= self.patterns.MAX_COMPONENTS_PER_FILE:
                continue

            comp_names = [c["name"] for c in components if c["name"]][:5]
            self.findings.append(
                StandardFinding(
                    rule_name="react-multiple-components",
                    message=f"File contains {count} components (max: {self.patterns.MAX_COMPONENTS_PER_FILE})",
                    file_path=file_path,
                    line=1,
                    severity=Severity.LOW,
                    category="react-component",
                    snippet=f"Components: {', '.join(comp_names)}{'...' if count > 5 else ''}",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1066",
                )
            )

    def _check_missing_memoization(self) -> None:
        """Check for components that should be memoized but aren't."""
        performance_tokens = set(self.patterns.PERFORMANCE_PROPS)
        memo_tokens = set(self.patterns.MEMO_CANDIDATES)

        for component in self.components:
            if component["type"] == "memo" or not component["has_jsx"]:
                continue

            name = component["name"] or ""
            if not name:
                continue

            basename = self._component_basename(name)
            normalized_basename = basename.lower()
            key = self._component_key(component["file"], name)

            hooks = self.component_hooks.get(key, set())
            dependency_tokens = self.component_dependencies.get(key, set())
            prop_tokens = self._extract_prop_tokens(component["props_type"])

            reason: str | None = None
            if hooks.intersection({"useCallback", "useMemo"}):
                reason = "uses optimization hooks"
            elif any(normalized_basename.endswith(token) for token in memo_tokens):
                reason = "renders list/table items"
            elif (dependency_tokens | prop_tokens).intersection(performance_tokens):
                reason = "receives data props"

            if reason:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-missing-memo",
                        message=f"Component {name} {reason} but is not memoized",
                        file_path=component["file"],
                        line=component["start_line"] or 1,
                        severity=Severity.LOW,
                        category="react-performance",
                        snippet=f"{component['type']} {name}",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1050",
                    )
                )

    def _check_inline_components(self) -> None:
        """Check for components defined inside other components.

        This is a performance anti-pattern - inline components are recreated
        on every render, losing state and causing unnecessary re-renders.
        """
        for file_path, components in self.components_by_file.items():
            if len(components) < 2:
                continue

            sorted_components = sorted(components, key=lambda c: c["start_line"] or 0)

            for i, outer in enumerate(sorted_components):
                outer_start = outer["start_line"] or 0
                outer_end = outer["end_line"] or 0
                if outer_end <= outer_start:
                    continue

                for inner in sorted_components[i + 1 :]:
                    inner_start = inner["start_line"] or 0
                    inner_end = inner["end_line"] or 0

                    if (
                        inner_start > outer_start
                        and inner_end < outer_end
                        and outer["name"] != inner["name"]
                    ):
                        self.findings.append(
                            StandardFinding(
                                rule_name="react-inline-component",
                                message=f"Component {inner['name']} is defined inside {outer['name']}",
                                file_path=file_path,
                                line=inner_start,
                                severity=Severity.HIGH,
                                category="react-component",
                                snippet=f"{inner['name']} inside {outer['name']}",
                                confidence=Confidence.HIGH,
                                cwe_id="CWE-1050",
                            )
                        )

    def _check_missing_display_names(self) -> None:
        """Check for anonymous components without display names."""
        for component in self.components:
            name = component["name"] or ""
            comp_type = component["type"]
            if not name:
                continue

            basename = self._component_basename(name)
            normalized = basename.lower()

            is_anonymous_type = comp_type in ("arrow", "anonymous")
            is_placeholder_name = normalized in {"anonymous", "_", "component"}

            if not (is_anonymous_type or is_placeholder_name):
                continue

            if "component" in normalized or "container" in normalized:
                continue

            if not self._has_meaningful_display_name(basename):
                self.findings.append(
                    StandardFinding(
                        rule_name="react-missing-display-name",
                        message=f"Component lacks meaningful display name: {name}",
                        file_path=component["file"],
                        line=component["start_line"] or 1,
                        severity=Severity.LOW,
                        category="react-component",
                        snippet=f"{comp_type} component: {name}",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1078",
                    )
                )

    def _check_component_naming(self) -> None:
        """Check for poor component naming conventions."""
        for component in self.components:
            name = component["name"]
            if not name:
                continue

            file = component["file"]
            line = component["start_line"] or 1

            if not name[0].isupper():
                self.findings.append(
                    StandardFinding(
                        rule_name="react-component-naming",
                        message=f"Component {name} should use PascalCase",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-component",
                        snippet=name,
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1078",
                    )
                )
            elif len(name) < 3:
                self.findings.append(
                    StandardFinding(
                        rule_name="react-component-naming",
                        message=f"Component name {name} is too short",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="react-component",
                        snippet=name,
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1078",
                    )
                )

    def _check_no_jsx_components(self) -> None:
        """Check for components that don't return JSX."""
        for component in self.components:
            if component["has_jsx"]:
                continue

            name = component["name"] or ""
            key = self._component_key(component["file"], name)
            hooks = self.component_hooks.get(key, set())

            if hooks:
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="react-no-jsx",
                    message=f"Component {name} does not appear to return JSX",
                    file_path=component["file"],
                    line=component["start_line"] or 1,
                    severity=Severity.MEDIUM,
                    category="react-component",
                    snippet=f"{name}: no JSX detected",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1066",
                )
            )

    def _check_excessive_hooks(self) -> None:
        """Check for components with too many hooks."""
        for key, hooks in self.component_hooks.items():
            file_path, component_name = key
            count = len(hooks)

            if count <= self.patterns.MAX_HOOKS_COUNT:
                continue

            hook_list = list(hooks)[:5]
            self.findings.append(
                StandardFinding(
                    rule_name="react-excessive-hooks",
                    message=f"Component {component_name} uses {count} hooks - consider refactoring",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="react-component",
                    snippet=f"Hooks: {', '.join(hook_list)}...",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1066",
                )
            )

    def _check_prop_complexity(self) -> None:
        """Check for components with too many props."""
        for component in self.components:
            props = component["props_type"]
            if not props or len(props) <= 200:
                continue

            prop_count = props.count(":")
            if prop_count <= self.patterns.MAX_PROPS_COUNT:
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="react-prop-complexity",
                    message=f"Component {component['name']} has ~{prop_count} props - too complex",
                    file_path=component["file"],
                    line=component["start_line"] or 1,
                    severity=Severity.LOW,
                    category="react-component",
                    snippet=f"{component['name']}: ~{prop_count} props",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1066",
                )
            )

    def _check_component_hierarchy(self) -> None:
        """Check for potential component hierarchy issues."""
        for file_path, components in self.components_by_file.items():
            total = len(components)
            if total <= 2:
                continue

            containers = 0
            components_count = 0
            pages = 0

            for component in components:
                basename = self._component_basename(component["name"]).lower()
                if basename.endswith("container"):
                    containers += 1
                elif basename.endswith("component"):
                    components_count += 1
                elif basename.endswith("page"):
                    pages += 1

            if pages > 0 and components_count > 0:
                first_line = min((comp["start_line"] or 1) for comp in components)
                self.findings.append(
                    StandardFinding(
                        rule_name="react-mixed-hierarchy",
                        message="File mixes page-level and component-level React components",
                        file_path=file_path,
                        line=first_line,
                        severity=Severity.LOW,
                        category="react-component",
                        snippet=f"Pages: {pages}, Components: {components_count}, Containers: {containers}",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1066",
                    )
                )

    def _bootstrap_component_metadata(self) -> None:
        """Load component-level metadata and relationship tables once."""
        rows = self.db.query(
            Q("react_components").select(
                "file", "name", "type", "start_line", "end_line", "has_jsx", "props_type"
            )
        )

        for file, name, comp_type, start_line, end_line, has_jsx, props_type in rows:
            component = {
                "file": file,
                "name": name,
                "type": comp_type,
                "start_line": start_line,
                "end_line": end_line,
                "has_jsx": bool(has_jsx),
                "props_type": props_type,
            }
            self.components.append(component)
            self.components_by_file[file].append(component)

        self.component_hooks = self._load_component_hooks()
        self.component_dependencies = self._load_component_dependencies()

    def _load_component_hooks(self) -> dict[tuple, set[str]]:
        """Return mapping of components to hooks used."""
        hooks: dict[tuple, set[str]] = defaultdict(set)
        rows = self.db.query(
            Q("react_component_hooks").select("component_file", "component_name", "hook_name")
        )
        for component_file, component_name, hook_name in rows:
            key = self._component_key(component_file, component_name)
            hooks[key].add(hook_name)
        return hooks

    def _load_component_dependencies(self) -> dict[tuple, set[str]]:
        """Return mapping of components to dependency tokens."""
        dependencies: dict[tuple, set[str]] = defaultdict(set)
        rows = self.db.query(
            Q("react_hook_dependencies").select("hook_file", "hook_component", "dependency_name")
        )
        for hook_file, hook_component, dependency_name in rows:
            normalized = self._normalize_dependency_name(dependency_name)
            if not normalized:
                continue
            key = self._component_key(hook_file, hook_component)
            dependencies[key].add(normalized)
        return dependencies

    @staticmethod
    def _component_key(file_path: str, name: str | None) -> tuple:
        return (file_path, name or "")

    @staticmethod
    def _component_basename(name: str | None) -> str:
        if not name:
            return ""
        return name.split(".")[-1]

    @staticmethod
    def _normalize_dependency_name(name: str | None) -> str | None:
        if not name:
            return None
        token = name.split(".")[-1].strip()
        return token.lower() if token else None

    @staticmethod
    def _extract_prop_tokens(props: str | None) -> set[str]:
        if not props:
            return set()
        tokens: set[str] = set()
        current: list[str] = []
        for char in props:
            if char.isalpha():
                current.append(char.lower())
            else:
                if current:
                    tokens.add("".join(current))
                    current = []
        if current:
            tokens.add("".join(current))
        return tokens

    def _has_meaningful_display_name(self, name: str) -> bool:
        lowered = name.lower()
        if lowered in self.patterns.ANONYMOUS_PATTERNS:
            return False
        if any(lowered.endswith(suffix.lower()) for suffix in self.patterns.COMPONENT_SUFFIXES):
            return True
        return len(name) >= 3 and any(char.isalpha() for char in name)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect React component anti-patterns and best practices violations.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        analyzer = ReactComponentAnalyzer(db)
        findings = analyzer.analyze()
        return RuleResult(findings=findings, manifest=db.get_manifest())
