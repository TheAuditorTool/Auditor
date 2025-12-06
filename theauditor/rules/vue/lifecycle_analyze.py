"""Vue Lifecycle Analyzer - Fidelity Layer Implementation.

Detects Vue lifecycle hook misuse and anti-patterns:
- DOM operations before component is mounted
- Missing cleanup for subscriptions/timers
- Data fetching in wrong lifecycle hooks
- Infinite update loops from state mutation in update hooks
- Timer leaks without proper cleanup
- Side effects in computed properties
- Incorrect lifecycle hook ordering
- Unhandled async operations in lifecycle hooks
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
    name="vue_lifecycle",
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
    primary_table="function_call_args",
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


CLEANUP_FUNCTIONS = frozenset(
    [
        "removeEventListener",
        "clearInterval",
        "clearTimeout",
        "unsubscribe",
        "disconnect",
        "close",
        "abort",
        "terminate",
        "destroyed",
        "beforeDestroy",
        "unmounted",
        "beforeUnmount",
        "onUnmounted",
        "onBeforeUnmount",
    ]
)


DATA_FETCH_OPS = frozenset(
    [
        "fetch",
        "axios",
        "ajax",
        "$http",
        "get",
        "post",
        "api.",
        "request",
        "load",
        "query",
    ]
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


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue lifecycle hook misuse and anti-patterns."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        vue_files = _get_vue_files(db)
        if not vue_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_find_dom_before_mount(db, vue_files))
        findings.extend(_find_missing_cleanup(db, vue_files))
        findings.extend(_find_wrong_data_fetch(db, vue_files))
        findings.extend(_find_infinite_updates(db, vue_files))
        findings.extend(_find_timer_leaks(db, vue_files))
        findings.extend(_find_computed_side_effects(db, vue_files))
        findings.extend(_find_incorrect_hook_order(db, vue_files))
        findings.extend(_find_unhandled_async(db, vue_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_vue_files(db: RuleDB) -> set[str]:
    """Get all Vue-related files from the database."""
    vue_files: set[str] = set()

    rows = db.query(
        Q("files").select("path", "ext").where("ext IN (?, ?, ?)", ".vue", ".js", ".ts")
    )

    for path, ext in rows:
        if ext == ".vue" or (ext in (".js", ".ts") and "component" in path.lower()):
            vue_files.add(path)

    all_hooks = VUE2_LIFECYCLE | VUE3_LIFECYCLE | COMPOSITION_LIFECYCLE
    rows = db.query(Q("function_call_args").select("file", "callee_function"))

    for file, callee in rows:
        if callee in all_hooks:
            vue_files.add(file)

    return vue_files


def _find_dom_before_mount(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find DOM operations in hooks that run before mounting.

    DOM is not available in beforeCreate, created, or onBeforeMount.
    DOM operations in these hooks will fail or behave unexpectedly.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    file_calls: dict[str, list[tuple[int, str]]] = {}
    for file, line, callee in rows:
        if file not in vue_files:
            continue
        if file not in file_calls:
            file_calls[file] = []
        file_calls[file].append((line, callee))

    early_hooks = {"beforeCreate", "created", "onBeforeMount"}

    for file, calls in file_calls.items():
        for line, callee in calls:
            if callee not in early_hooks:
                continue

            for other_line, other_callee in calls:
                if other_line <= line or other_line > line + 20:
                    continue

                if other_callee in MOUNT_OPERATIONS:
                    findings.append(
                        StandardFinding(
                            rule_name="vue-dom-before-mount",
                            message=f"DOM operation '{other_callee}' in '{callee}' hook - DOM not available yet",
                            file_path=file,
                            line=other_line,
                            severity=Severity.HIGH,
                            category="vue-lifecycle",
                            confidence=Confidence.HIGH,
                            cwe_id="CWE-665",
                            snippet=f"{callee}() {{ ... {other_callee}() ... }}",
                        )
                    )

    return findings


def _find_missing_cleanup(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find resources created without cleanup.

    Subscriptions, event listeners, and observers created in lifecycle hooks
    must be cleaned up in unmount hooks to prevent memory leaks.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    file_calls: dict[str, list[tuple[int, str]]] = {}
    for file, line, callee in rows:
        if file not in vue_files:
            continue
        if file not in file_calls:
            file_calls[file] = []
        file_calls[file].append((line, callee))

    mount_hooks = {"mounted", "onMounted", "created"}

    for file, calls in file_calls.items():
        callee_set = {c for _, c in calls}

        has_cleanup = bool(callee_set & CLEANUP_FUNCTIONS)

        for line, callee in calls:
            if callee not in CLEANUP_REQUIRED:
                continue

            near_mount = False
            for other_line, other_callee in calls:
                if other_callee in mount_hooks and abs(other_line - line) <= 20:
                    near_mount = True
                    break

            if near_mount and not has_cleanup:
                findings.append(
                    StandardFinding(
                        rule_name="vue-missing-cleanup",
                        message=f"'{callee}' created in lifecycle hook without cleanup - memory leak",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="vue-memory-leak",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-401",
                        snippet=f"{callee}(...) // missing cleanup in onUnmounted",
                    )
                )

    return findings


def _find_wrong_data_fetch(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find data fetching in wrong lifecycle hooks.

    - Fetching in updated/onUpdated causes infinite loops
    - Fetching in beforeMount/onBeforeMount is suboptimal
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    file_calls: dict[str, list[tuple[int, str]]] = {}
    for file, line, callee in rows:
        if file not in vue_files:
            continue
        if file not in file_calls:
            file_calls[file] = []
        file_calls[file].append((line, callee))

    bad_hooks = {
        "beforeMount": ("use created/mounted instead", Severity.MEDIUM),
        "onBeforeMount": ("use onMounted instead", Severity.MEDIUM),
        "updated": ("causes infinite update loop", Severity.CRITICAL),
        "onUpdated": ("causes infinite update loop", Severity.CRITICAL),
    }

    for file, calls in file_calls.items():
        for line, callee in calls:
            if callee not in bad_hooks:
                continue

            suggestion, severity = bad_hooks[callee]

            for other_line, other_callee in calls:
                if other_line <= line or other_line > line + 20:
                    continue

                if other_callee in DATA_FETCH_OPS:
                    findings.append(
                        StandardFinding(
                            rule_name="vue-wrong-fetch-hook",
                            message=f"Data fetch '{other_callee}' in '{callee}' - {suggestion}",
                            file_path=file,
                            line=other_line,
                            severity=severity,
                            category="vue-lifecycle",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-665",
                            snippet=f"{callee}() {{ ... {other_callee}() ... }}",
                        )
                    )

    return findings


def _find_infinite_updates(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find potential infinite update loops.

    Modifying reactive state in updated/onUpdated causes the component
    to re-render, triggering the update hook again in an infinite loop.
    """
    findings = []

    if not vue_files:
        return findings

    call_rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    file_calls: dict[str, list[tuple[int, str]]] = {}
    for file, line, callee in call_rows:
        if file not in vue_files:
            continue
        if file not in file_calls:
            file_calls[file] = []
        file_calls[file].append((line, callee))

    assignment_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var")
        .where("target_var IS NOT NULL")
        .order_by("file, line")
    )

    file_assignments: dict[str, list[tuple[int, str]]] = {}
    for file, line, target in assignment_rows:
        if file not in vue_files:
            continue
        if file not in file_assignments:
            file_assignments[file] = []
        file_assignments[file].append((line, target))

    update_hooks = {"beforeUpdate", "updated", "onBeforeUpdate", "onUpdated"}
    reactive_prefixes = ("this.", "data.", "state.")

    for file, calls in file_calls.items():
        assignments = file_assignments.get(file, [])

        for hook_line, hook in calls:
            if hook not in update_hooks:
                continue

            for assign_line, target in assignments:
                if assign_line <= hook_line or assign_line > hook_line + 20:
                    continue

                is_options_mutation = target.startswith(reactive_prefixes)
                is_ref_mutation = ".value" in target

                if is_options_mutation or is_ref_mutation:
                    findings.append(
                        StandardFinding(
                            rule_name="vue-infinite-update",
                            message=f"Modifying '{target}' in '{hook}' causes infinite update loop",
                            file_path=file,
                            line=assign_line,
                            severity=Severity.CRITICAL,
                            category="vue-lifecycle",
                            confidence=Confidence.HIGH,
                            cwe_id="CWE-835",
                            snippet=f"{hook}() {{ ... {target} = ... }}",
                        )
                    )

    return findings


def _find_timer_leaks(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find timers without cleanup.

    setInterval and setTimeout should be stored in a variable
    so they can be cleared in unmount hooks.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    timer_calls: list[tuple[str, int, str]] = []
    for file, line, callee in rows:
        if file not in vue_files:
            continue
        if callee in ("setInterval", "setTimeout"):
            timer_calls.append((file, line, callee))

    assignment_rows = db.query(
        Q("assignments").select("file", "line", "target_var").where("target_var IS NOT NULL")
    )

    assignments: dict[tuple[str, int], str] = {}
    for file, line, target in assignment_rows:
        assignments[(file, line)] = target

    for file, line, timer_func in timer_calls:
        target = assignments.get((file, line))

        has_timer_var = False
        if target:
            target_lower = target.lower()
            if any(kw in target_lower for kw in ("timer", "interval", "timeout", "id")):
                has_timer_var = True

        if not has_timer_var:
            findings.append(
                StandardFinding(
                    rule_name="vue-timer-leak",
                    message=f"'{timer_func}' not stored for cleanup - will leak if component unmounts",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="vue-memory-leak",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-401",
                    snippet=f"{timer_func}(...) // should be: const timerId = {timer_func}(...)",
                )
            )

    return findings


def _find_computed_side_effects(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find side effects in computed properties.

    Computed properties should be pure functions without side effects.
    Side effects break Vue's reactivity tracking and caching.
    """
    findings = []

    if not vue_files:
        return findings

    symbol_rows = db.query(Q("symbols").select("path", "line", "name").where("name IS NOT NULL"))

    computed_locations: list[tuple[str, int, str]] = []
    for path, line, name in symbol_rows:
        if path not in vue_files:
            continue
        if "computed" in name.lower():
            computed_locations.append((path, line, name))

    call_rows = db.query(Q("function_call_args").select("file", "line", "callee_function"))

    file_calls: dict[str, list[tuple[int, str]]] = {}
    for file, line, callee in call_rows:
        if file not in vue_files:
            continue
        if file not in file_calls:
            file_calls[file] = []
        file_calls[file].append((line, callee))

    for file, computed_line, _name in computed_locations:
        calls = file_calls.get(file, [])

        for call_line, callee in calls:
            if call_line <= computed_line or call_line > computed_line + 10:
                continue

            if callee in SIDE_EFFECTS:
                findings.append(
                    StandardFinding(
                        rule_name="vue-computed-side-effect",
                        message=f"Side effect '{callee}' in computed property - breaks reactivity caching",
                        file_path=file,
                        line=call_line,
                        severity=Severity.HIGH,
                        category="vue-antipattern",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1061",
                        snippet=f"computed: {{ ... {callee}(...) ... }}",
                    )
                )

    return findings


def _find_incorrect_hook_order(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find incorrect lifecycle hook ordering.

    Hooks should be declared in lifecycle order for readability
    and to match execution order.
    """
    findings = []

    if not vue_files:
        return findings

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

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    file_hooks: dict[str, list[tuple[int, str, int]]] = {}
    for file, line, callee in rows:
        if file not in vue_files:
            continue
        if callee in hook_order:
            if file not in file_hooks:
                file_hooks[file] = []
            file_hooks[file].append((line, callee, hook_order[callee]))

    for file, hooks in file_hooks.items():
        hooks.sort(key=lambda x: x[0])

        for i in range(len(hooks) - 1):
            current_line, current_hook, current_order = hooks[i]
            _next_line, next_hook, next_order = hooks[i + 1]

            if current_order > next_order:
                findings.append(
                    StandardFinding(
                        rule_name="vue-hook-order",
                        message=f"'{current_hook}' declared after '{next_hook}' - should follow lifecycle order",
                        file_path=file,
                        line=current_line,
                        severity=Severity.MEDIUM,
                        category="vue-lifecycle",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-665",
                        snippet=f"// {current_hook} should come before {next_hook}",
                    )
                )

    return findings


def _find_unhandled_async(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find async operations without error handling in lifecycle hooks.

    Async operations in lifecycle hooks should have proper error handling
    to prevent unhandled promise rejections.
    """
    findings = []

    if not vue_files:
        return findings

    all_hooks = VUE2_LIFECYCLE | VUE3_LIFECYCLE | COMPOSITION_LIFECYCLE
    async_operations = {"fetch", "axios", "Promise"}
    error_handlers = {"catch", "finally", "try"}

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    file_calls: dict[str, list[tuple[int, str]]] = {}
    for file, line, callee in rows:
        if file not in vue_files:
            continue
        if file not in file_calls:
            file_calls[file] = []
        file_calls[file].append((line, callee))

    for file, calls in file_calls.items():
        callee_set = {c for _, c in calls}

        has_error_handling = bool(callee_set & error_handlers)

        for line, callee in calls:
            if callee not in all_hooks:
                continue

            has_async = False
            for other_line, other_callee in calls:
                if other_line <= line or other_line > line + 20:
                    continue
                if other_callee in async_operations:
                    has_async = True
                    break

            if has_async and not has_error_handling:
                findings.append(
                    StandardFinding(
                        rule_name="vue-unhandled-async",
                        message=f"Async operation in '{callee}' without error handling - add try/catch or .catch()",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="vue-error-handling",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-248",
                        snippet=f"{callee}() {{ await fetch(...) }} // add try/catch",
                    )
                )

    return findings
