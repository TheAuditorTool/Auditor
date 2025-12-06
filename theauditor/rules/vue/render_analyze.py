"""Vue Render Analyzer - Database-First Approach."""

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
    name="vue_render",
    category="vue",
    target_extensions=[".vue", ".js", ".ts", ".jsx", ".tsx"],
    target_file_patterns=["frontend/", "client/", "src/components/", "src/views/"],
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
    primary_table="files",
)


RENDER_FUNCTIONS = frozenset(
    [
        "render",
        "h",
        "createVNode",
        "createElementVNode",
        "createTextVNode",
        "createCommentVNode",
        "createStaticVNode",
        "resolveComponent",
        "resolveDynamicComponent",
        "resolveDirective",
        "withDirectives",
        "renderSlot",
        "renderList",
    ]
)


RERENDER_TRIGGERS = frozenset(
    [
        "$forceUpdate",
        "forceUpdate",
        "$set",
        "$delete",
        "Vue.set",
        "Vue.delete",
        "nextTick",
        "$nextTick",
    ]
)


EXPENSIVE_DOM_OPS = frozenset(
    [
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "document.writeln",
        "appendChild",
        "removeChild",
        "replaceChild",
        "cloneNode",
        "importNode",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue rendering anti-patterns and performance issues."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        vue_files = _get_vue_files(db)
        if not vue_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_find_vif_with_vfor(db, vue_files))
        findings.extend(_find_missing_list_keys(db, vue_files))
        findings.extend(_find_unnecessary_rerenders(db, vue_files))
        findings.extend(_find_unoptimized_lists(db, vue_files))
        findings.extend(_find_complex_render_functions(db, vue_files))
        findings.extend(_find_direct_dom_manipulation(db, vue_files))
        findings.extend(_find_inefficient_event_handlers(db, vue_files))
        findings.extend(_find_missing_optimizations(db, vue_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_vue_files(db: RuleDB) -> set[str]:
    """Get all Vue-related files from the database."""
    vue_files: set[str] = set()

    file_rows = db.query(
        Q("files").select("path", "ext").where("ext IN (?, ?, ?)", ".vue", ".js", ".ts")
    )

    for path, ext in file_rows:
        path_lower = path.lower()
        if ext == ".vue" or (ext in (".js", ".ts") and "vue" in path_lower):
            vue_files.add(path)

    symbol_rows = db.query(Q("symbols").select("path", "name").where("name IS NOT NULL"))

    for path, name in symbol_rows:
        if any(pattern in name for pattern in ["Vue", "v-for", "v-if", "template"]):
            vue_files.add(path)

    return vue_files


def _find_vif_with_vfor(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find v-if used with v-for (performance anti-pattern)."""
    findings: list[StandardFinding] = []

    all_symbols: list[tuple[str, int, str]] = []
    for file in vue_files:
        rows = db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("path = ?", file)
            .where("name IS NOT NULL")
            .order_by("path, line")
        )
        all_symbols.extend(rows)

    vfor_with_vif: list[tuple[str, int]] = []

    for file, line, name in all_symbols:
        if "v-for" not in name:
            continue

        has_vif = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and abs(line2 - line) <= 1 and "v-if" in name2:
                has_vif = True
                break

        if has_vif:
            vfor_with_vif.append((file, line))

    for file, line in vfor_with_vif:
        findings.append(
            StandardFinding(
                rule_name="vue-vif-with-vfor",
                message="v-if with v-for on same element - use computed property instead",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vue-performance",
                confidence=Confidence.HIGH,
                cwe_id="CWE-1050",
            )
        )

    return findings


def _find_missing_list_keys(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find v-for without proper keys."""
    findings: list[StandardFinding] = []

    all_symbols: list[tuple[str, int, str]] = []
    for file in vue_files:
        rows = db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("path = ?", file)
            .where("name IS NOT NULL")
            .order_by("path, line")
        )
        all_symbols.extend(rows)

    for file, line, name in all_symbols:
        if "v-for" not in name:
            continue

        has_key = False
        for file2, line2, name2 in all_symbols:
            if (
                file2 == file
                and abs(line2 - line) <= 2
                and (":key" in name2 or "v-bind:key" in name2 or "key=" in name2)
            ):
                has_key = True
                break

        if not has_key:
            findings.append(
                StandardFinding(
                    rule_name="vue-missing-key",
                    message="v-for without unique :key - causes rendering issues",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="vue-performance",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-1050",
                )
            )

    for file, line, name in all_symbols:
        if ':key="index"' in name or ':key="i"' in name or ':key="idx"' in name:
            findings.append(
                StandardFinding(
                    rule_name="vue-index-as-key",
                    message="Using array index as :key - causes issues when list changes",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="vue-performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1050",
                )
            )

    return findings


def _find_unnecessary_rerenders(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find unnecessary re-render triggers."""
    findings: list[StandardFinding] = []

    for file in vue_files:
        for trigger in RERENDER_TRIGGERS:
            rows = db.query(
                Q("function_call_args")
                .select("file", "line", "callee_function", "argument_expr")
                .where("file = ?", file)
                .where("callee_function = ?", trigger)
                .order_by("file, line")
            )

            for file_path, line, func, _args in rows:
                if func in ["$forceUpdate", "forceUpdate"]:
                    severity = Severity.HIGH
                    message = "Using $forceUpdate indicates reactivity system failure"
                else:
                    severity = Severity.MEDIUM
                    message = f"Manual reactivity trigger {func} - review necessity"

                findings.append(
                    StandardFinding(
                        rule_name="vue-force-update",
                        message=message,
                        file_path=file_path,
                        line=line,
                        severity=severity,
                        category="vue-performance",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1050",
                    )
                )

    return findings


def _find_unoptimized_lists(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find large lists without virtualization."""
    findings: list[StandardFinding] = []

    all_symbols: list[tuple[str, int, str]] = []
    for file in vue_files:
        rows = db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("path = ?", file)
            .where("name IS NOT NULL")
            .order_by("path, line")
        )
        all_symbols.extend(rows)

    for file, line, name in all_symbols:
        if "v-for" not in name:
            continue

        if any(pattern in name for pattern in ["1000", "10000", ".length > 100", ".length > 500"]):
            findings.append(
                StandardFinding(
                    rule_name="vue-large-list",
                    message="Large list without virtual scrolling - performance impact",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="vue-performance",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1050",
                )
            )

    for file, line, name in all_symbols:
        if "v-for" not in name:
            continue

        has_nested = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and line2 > line and line2 < line + 10 and "v-for" in name2:
                has_nested = True
                break

        if not has_nested:
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-nested-vfor",
                message="Nested v-for loops - O(n^2) complexity",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vue-performance",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-1050",
            )
        )

    return findings


def _find_complex_render_functions(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find overly complex render functions."""
    findings: list[StandardFinding] = []

    for file in vue_files:
        for func in RENDER_FUNCTIONS:
            rows = db.query(
                Q("function_call_args")
                .select("file", "caller_function")
                .where("file = ?", file)
                .where("callee_function = ?", func)
                .where("caller_function IS NOT NULL")
            )

            caller_counts: dict[str, int] = {}
            for file_path, caller in rows:
                key = f"{file_path}:{caller}"
                caller_counts[key] = caller_counts.get(key, 0) + 1

            for key, count in caller_counts.items():
                if count > 10:
                    file_path = key.rsplit(":", 1)[0]
                    findings.append(
                        StandardFinding(
                            rule_name="vue-complex-render",
                            message=f"Render function with {count} VNode calls - consider template",
                            file_path=file_path,
                            line=1,
                            severity=Severity.MEDIUM,
                            category="vue-maintainability",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-1061",
                        )
                    )

    return findings


def _find_direct_dom_manipulation(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find direct DOM manipulation (anti-pattern in Vue)."""
    findings: list[StandardFinding] = []

    dom_call_methods = frozenset(
        [
            "document.write",
            "document.writeln",
            "appendChild",
            "removeChild",
            "replaceChild",
            "cloneNode",
            "importNode",
            "insertAdjacentHTML",
        ]
    )

    for file in vue_files:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function")
            .where("file = ?", file)
            .where("callee_function IS NOT NULL")
            .order_by("file, line")
        )

        for file_path, line, operation in rows:
            if operation not in dom_call_methods and not operation.startswith("document."):
                continue

            if operation in ["document.write", "document.writeln", "insertAdjacentHTML"]:
                severity = Severity.HIGH
                message = f"Direct DOM manipulation with {operation} - security risk"
                cwe = "CWE-79"
            else:
                severity = Severity.MEDIUM
                message = f"Direct DOM manipulation {operation} - use Vue reactivity"
                cwe = "CWE-1061"

            findings.append(
                StandardFinding(
                    rule_name="vue-direct-dom",
                    message=message,
                    file_path=file_path,
                    line=line,
                    severity=severity,
                    category="vue-antipattern",
                    confidence=Confidence.MEDIUM,
                    cwe_id=cwe,
                )
            )

    for file in vue_files:
        assign_rows = db.query(
            Q("assignments")
            .select("file", "line", "target_var")
            .where("file = ?", file)
            .where("target_var IS NOT NULL")
            .order_by("file, line")
        )

        for file_path, line, target in assign_rows:
            target_lower = target.lower()
            if ".innerhtml" in target_lower or ".outerhtml" in target_lower:
                findings.append(
                    StandardFinding(
                        rule_name="vue-direct-dom",
                        message=f"Direct DOM manipulation via {target} - XSS risk",
                        file_path=file_path,
                        line=line,
                        severity=Severity.HIGH,
                        category="vue-antipattern",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _find_inefficient_event_handlers(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find inefficient event handler patterns."""
    findings: list[StandardFinding] = []

    for file in vue_files:
        assignment_rows = db.query(
            Q("assignments")
            .select("file", "line", "source_expr")
            .where("file = ?", file)
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file_path, line, handler in assignment_rows:
            if any(
                pattern in handler
                for pattern in ['@click="() =>', '@input="() =>', '@change="() =>', "v-on:"]
            ):
                findings.append(
                    StandardFinding(
                        rule_name="vue-inline-handler",
                        message="Inline arrow function in template - recreated on each render",
                        file_path=file_path,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="vue-performance",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1050",
                    )
                )

        symbol_rows = db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("path = ?", file)
            .where("name IS NOT NULL")
            .order_by("path, line")
        )

        for file_path, line, name in symbol_rows:
            if "@submit" in name and ".prevent" not in name:
                findings.append(
                    StandardFinding(
                        rule_name="vue-missing-prevent",
                        message="Form submit without .prevent modifier",
                        file_path=file_path,
                        line=line,
                        severity=Severity.LOW,
                        category="vue-bestpractice",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1061",
                    )
                )

    return findings


def _find_missing_optimizations(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find missing render optimizations."""
    findings: list[StandardFinding] = []

    for file in vue_files:
        template_rows = db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("path = ?", file)
            .where("type = ?", "template")
            .where("name IS NOT NULL")
            .order_by("path, line")
            .limit(10)
        )

        for file_path, line, name in template_rows:
            if (
                len(name) > 200
                and "{{" not in name
                and "v-once" not in name
                and "v-pre" not in name
            ):
                findings.append(
                    StandardFinding(
                        rule_name="vue-static-content",
                        message="Large static content without v-once directive",
                        file_path=file_path,
                        line=line,
                        severity=Severity.LOW,
                        category="vue-performance",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1050",
                    )
                )

        computed_rows = db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("path = ?", file)
            .where("name IS NOT NULL")
        )

        computed_symbols = [(f, ln, n) for f, ln, n in computed_rows if "computed" in n]

        for file_path, line, _name in computed_symbols:
            side_effect_rows = db.query(
                Q("function_call_args")
                .select("callee_function")
                .where("file = ?", file_path)
                .where("line BETWEEN ? AND ?", line - 5, line + 5)
                .where("callee_function IN (?, ?, ?)", "Math.random", "Date.now", "performance.now")
            )

            if list(side_effect_rows):
                findings.append(
                    StandardFinding(
                        rule_name="vue-computed-side-effects",
                        message="Computed property with non-deterministic value",
                        file_path=file_path,
                        line=line,
                        severity=Severity.HIGH,
                        category="vue-antipattern",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1061",
                    )
                )

    return findings
