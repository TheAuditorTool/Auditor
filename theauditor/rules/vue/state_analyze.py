"""Vue State Management Analyzer - Database-First Approach."""

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
    name="vue_state",
    category="vue",
    target_extensions=[".js", ".ts"],
    target_file_patterns=["frontend/", "client/", "src/store/", "src/stores/", "store/", "stores/"],
    exclude_patterns=["backend/", "server/", "api/", "__tests__/", "*.test.*", "*.spec.*"],
    execution_scope="database",
    primary_table="files",
)


VUEX_PATTERNS = frozenset(
    [
        "createStore",
        "useStore",
        "$store",
        "this.$store",
        "mapState",
        "mapGetters",
        "mapActions",
        "mapMutations",
        "commit",
        "dispatch",
        "subscribe",
        "subscribeAction",
        "registerModule",
        "unregisterModule",
        "hasModule",
    ]
)


PINIA_PATTERNS = frozenset(
    [
        "defineStore",
        "createPinia",
        "setActivePinia",
        "storeToRefs",
        "acceptHMRUpdate",
        "useStore",
        "$patch",
        "$reset",
        "$subscribe",
        "$onAction",
        "$dispose",
        "getActivePinia",
        "setMapStoreSuffix",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue state management anti-patterns (Vuex/Pinia)."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        store_files = _get_store_files(db)
        if not store_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_find_direct_state_mutations(db, store_files))
        findings.extend(_find_async_mutations(db, store_files))
        findings.extend(_find_missing_namespacing(db, store_files))
        findings.extend(_find_subscription_leaks(db, store_files))
        findings.extend(_find_circular_getters(db, store_files))
        findings.extend(_find_persistence_issues(db, store_files))
        findings.extend(_find_large_stores(db, store_files))
        findings.extend(_find_unhandled_action_errors(db, store_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_store_files(db: RuleDB) -> set[str]:
    """Get all Vuex/Pinia store files."""
    store_files: set[str] = set()

    file_rows = db.query(Q("files").select("path").where("path IS NOT NULL"))

    for (path,) in file_rows:
        path_lower = path.lower()
        if any(pattern in path_lower for pattern in ["store", "vuex", "pinia", "state"]):
            store_files.add(path)

    symbol_rows = db.query(Q("symbols").select("path", "name").where("name IS NOT NULL"))

    for path, name in symbol_rows:
        if "$store" in name or "defineStore" in name or "createStore" in name:
            store_files.add(path)

    return store_files


def _find_direct_state_mutations(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find direct state mutations outside of mutations."""
    findings: list[StandardFinding] = []

    for file in store_files:
        assignment_rows = db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("file = ?", file)
            .where("target_var IS NOT NULL")
            .order_by("file, line")
        )

        for file_path, line, target, _source in assignment_rows:
            if not any(
                pattern in target
                for pattern in ["state.", "this.state.", "$store.state.", "store.state."]
            ):
                continue

            file_lower = file_path.lower()
            if "mutation" in file_lower or "reducer" in file_lower:
                continue

            findings.append(
                StandardFinding(
                    rule_name="vue-direct-state-mutation",
                    message=f'Direct state mutation "{target}" outside of mutation',
                    file_path=file_path,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="vuex-antipattern",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-471",
                )
            )

    return findings


def _find_async_mutations(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find async operations in mutations (anti-pattern)."""
    findings: list[StandardFinding] = []

    async_ops = [
        "setTimeout",
        "setInterval",
        "fetch",
        "axios",
        "Promise",
        "async",
        "await",
        "then",
        "catch",
    ]

    for file in store_files:
        file_lower = file.lower()
        if "mutation" not in file_lower and "mutations." not in file_lower:
            continue

        for async_op in async_ops:
            rows = db.query(
                Q("function_call_args")
                .select("file", "line", "callee_function")
                .where("file = ?", file)
                .where("callee_function = ?", async_op)
                .order_by("file, line")
            )

            for file_path, line, op in rows:
                findings.append(
                    StandardFinding(
                        rule_name="vue-async-mutation",
                        message=f"Async operation {op} in mutation - use actions instead",
                        file_path=file_path,
                        line=line,
                        severity=Severity.HIGH,
                        category="vuex-antipattern",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-662",
                    )
                )

    return findings


def _find_missing_namespacing(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find modules without proper namespacing."""
    findings: list[StandardFinding] = []

    for file in store_files:
        if "modules" not in file.lower():
            continue

        symbol_rows = db.query(
            Q("symbols").select("path", "name").where("path = ?", file).where("name IS NOT NULL")
        )

        symbols = [name for _, name in symbol_rows]

        has_namespace = any("namespaced" in s and "true" in s for s in symbols)
        if has_namespace:
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-module-no-namespace",
                message="Store module without namespacing - naming conflicts risk",
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category="vuex-architecture",
                confidence=Confidence.LOW,
                cwe_id="CWE-1061",
            )
        )

    return findings


def _find_subscription_leaks(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find store subscriptions without cleanup."""
    findings: list[StandardFinding] = []

    subscription_funcs = ["subscribe", "subscribeAction", "$subscribe", "$onAction"]

    for file in store_files:
        for sub_func in subscription_funcs:
            sub_rows = db.query(
                Q("function_call_args")
                .select("file", "line", "callee_function")
                .where("file = ?", file)
                .where("callee_function = ?", sub_func)
                .order_by("file, line")
            )

            for file_path, line, subscription in sub_rows:
                assign_rows = db.query(
                    Q("assignments")
                    .select("target_var")
                    .where("file = ?", file_path)
                    .where("line = ?", line)
                    .where("target_var IS NOT NULL")
                )

                if list(assign_rows):
                    continue

                findings.append(
                    StandardFinding(
                        rule_name="vue-subscription-leak",
                        message=f"{subscription} return value not captured - memory leak risk",
                        file_path=file_path,
                        line=line,
                        severity=Severity.HIGH,
                        category="vuex-memory-leak",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-401",
                    )
                )

    return findings


def _find_circular_getters(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find circular dependencies in getters."""
    findings: list[StandardFinding] = []

    for file in store_files:
        symbol_rows = db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("path = ?", file)
            .where("name IS NOT NULL")
            .order_by("path, line")
        )

        all_symbols = list(symbol_rows)

        for file_path, line, name in all_symbols:
            if "getters." not in name:
                continue

            has_getter_ref = False
            for file2, line2, name2 in all_symbols:
                if (
                    file2 == file_path
                    and line2 > line
                    and line2 < line + 10
                    and "getters." in name2
                ):
                    has_getter_ref = True
                    break

            if not has_getter_ref:
                continue

            findings.append(
                StandardFinding(
                    rule_name="vue-circular-getter",
                    message="Getter referencing other getters - potential circular dependency",
                    file_path=file_path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="vuex-architecture",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1047",
                )
            )

    return findings


def _find_persistence_issues(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find state persistence anti-patterns."""
    findings: list[StandardFinding] = []
    sensitive_patterns = frozenset(["password", "token", "secret", "apikey", "creditcard", "ssn"])

    for file in store_files:
        assignment_rows = db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("file = ?", file)
            .order_by("file, line")
        )

        for file_path, line, target, source in assignment_rows:
            target_str = target or ""
            source_str = source or ""

            if "localStorage" in source_str or "localStorage" in target_str:
                storage = "localStorage"
            elif "sessionStorage" in source_str or "sessionStorage" in target_str:
                storage = "sessionStorage"
            else:
                storage = None

            if storage:
                findings.append(
                    StandardFinding(
                        rule_name="vue-unsafe-persistence",
                        message=f"Using {storage} for state persistence - use proper plugins",
                        file_path=file_path,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="vuex-persistence",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-922",
                    )
                )

            if target_str.lower().startswith("state."):
                var_lower = target_str.lower()
                if any(pattern in var_lower for pattern in sensitive_patterns):
                    findings.append(
                        StandardFinding(
                            rule_name="vue-sensitive-in-state",
                            message=f'Sensitive data "{target_str}" in state - security risk',
                            file_path=file_path,
                            line=line,
                            severity=Severity.HIGH,
                            category="vuex-security",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-200",
                        )
                    )

    return findings


def _find_large_stores(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find excessively large store definitions."""
    findings: list[StandardFinding] = []

    for file in store_files:
        symbol_rows = db.query(
            Q("symbols").select("path", "name").where("path = ?", file).where("name IS NOT NULL")
        )

        state_count = 0
        action_count = 0
        mutation_count = 0

        for _path, name in symbol_rows:
            if name.startswith("state.") or name.startswith("state:"):
                state_count += 1

            name_lower = name.lower()
            if "action" in name_lower:
                action_count += 1
            if "mutation" in name_lower:
                mutation_count += 1

        if state_count > 50:
            findings.append(
                StandardFinding(
                    rule_name="vue-large-store",
                    message=f"Store has {state_count} state properties - consider modularization",
                    file_path=file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="vuex-architecture",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-1061",
                )
            )

        if action_count > 30 or mutation_count > 30:
            findings.append(
                StandardFinding(
                    rule_name="vue-too-many-actions",
                    message=f"Store has {action_count} actions and {mutation_count} mutations - refactor needed",
                    file_path=file,
                    line=1,
                    severity=Severity.LOW,
                    category="vuex-architecture",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1061",
                )
            )

    return findings


def _find_unhandled_action_errors(db: RuleDB, store_files: set[str]) -> list[StandardFinding]:
    """Find actions without error handling."""
    findings: list[StandardFinding] = []
    api_call_funcs = ["fetch", "axios", "post", "get", "put", "delete"]
    error_handling_funcs = ["catch", "try", "finally"]

    for file in store_files:
        file_lower = file.lower()
        if "action" not in file_lower and "actions." not in file_lower:
            continue

        for api_func in api_call_funcs:
            api_rows = db.query(
                Q("function_call_args")
                .select("file", "line", "callee_function")
                .where("file = ?", file)
                .where("callee_function = ?", api_func)
                .order_by("file, line")
            )

            for file_path, line, api_call in api_rows:
                has_error_handling = False

                for error_func in error_handling_funcs:
                    error_rows = db.query(
                        Q("function_call_args")
                        .select("callee_function")
                        .where("file = ?", file_path)
                        .where("line BETWEEN ? AND ?", line - 10, line + 10)
                        .where("callee_function = ?", error_func)
                    )

                    if list(error_rows):
                        has_error_handling = True
                        break

                if has_error_handling:
                    continue

                findings.append(
                    StandardFinding(
                        rule_name="vue-action-no-error-handling",
                        message=f"Action with {api_call} but no error handling",
                        file_path=file_path,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="vuex-error-handling",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-248",
                    )
                )

    return findings
