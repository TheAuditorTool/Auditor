"""Vue Component Analyzer - Fidelity Layer Implementation.

Detects Vue component anti-patterns, performance issues, and maintainability problems:
- Props mutations (immutability violations)
- Missing v-for keys (reconciliation performance)
- Complex components (maintainability)
- Unnecessary re-renders ($forceUpdate abuse)
- Missing component names (debugging difficulty)
- Inefficient computed properties
- Complex template expressions
"""

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
    name="vue_component",
    category="vue",
    target_extensions=[".vue", ".js", ".ts", ".jsx", ".tsx"],
    target_file_patterns=[
        "frontend/",
        "client/",
        "src/components/",
        "src/views/",
        "src/pages/",
    ],
    exclude_patterns=[
        "backend/",
        "server/",
        "api/",
        "migrations/",
        "__tests__/",
        "*.test.*",
        "*.spec.*",
    ],
    execution_scope="database",
    primary_table="vue_components",
)


IMMUTABLE_PROPS = frozenset(
    [
        "props.",
        "this.props.",
        "this.$props.",
        "prop.",
        "parentProp.",
        "inheritedProp.",
    ]
)


RENDER_TRIGGERS = frozenset(
    [
        "$forceUpdate",
        "forceUpdate",
        "$set",
        "$delete",
        "Vue.set",
        "Vue.delete",
        "this.$nextTick",
    ]
)


EXPENSIVE_TEMPLATE_OPS = frozenset(
    [
        "JSON.stringify",
        "JSON.parse",
        "Object.keys",
        "Object.values",
        "Array.from",
        ".filter",
        ".map",
        ".reduce",
        ".sort",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue component anti-patterns and performance issues."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        vue_files = _get_vue_files(db)
        if not vue_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_find_props_mutations(db, vue_files))
        findings.extend(_find_missing_vfor_keys(db, vue_files))
        findings.extend(_find_complex_components(db, vue_files))
        findings.extend(_find_unnecessary_rerenders(db, vue_files))
        findings.extend(_find_missing_component_names(db, vue_files))
        findings.extend(_find_inefficient_computed(db, vue_files))
        findings.extend(_find_complex_template_expressions(db, vue_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_vue_files(db: RuleDB) -> set[str]:
    """Get all Vue-related files from the database."""
    vue_files: set[str] = set()

    rows = db.query(Q("vue_components").select("file"))
    vue_files.update(row[0] for row in rows)

    rows = db.query(Q("files").select("path").where("ext = ?", ".vue"))
    vue_files.update(row[0] for row in rows)

    rows = db.query(Q("symbols").select("path", "name").where("name IS NOT NULL"))

    vue_patterns = ("Vue", "defineComponent", "createApp")
    for path, name in rows:
        if name and any(pattern in name for pattern in vue_patterns):
            vue_files.add(path)

    return vue_files


def _find_props_mutations(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find direct props mutations (anti-pattern in Vue).

    Props should be immutable. Mutating them breaks one-way data flow
    and can cause subtle bugs with component re-rendering.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, target, source in rows:
        if file not in vue_files:
            continue

        if any(pattern in target for pattern in IMMUTABLE_PROPS):
            findings.append(
                StandardFinding(
                    rule_name="vue-props-mutation",
                    message=f"Direct mutation of prop '{target}' - props should be immutable",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="vue-antipattern",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-471",
                    snippet=f"{target} = {source[:50] if source else '...'}",
                )
            )

    return findings


def _find_missing_vfor_keys(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find v-for loops without :key attribute.

    Missing keys cause Vue to use an inefficient in-place patch strategy
    instead of reordering elements, leading to bugs with stateful components.
    """
    findings = []
    found_locations: set[tuple[str, int]] = set()

    if not vue_files:
        return findings

    rows = db.query(
        Q("vue_directives")
        .select("file", "line", "expression")
        .where("directive_name = ?", "v-for")
        .where("has_key = ?", 0)
        .order_by("file, line")
    )

    for file, line, expression in rows:
        if file not in vue_files:
            continue

        location = (file, line)
        if location not in found_locations:
            found_locations.add(location)
            findings.append(
                StandardFinding(
                    rule_name="vue-missing-vfor-key",
                    message=f"v-for directive without :key attribute: '{expression}'",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="vue-performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1050",
                    snippet=f'v-for="{expression}"',
                )
            )

    return findings


def _find_complex_components(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find components with excessive complexity.

    Components with too many methods or data properties are hard to maintain
    and should be split into smaller, focused components.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("symbols").select("path", "name").where("type = ?", "function").where("name IS NOT NULL")
    )

    file_methods: dict[str, set[str]] = {}
    for path, name in rows:
        if path not in vue_files:
            continue

        if name.startswith("on") or name.startswith("handle"):
            continue
        if path not in file_methods:
            file_methods[path] = set()
        file_methods[path].add(name)

    for file, methods in file_methods.items():
        method_count = len(methods)
        if method_count > 15:
            findings.append(
                StandardFinding(
                    rule_name="vue-complex-component",
                    message=f"Component has {method_count} methods - consider splitting into smaller components",
                    file_path=file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="vue-maintainability",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-1061",
                )
            )

    rows = db.query(
        Q("symbols")
        .select("path", "name")
        .where("type IN (?, ?)", "property", "variable")
        .where("name IS NOT NULL")
    )

    file_data: dict[str, int] = {}
    for path, name in rows:
        if path not in vue_files:
            continue
        if name.startswith("data.") or name.startswith("state."):
            file_data[path] = file_data.get(path, 0) + 1

    for file, data_count in file_data.items():
        if data_count > 20:
            findings.append(
                StandardFinding(
                    rule_name="vue-excessive-data",
                    message=f"Component has {data_count} data properties - consider using composition API or splitting",
                    file_path=file,
                    line=1,
                    severity=Severity.LOW,
                    category="vue-maintainability",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1061",
                )
            )

    return findings


def _find_unnecessary_rerenders(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find unnecessary re-render triggers.

    $forceUpdate and manual Vue.set/delete calls often indicate
    reactivity issues that should be fixed at the source.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, _args in rows:
        if file not in vue_files:
            continue

        if func not in RENDER_TRIGGERS:
            continue

        if func in ("$forceUpdate", "forceUpdate"):
            severity = Severity.HIGH
            message = "Using $forceUpdate - indicates reactivity issue that should be fixed"
        else:
            severity = Severity.MEDIUM
            message = f"Manual reactivity trigger '{func}' - review if necessary"

        findings.append(
            StandardFinding(
                rule_name="vue-unnecessary-rerender",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="vue-performance",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-1050",
                snippet=f"{func}(...)",
            )
        )

    return findings


def _find_missing_component_names(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find components without explicit names.

    Named components are easier to debug in Vue DevTools and produce
    better warning messages.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(Q("files").select("path").where("ext = ?", ".vue"))

    vue_component_files = [row[0] for row in rows if row[0] in vue_files]

    for file in vue_component_files:
        rows = db.query(
            Q("symbols").select("name").where("path = ?", file).where("name IS NOT NULL")
        )

        has_name = False
        for (name,) in rows:
            if name == "name" or name.startswith("name:") or name.startswith('"name"'):
                has_name = True
                break

        if not has_name:
            findings.append(
                StandardFinding(
                    rule_name="vue-missing-name",
                    message="Component missing explicit name property - harder to debug in DevTools",
                    file_path=file,
                    line=1,
                    severity=Severity.LOW,
                    category="vue-maintainability",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1061",
                )
            )

    return findings


def _find_inefficient_computed(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find inefficient computed properties.

    Expensive operations in computed properties run on every dependency change.
    Consider memoization or moving to methods with manual caching.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function")
        .where("caller_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, operation, caller in rows:
        if file not in vue_files:
            continue

        if operation not in EXPENSIVE_TEMPLATE_OPS:
            continue

        if "computed" in caller or "get " in caller:
            findings.append(
                StandardFinding(
                    rule_name="vue-expensive-computed",
                    message=f"Expensive operation '{operation}' in computed property - consider memoization",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="vue-performance",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-1050",
                    snippet=f"{operation}(...) in computed",
                )
            )

    return findings


def _find_complex_template_expressions(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find overly complex expressions in templates.

    Complex logic in templates is hard to read and test.
    Move to computed properties or methods.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("symbols").select("path", "line", "name").where("name IS NOT NULL").order_by("path, line")
    )

    for path, line, name in rows:
        if path not in vue_files:
            continue

        and_count = name.count("&&")
        or_count = name.count("||")
        ternary_count = name.count("?")

        if and_count > 2 or or_count > 2 or ternary_count > 2:
            findings.append(
                StandardFinding(
                    rule_name="vue-complex-template",
                    message="Complex logic in template - move to computed property for readability",
                    file_path=path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="vue-maintainability",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1061",
                )
            )

    return findings
