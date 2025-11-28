"""Vue State Management Analyzer - Database-First Approach."""

import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="vue_state",
    category="vue",
    target_extensions=[".js", ".ts"],
    target_file_patterns=["frontend/", "client/", "src/store/", "src/stores/", "store/", "stores/"],
    exclude_patterns=["backend/", "server/", "api/", "__tests__/", "*.test.*", "*.spec.*"],
    requires_jsx_pass=False,
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


STATE_MUTATIONS = frozenset(
    ["state.", "this.state.", "$store.state.", "store.state.", "this.$store.state."]
)


STRICT_VIOLATIONS = frozenset(
    [
        "state.",
        "this.$store.state.",
        "store.state.",
        "Object.assign",
        "Array.push",
        "Array.splice",
        "delete ",
        "Vue.set",
        "Vue.delete",
    ]
)


ACTION_PATTERNS = frozenset(
    [
        "actions:",
        "dispatch",
        "store.dispatch",
        "$store.dispatch",
        "mapActions",
        "action.type",
        "action.payload",
    ]
)


MUTATION_PATTERNS = frozenset(
    [
        "mutations:",
        "commit",
        "store.commit",
        "$store.commit",
        "mapMutations",
        "mutation.type",
        "mutation.payload",
    ]
)


GETTER_PATTERNS = frozenset(
    ["getters:", "store.getters", "$store.getters", "mapGetters", "rootGetters", "getter"]
)


ANTIPATTERNS = frozenset(
    ["localStorage", "sessionStorage", "window.", "document.", "global.", "process.env"]
)


def find_vue_state_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Vue state management anti-patterns (Vuex/Pinia)."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        store_files = _get_store_files(cursor)
        if not store_files:
            return findings

        findings.extend(_find_direct_state_mutations(cursor, store_files))
        findings.extend(_find_async_mutations(cursor, store_files))
        findings.extend(_find_missing_namespacing(cursor, store_files))
        findings.extend(_find_subscription_leaks(cursor, store_files))
        findings.extend(_find_circular_getters(cursor, store_files))
        findings.extend(_find_persistence_issues(cursor, store_files))
        findings.extend(_find_large_stores(cursor, store_files))
        findings.extend(_find_unhandled_action_errors(cursor, store_files))

    finally:
        conn.close()

    return findings


def _get_store_files(cursor) -> set[str]:
    """Get all Vuex/Pinia store files."""
    store_files = set()

    cursor.execute("""
        SELECT DISTINCT path
        FROM files
        WHERE path IS NOT NULL
    """)

    for (path,) in cursor.fetchall():
        path_lower = path.lower()
        if any(pattern in path_lower for pattern in ["store", "vuex", "pinia", "state"]):
            store_files.add(path)

    all_patterns = list(VUEX_PATTERNS | PINIA_PATTERNS)
    placeholders = ",".join("?" * len(all_patterns))

    cursor.execute(
        f"""
        SELECT DISTINCT path, name
        FROM symbols
        WHERE name IN ({placeholders})
           OR name IS NOT NULL
    """,
        all_patterns,
    )

    for path, name in cursor.fetchall():
        if "$store" in name or "defineStore" in name or "createStore" in name:
            store_files.add(path)

    return store_files


def _find_direct_state_mutations(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find direct state mutations outside of mutations."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND target_var IS NOT NULL
        ORDER BY file, line
    """,
        list(store_files),
    )

    for file, line, target, _source in cursor.fetchall():
        if not any(
            pattern in target
            for pattern in ["state.", "this.state.", "$store.state.", "store.state."]
        ):
            continue

        file_lower = file.lower()
        if "mutation" in file_lower or "reducer" in file_lower:
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-direct-state-mutation",
                message=f'Direct state mutation "{target}" outside of mutation',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="vuex-antipattern",
                confidence=Confidence.HIGH,
                cwe_id="CWE-471",
            )
        )

    cursor.execute(
        f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ('push', 'pop', 'shift', 'unshift', 'splice', 'sort', 'reverse')
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """,
        list(store_files),
    )

    for file, line, method, args in cursor.fetchall():
        if "state." not in args and "$store.state" not in args:
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-state-array-mutation",
                message=f"Array mutation method {method} on state",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vuex-antipattern",
                confidence=Confidence.HIGH,
                cwe_id="CWE-471",
            )
        )

    return findings


def _find_async_mutations(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find async operations in mutations (anti-pattern)."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN (
              'setTimeout', 'setInterval', 'fetch', 'axios',
              'Promise', 'async', 'await', 'then', 'catch'
          )
        ORDER BY file, line
    """,
        list(store_files),
    )

    for file, line, async_op in cursor.fetchall():
        file_lower = file.lower()
        if "mutation" not in file_lower and "mutations." not in file_lower:
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-async-mutation",
                message=f"Async operation {async_op} in mutation - use actions instead",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vuex-antipattern",
                confidence=Confidence.HIGH,
                cwe_id="CWE-662",
            )
        )

    return findings


def _find_missing_namespacing(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find modules without proper namespacing."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT DISTINCT s1.path, s1.name
        FROM symbols s1
        WHERE s1.path IN ({file_placeholders})
          AND s1.name IS NOT NULL
        ORDER BY s1.path
    """,
        list(store_files),
    )

    file_symbols = {}
    for path, name in cursor.fetchall():
        if path not in file_symbols:
            file_symbols[path] = []
        file_symbols[path].append(name)

    for file, symbols in file_symbols.items():
        if "modules" not in file.lower():
            continue

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


def _find_subscription_leaks(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find store subscriptions without cleanup."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ('subscribe', 'subscribeAction', '$subscribe', '$onAction')
        ORDER BY f.file, f.line
    """,
        list(store_files),
    )

    for file, line, subscription in cursor.fetchall():
        cursor.execute(
            """
            SELECT target_var
            FROM assignments
            WHERE file = ?
              AND line = ?
              AND target_var IS NOT NULL
        """,
            (file, line),
        )

        has_unsubscribe = False
        for (target_var,) in cursor.fetchall():
            if "unsubscribe" in target_var.lower():
                has_unsubscribe = True
                break

        if has_unsubscribe:
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-subscription-leak",
                message=f"{subscription} without cleanup - memory leak",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vuex-memory-leak",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-401",
            )
        )

    return findings


def _find_circular_getters(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find circular dependencies in getters."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT s.path, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
        ORDER BY s.path, s.line
    """,
        list(store_files),
    )

    all_symbols = cursor.fetchall()

    for file, line, name in all_symbols:
        if "getters." not in name:
            continue

        has_getter_ref = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and line2 > line and line2 < line + 10 and "getters." in name2:
                has_getter_ref = True
                break

        if not has_getter_ref:
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-circular-getter",
                message="Getter referencing other getters - potential circular dependency",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="vuex-architecture",
                confidence=Confidence.LOW,
                cwe_id="CWE-1047",
            )
        )

    return findings


def _find_persistence_issues(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find state persistence anti-patterns."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND (target_var IS NOT NULL OR source_expr IS NOT NULL)
        ORDER BY file, line
    """,
        list(store_files),
    )

    for file, line, target, source in cursor.fetchall():
        if not (
            "localStorage" in (source or "")
            or "sessionStorage" in (source or "")
            or "localStorage" in (target or "")
            or "sessionStorage" in (target or "")
        ):
            continue

        if "localStorage" in (source or "") or "localStorage" in (target or ""):
            storage = "localStorage"
        else:
            storage = "sessionStorage"

        findings.append(
            StandardFinding(
                rule_name="vue-unsafe-persistence",
                message=f"Using {storage} for state persistence - use proper plugins",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="vuex-persistence",
                confidence=Confidence.HIGH,
                cwe_id="CWE-922",
            )
        )

    cursor.execute(
        f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND target_var IS NOT NULL
        ORDER BY file, line
    """,
        list(store_files),
    )

    sensitive_patterns = frozenset(["password", "token", "secret", "apikey", "creditcard", "ssn"])

    for file, line, var, _ in cursor.fetchall():
        var_lower = var.lower()

        if not var_lower.startswith("state."):
            continue

        if not any(pattern in var_lower for pattern in sensitive_patterns):
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-sensitive-in-state",
                message=f'Sensitive data "{var}" in state - security risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vuex-security",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-200",
            )
        )

    return findings


def _find_large_stores(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find excessively large store definitions."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT s.path, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
    """,
        list(store_files),
    )

    file_props = {}
    for path, name in cursor.fetchall():
        if name.startswith("state.") or name.startswith("state:"):
            if path not in file_props:
                file_props[path] = 0
            file_props[path] += 1

    for file, count in file_props.items():
        if count > 50:
            findings.append(
                StandardFinding(
                    rule_name="vue-large-store",
                    message=f"Store has {count} state properties - consider modularization",
                    file_path=file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="vuex-architecture",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-1061",
                )
            )

    cursor.execute(
        f"""
        SELECT s.path, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
    """,
        list(store_files),
    )

    file_counts = {}
    for path, name in cursor.fetchall():
        name_lower = name.lower()
        if "action" in name_lower or "mutation" in name_lower:
            if path not in file_counts:
                file_counts[path] = {"actions": 0, "mutations": 0}
            if "action" in name_lower:
                file_counts[path]["actions"] += 1
            if "mutation" in name_lower:
                file_counts[path]["mutations"] += 1

    for file, counts in file_counts.items():
        actions = counts["actions"]
        mutations = counts["mutations"]
        if actions > 30 or mutations > 30:
            findings.append(
                StandardFinding(
                    rule_name="vue-too-many-actions",
                    message=f"Store has {actions} actions and {mutations} mutations - refactor needed",
                    file_path=file,
                    line=1,
                    severity=Severity.LOW,
                    category="vuex-architecture",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-1061",
                )
            )

    return findings


def _find_unhandled_action_errors(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find actions without error handling."""
    findings = []

    file_placeholders = ",".join("?" * len(store_files))

    cursor.execute(
        f"""
        SELECT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.file IN ({file_placeholders})
          AND f1.callee_function IN ('fetch', 'axios', 'post', 'get', 'put', 'delete')
        ORDER BY f1.file, f1.line
    """,
        list(store_files),
    )

    for file, line, api_call in cursor.fetchall():
        file_lower = file.lower()
        if "action" not in file_lower and "actions." not in file_lower:
            continue

        cursor.execute(
            """
            SELECT callee_function
            FROM function_call_args
            WHERE file = ?
              AND ABS(line - ?) <= 10
              AND callee_function IN ('catch', 'try', 'finally')
        """,
            (file, line),
        )

        if cursor.fetchone():
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-action-no-error-handling",
                message=f"Action with {api_call} but no error handling",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="vuex-error-handling",
                confidence=Confidence.LOW,
                cwe_id="CWE-248",
            )
        )

    return findings


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point."""
    return find_vue_state_issues(context)
