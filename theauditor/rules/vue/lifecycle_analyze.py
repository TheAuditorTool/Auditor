"""Vue Lifecycle Analyzer - Database-First Approach."""

import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="vue_lifecycle",
    category="vue",
    target_extensions=[".vue", ".js", ".ts", ".jsx", ".tsx"],
    target_file_patterns=["frontend/", "client/", "src/components/", "src/views/", "src/pages/"],
    exclude_patterns=[
        "backend/",
        "server/",
        "api/",
        "migrations/",
        "__tests__/",
        "*.test.*",
        "*.spec.*",
    ],
    requires_jsx_pass=False,
)


VUE2_LIFECYCLE = frozenset(
    [
        "beforeCreate",
        "created",
        "beforeMount",
        "mounted",
        "beforeUpdate",
        "updated",
        "beforeDestroy",
        "destroyed",
        "activated",
        "deactivated",
        "errorCaptured",
    ]
)


VUE3_LIFECYCLE = frozenset(
    [
        "beforeCreate",
        "created",
        "beforeMount",
        "mounted",
        "beforeUpdate",
        "updated",
        "beforeUnmount",
        "unmounted",
        "activated",
        "deactivated",
        "errorCaptured",
        "renderTracked",
        "renderTriggered",
        "serverPrefetch",
    ]
)


COMPOSITION_LIFECYCLE = frozenset(
    [
        "onBeforeMount",
        "onMounted",
        "onBeforeUpdate",
        "onUpdated",
        "onBeforeUnmount",
        "onUnmounted",
        "onActivated",
        "onDeactivated",
        "onErrorCaptured",
        "onRenderTracked",
        "onRenderTriggered",
        "onServerPrefetch",
    ]
)


MOUNT_OPERATIONS = frozenset(
    [
        "addEventListener",
        "querySelector",
        "getElementById",
        "getElementsByClassName",
        "document.",
        "window.",
        "ResizeObserver",
        "IntersectionObserver",
        "MutationObserver",
    ]
)


CLEANUP_REQUIRED = frozenset(
    [
        "addEventListener",
        "setInterval",
        "setTimeout",
        "ResizeObserver",
        "IntersectionObserver",
        "MutationObserver",
        "WebSocket",
        "EventSource",
        "Worker",
        "subscribe",
    ]
)


DATA_FETCH_OPS = frozenset(
    ["fetch", "axios", "ajax", "$http", "get", "post", "api.", "request", "load", "query"]
)


REACTIVE_OPS = frozenset(
    ["this.", "data.", "props.", "computed.", "watch", "watchEffect", "$watch", "ref", "reactive"]
)


SIDE_EFFECTS = frozenset(
    [
        "console.",
        "alert",
        "confirm",
        "localStorage",
        "sessionStorage",
        "document.title",
        "window.location",
    ]
)


def find_vue_lifecycle_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Vue lifecycle hook misuse and anti-patterns."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        vue_files = _get_vue_files(cursor)
        if not vue_files:
            return findings

        findings.extend(_find_dom_before_mount(cursor, vue_files))
        findings.extend(_find_missing_cleanup(cursor, vue_files))
        findings.extend(_find_wrong_data_fetch(cursor, vue_files))
        findings.extend(_find_infinite_updates(cursor, vue_files))
        findings.extend(_find_timer_leaks(cursor, vue_files))
        findings.extend(_find_computed_side_effects(cursor, vue_files))
        findings.extend(_find_incorrect_hook_order(cursor, vue_files))
        findings.extend(_find_unhandled_async(cursor, vue_files))

    finally:
        conn.close()

    return findings


def _get_vue_files(cursor) -> set[str]:
    """Get all Vue-related files from the database."""
    vue_files = set()

    cursor.execute("""
        SELECT DISTINCT path, ext
        FROM files
        WHERE ext IN ('.vue', '.js', '.ts')
    """)

    for path, ext in cursor.fetchall():
        if ext == ".vue" or (ext in (".js", ".ts") and "component" in path.lower()):
            vue_files.add(path)

    all_hooks = list(VUE2_LIFECYCLE | VUE3_LIFECYCLE | COMPOSITION_LIFECYCLE)
    placeholders = ",".join("?" * len(all_hooks))

    cursor.execute(
        f"""
        SELECT DISTINCT file
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
    """,
        all_hooks,
    )
    vue_files.update(row[0] for row in cursor.fetchall())

    return vue_files


def _find_dom_before_mount(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find DOM operations in hooks that run before mounting."""
    findings = []

    dom_ops = list(MOUNT_OPERATIONS)
    dom_placeholders = ",".join("?" * len(dom_ops))
    file_placeholders = ",".join("?" * len(vue_files))

    early_hooks = ["beforeCreate", "created", "onBeforeMount"]

    for hook in early_hooks:
        cursor.execute(
            f"""
            SELECT DISTINCT f1.file, f1.line, f2.callee_function
            FROM function_call_args f1
            JOIN function_call_args f2 ON f1.file = f2.file
            WHERE f1.file IN ({file_placeholders})
              AND f1.callee_function = ?
              AND f2.callee_function IN ({dom_placeholders})
              AND ABS(f2.line - f1.line) <= 20
              AND f2.line > f1.line
            ORDER BY f1.file, f1.line
        """,
            list(vue_files) + [hook] + dom_ops,
        )

        for file, line, dom_op in cursor.fetchall():
            findings.append(
                StandardFinding(
                    rule_name="vue-dom-before-mount",
                    message=f"DOM operation {dom_op} in {hook} - DOM not ready yet",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="vue-lifecycle",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-665",
                )
            )

    return findings


def _find_missing_cleanup(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find resources created without cleanup."""
    findings = []

    cleanup_ops = list(CLEANUP_REQUIRED)
    cleanup_placeholders = ",".join("?" * len(cleanup_ops))
    file_placeholders = ",".join("?" * len(vue_files))

    cursor.execute(
        f"""
        SELECT DISTINCT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.file IN ({file_placeholders})
          AND f1.callee_function IN ({cleanup_placeholders})
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.callee_function IN ('mounted', 'onMounted', 'created')
                AND ABS(f2.line - f1.line) <= 20
          )
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f3
              WHERE f3.file = f1.file
                AND f3.callee_function IN (
                    'removeEventListener', 'clearInterval', 'clearTimeout',
                    'unsubscribe', 'disconnect', 'close', 'abort', 'terminate',
                    'destroyed', 'beforeDestroy', 'unmounted', 'beforeUnmount',
                    'onUnmounted', 'onBeforeUnmount'
                )
          )
        ORDER BY f1.file, f1.line
    """,
        list(vue_files) + cleanup_ops,
    )

    for file, line, operation in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="vue-missing-cleanup",
                message=f"{operation} without cleanup - memory leak",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vue-memory-leak",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-401",
            )
        )

    return findings


def _find_wrong_data_fetch(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find data fetching in wrong lifecycle hooks."""
    findings = []

    fetch_ops = list(DATA_FETCH_OPS)
    fetch_placeholders = ",".join("?" * len(fetch_ops))
    file_placeholders = ",".join("?" * len(vue_files))

    bad_hooks = ["beforeMount", "onBeforeMount", "updated", "onUpdated"]

    for hook in bad_hooks:
        cursor.execute(
            f"""
            SELECT DISTINCT f1.file, f1.line, f2.callee_function
            FROM function_call_args f1
            JOIN function_call_args f2 ON f1.file = f2.file
            WHERE f1.file IN ({file_placeholders})
              AND f1.callee_function = ?
              AND f2.callee_function IN ({fetch_placeholders})
              AND ABS(f2.line - f1.line) <= 20
              AND f2.line > f1.line
            ORDER BY f1.file, f1.line
        """,
            list(vue_files) + [hook] + fetch_ops,
        )

        for file, line, fetch_op in cursor.fetchall():
            if hook in ["updated", "onUpdated"]:
                message = f"Data fetch {fetch_op} in {hook} - causes infinite loops"
                severity = Severity.CRITICAL
            else:
                message = f"Data fetch {fetch_op} in {hook} - use created/mounted instead"
                severity = Severity.MEDIUM

            findings.append(
                StandardFinding(
                    rule_name="vue-wrong-fetch-hook",
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="vue-lifecycle",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-665",
                )
            )

    return findings


def _find_infinite_updates(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find potential infinite update loops."""
    findings = []

    file_placeholders = ",".join("?" * len(vue_files))

    update_hooks = ["beforeUpdate", "updated", "onBeforeUpdate", "onUpdated"]

    for hook in update_hooks:
        cursor.execute(
            f"""
            SELECT DISTINCT a.file, a.line, a.target_var
            FROM assignments a
            JOIN function_call_args f ON a.file = f.file
            WHERE a.file IN ({file_placeholders})
              AND f.callee_function = ?
              AND ABS(a.line - f.line) <= 20
              AND a.line > f.line
              AND a.target_var IS NOT NULL
            ORDER BY a.file, a.line
        """,
            list(vue_files) + [hook],
        )

        for file, line, var in cursor.fetchall():
            if not (var.startswith("this.") or var.startswith("data.") or var.startswith("state.")):
                continue
            findings.append(
                StandardFinding(
                    rule_name="vue-infinite-update",
                    message=f"Modifying {var} in {hook} - causes infinite update loop",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="vue-lifecycle",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-835",
                )
            )

    return findings


def _find_timer_leaks(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find timers without cleanup."""
    findings = []

    file_placeholders = ",".join("?" * len(vue_files))

    cursor.execute(
        f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ('setInterval', 'setTimeout')
        ORDER BY f.file, f.line
    """,
        list(vue_files),
    )

    for file, line, timer_func in cursor.fetchall():
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

        has_timer_var = False
        for (target_var,) in cursor.fetchall():
            target_lower = target_var.lower()
            if "timer" in target_lower or "interval" in target_lower or "timeout" in target_lower:
                has_timer_var = True
                break

        if has_timer_var:
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-timer-leak",
                message=f"{timer_func} not stored for cleanup",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vue-memory-leak",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-401",
            )
        )

    return findings


def _find_computed_side_effects(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find side effects in computed properties."""
    findings = []

    side_effects = list(SIDE_EFFECTS)
    effect_placeholders = ",".join("?" * len(side_effects))
    file_placeholders = ",".join("?" * len(vue_files))

    cursor.execute(
        f"""
        SELECT DISTINCT s.path, s.line, s.name, f.callee_function, f.line AS f_line
        FROM symbols s
        JOIN function_call_args f ON s.path = f.file
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
          AND f.callee_function IN ({effect_placeholders})
          AND ABS(f.line - s.line) <= 10
          AND f.line > s.line
        ORDER BY s.path, s.line
    """,
        list(vue_files) + side_effects,
    )

    for file, line, name, effect, _f_line in cursor.fetchall():
        if "computed" not in name.lower():
            continue
        findings.append(
            StandardFinding(
                rule_name="vue-computed-side-effect",
                message=f"Side effect {effect} in computed property",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="vue-antipattern",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-1061",
            )
        )

    return findings


def _find_incorrect_hook_order(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find incorrect lifecycle hook ordering."""
    findings = []

    hook_order = {
        "beforeCreate": 1,
        "onBeforeMount": 1,
        "created": 2,
        "beforeMount": 3,
        "mounted": 4,
        "onMounted": 4,
        "beforeUpdate": 5,
        "onBeforeUpdate": 5,
        "updated": 6,
        "onUpdated": 6,
        "beforeUnmount": 7,
        "onBeforeUnmount": 7,
        "beforeDestroy": 7,
        "unmounted": 8,
        "onUnmounted": 8,
        "destroyed": 8,
    }

    all_hooks = list(hook_order.keys())
    hook_placeholders = ",".join("?" * len(all_hooks))
    file_placeholders = ",".join("?" * len(vue_files))

    cursor.execute(
        f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ({hook_placeholders})
        ORDER BY file, line
    """,
        list(vue_files) + all_hooks,
    )

    file_hooks: dict[str, list[tuple]] = {}
    for file, line, hook in cursor.fetchall():
        if file not in file_hooks:
            file_hooks[file] = []
        if hook in hook_order:
            file_hooks[file].append((line, hook, hook_order[hook]))

    for file, hooks in file_hooks.items():
        hooks.sort(key=lambda x: x[0])
        for i in range(len(hooks) - 1):
            if hooks[i][2] > hooks[i + 1][2]:
                findings.append(
                    StandardFinding(
                        rule_name="vue-hook-order",
                        message=f"{hooks[i][1]} after {hooks[i + 1][1]} - wrong order",
                        file_path=file,
                        line=hooks[i][0],
                        severity=Severity.MEDIUM,
                        category="vue-lifecycle",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-665",
                    )
                )

    return findings


def _find_unhandled_async(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find async operations without error handling in lifecycle hooks."""
    findings = []

    file_placeholders = ",".join("?" * len(vue_files))
    all_hooks = list(VUE2_LIFECYCLE | VUE3_LIFECYCLE | COMPOSITION_LIFECYCLE)

    for hook in all_hooks:
        cursor.execute(
            f"""
            SELECT DISTINCT f1.file, f1.line
            FROM function_call_args f1
            WHERE f1.file IN ({file_placeholders})
              AND f1.callee_function = ?
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND ABS(f2.line - f1.line) <= 20
                    AND f2.line > f1.line
                    AND f2.callee_function IN ('fetch', 'axios', 'Promise')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f3
                  WHERE f3.file = f1.file
                    AND ABS(f3.line - f1.line) <= 20
                    AND f3.callee_function IN ('catch', 'finally', 'try')
              )
            ORDER BY f1.file, f1.line
        """,
            list(vue_files) + [hook],
        )

        for file, line in cursor.fetchall():
            findings.append(
                StandardFinding(
                    rule_name="vue-unhandled-async",
                    message=f"Async operation in {hook} without error handling",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="vue-error-handling",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-248",
                )
            )

    return findings


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point."""
    return find_vue_lifecycle_issues(context)
