"""Vue Composition API Hooks Analyzer - Fidelity Layer Implementation.

Detects Vue Composition API misuse patterns:
- Hooks called outside setup() context
- Missing cleanup in lifecycle hooks (memory leaks)
- Watch/watchEffect without stop handle
- Deep watchers performance impact
- Ref/reactive in loops
- Incorrect lifecycle hook ordering
- Excessive reactivity declarations
- Missing error boundaries
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
    name="vue_hooks",
    category="vue",
    target_extensions=[".vue", ".js", ".ts", ".jsx", ".tsx"],
    target_file_patterns=[
        "frontend/",
        "client/",
        "src/components/",
        "src/composables/",
        "src/hooks/",
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


REACTIVITY_FUNCTIONS = frozenset(
    [
        "ref",
        "reactive",
        "computed",
        "readonly",
        "shallowRef",
        "shallowReactive",
        "shallowReadonly",
        "toRef",
        "toRefs",
        "isRef",
        "isReactive",
        "isReadonly",
        "isProxy",
    ]
)


WATCH_FUNCTIONS = frozenset(
    [
        "watch",
        "watchEffect",
        "watchPostEffect",
        "watchSyncEffect",
    ]
)


SETUP_ONLY_FUNCTIONS = frozenset(
    [
        "useStore",
        "useRouter",
        "useRoute",
        "useMeta",
        "useHead",
        "useI18n",
        "useNuxt",
        "useFetch",
    ]
)


MEMORY_LEAK_PATTERNS = frozenset(
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
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue Composition API hooks misuse and issues."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        vue_files = _get_composition_api_files(db)
        if not vue_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_find_hooks_outside_setup(db, vue_files))
        findings.extend(_find_missing_cleanup(db, vue_files))
        findings.extend(_find_watch_issues(db, vue_files))
        findings.extend(_find_memory_leaks(db, vue_files))
        findings.extend(_find_incorrect_hook_order(db, vue_files))
        findings.extend(_find_excessive_reactivity(db, vue_files))
        findings.extend(_find_missing_error_boundaries(db, vue_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_composition_api_files(db: RuleDB) -> set[str]:
    """Get all files using Vue Composition API."""
    vue_files: set[str] = set()

    rows = db.query(Q("symbols").select("path", "name").where("name IS NOT NULL"))

    vue_patterns = ("ref", "reactive", "computed", "watch", "setup")
    for path, name in rows:
        name_lower = name.lower()
        if "vue" in name_lower and any(pattern in name_lower for pattern in vue_patterns):
            vue_files.add(path)

    rows = db.query(Q("function_call_args").select("file", "callee_function"))

    comp_api_funcs = COMPOSITION_LIFECYCLE | REACTIVITY_FUNCTIONS | WATCH_FUNCTIONS
    for file, callee in rows:
        if callee in comp_api_funcs:
            vue_files.add(file)

    return vue_files


def _find_hooks_outside_setup(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find Composition API hooks called outside setup().

    Lifecycle hooks and composables must be called synchronously
    during setup() or inside other composables.
    """
    findings = []

    if not vue_files:
        return findings

    setup_only = SETUP_ONLY_FUNCTIONS | COMPOSITION_LIFECYCLE

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function")
        .order_by("file, line")
    )

    for file, line, hook, caller_context in rows:
        if file not in vue_files:
            continue

        if hook not in setup_only:
            continue

        if caller_context and "setup" in caller_context.lower():
            continue

        if not caller_context and file.endswith(".vue"):
            continue

        if hook in COMPOSITION_LIFECYCLE:
            message = f"Lifecycle hook '{hook}' must be called synchronously in setup()"
            severity = Severity.HIGH
        else:
            message = f"Composable '{hook}' should be called in setup() context"
            severity = Severity.MEDIUM

        findings.append(
            StandardFinding(
                rule_name="vue-hook-outside-setup",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="vue-composition-api",
                confidence=Confidence.MEDIUM if caller_context else Confidence.LOW,
                cwe_id="CWE-665",
                snippet=f"{hook}(...)",
            )
        )

    return findings


def _find_missing_cleanup(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find lifecycle hooks with missing cleanup.

    onMounted/onActivated that create subscriptions should have
    corresponding onUnmounted/onDeactivated cleanup.
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

    mount_hooks = ("onMounted", "onActivated")
    cleanup_hooks = ("onUnmounted", "onDeactivated", "onBeforeUnmount")

    for file, calls in file_calls.items():
        for line, callee in calls:
            if callee not in mount_hooks:
                continue

            has_leak_pattern = False
            for other_line, other_callee in calls:
                if other_callee in MEMORY_LEAK_PATTERNS and abs(other_line - line) <= 20:
                    has_leak_pattern = True
                    break

            if not has_leak_pattern:
                continue

            has_cleanup = False
            for other_line, other_callee in calls:
                if other_callee in cleanup_hooks and other_line > line:
                    has_cleanup = True
                    break

            if not has_cleanup:
                findings.append(
                    StandardFinding(
                        rule_name="vue-missing-cleanup",
                        message=f"'{callee}' creates subscriptions but no cleanup hook found (memory leak)",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="vue-memory-leak",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-401",
                        snippet=f"{callee}(() => {{ ... addEventListener/setInterval ... }})",
                    )
                )

    return findings


def _find_watch_issues(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find watch/watchEffect issues.

    - Watchers without stop handle (memory leak on component unmount)
    - Deep watchers on large objects (performance impact)
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    watch_calls: list[tuple[str, int, str, str | None]] = []
    for file, line, callee, args in rows:
        if file not in vue_files:
            continue
        if callee in WATCH_FUNCTIONS:
            watch_calls.append((file, line, callee, args))

    assignment_rows = db.query(
        Q("assignments").select("file", "line", "target_var").where("target_var IS NOT NULL")
    )

    assignments: dict[tuple[str, int], str] = {}
    for file, line, target in assignment_rows:
        assignments[(file, line)] = target

    for file, line, watch_func, args in watch_calls:
        target = assignments.get((file, line))
        if not target or "stop" not in target.lower():
            findings.append(
                StandardFinding(
                    rule_name="vue-watch-no-stop",
                    message=f"'{watch_func}' return value not captured - cannot stop watcher (memory leak risk)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="vue-memory-leak",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-401",
                    snippet=f"{watch_func}(...) // missing: const stop = {watch_func}(...)",
                )
            )

        if args and "deep: true" in args:
            findings.append(
                StandardFinding(
                    rule_name="vue-deep-watch",
                    message=f"Deep watcher in '{watch_func}' - significant performance impact on large objects",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="vue-performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1050",
                    snippet=f"{watch_func}(..., {{ deep: true }})",
                )
            )

    return findings


def _find_memory_leaks(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find potential memory leaks from refs/reactive.

    - Large objects in ref/reactive (performance overhead)
    - ref/reactive created in loops (memory leak)
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    ref_calls: list[tuple[str, int, str]] = []
    for file, line, callee, args in rows:
        if file not in vue_files:
            continue

        if callee in ("ref", "reactive"):
            ref_calls.append((file, line, callee))

            if args and len(args) > 500:
                findings.append(
                    StandardFinding(
                        rule_name="vue-large-reactive",
                        message=f"Large object passed to '{callee}' - consider shallowRef/shallowReactive for performance",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="vue-performance",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1050",
                        snippet=f"{callee}({{ /* large object */ }})",
                    )
                )

    loop_rows = db.query(
        Q("cfg_blocks")
        .select("file", "block_type", "start_line", "end_line")
        .where("block_type IS NOT NULL")
    )

    loop_blocks: list[tuple[str, int, int]] = []
    for file, block_type, start, end in loop_rows:
        if file in vue_files and block_type and "loop" in block_type.lower():
            loop_blocks.append((file, start, end))

    for file, line, func in ref_calls:
        for loop_file, start, end in loop_blocks:
            if loop_file == file and start <= line <= end:
                findings.append(
                    StandardFinding(
                        rule_name="vue-ref-in-loop",
                        message=f"'{func}' created inside loop - creates new reactive object each iteration (memory leak)",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="vue-memory-leak",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-401",
                        snippet=f"for (...) {{ {func}(...) }} // move outside loop",
                    )
                )
                break

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
        "onBeforeMount": 1,
        "onMounted": 2,
        "onBeforeUpdate": 3,
        "onUpdated": 4,
        "onBeforeUnmount": 5,
        "onUnmounted": 6,
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
                        category="vue-composition-api",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-665",
                        snippet=f"// Wrong: {current_hook} before {next_hook}",
                    )
                )

    return findings


def _find_excessive_reactivity(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find excessive use of reactivity primitives.

    Too many reactive declarations in a single file suggests
    the component should be split or use a state management solution.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(Q("function_call_args").select("file", "callee_function"))

    file_counts: dict[str, int] = {}
    for file, callee in rows:
        if file not in vue_files:
            continue
        if callee in ("ref", "reactive", "computed"):
            file_counts[file] = file_counts.get(file, 0) + 1

    for file, count in file_counts.items():
        if count > 50:
            findings.append(
                StandardFinding(
                    rule_name="vue-excessive-reactivity",
                    message=f"File has {count} reactive declarations - consider splitting component or using Pinia",
                    file_path=file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="vue-performance",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-1050",
                )
            )

    return findings


def _find_missing_error_boundaries(db: RuleDB, vue_files: set[str]) -> list[StandardFinding]:
    """Find complex components without error handling.

    Components with multiple async hooks should have onErrorCaptured
    to prevent errors from propagating unhandled.
    """
    findings = []

    if not vue_files:
        return findings

    rows = db.query(Q("function_call_args").select("file", "callee_function"))

    file_hooks: dict[str, set[str]] = {}
    for file, callee in rows:
        if file not in vue_files:
            continue
        if callee in ("onMounted", "onUpdated", "watchEffect", "onErrorCaptured"):
            if file not in file_hooks:
                file_hooks[file] = set()
            file_hooks[file].add(callee)

    async_hooks = {"onMounted", "onUpdated", "watchEffect"}
    for file, hooks in file_hooks.items():
        async_hook_count = len(hooks & async_hooks)
        has_error_handler = "onErrorCaptured" in hooks

        if async_hook_count > 3 and not has_error_handler:
            findings.append(
                StandardFinding(
                    rule_name="vue-no-error-boundary",
                    message="Complex component with multiple async hooks but no onErrorCaptured - errors may propagate silently",
                    file_path=file,
                    line=1,
                    severity=Severity.LOW,
                    category="vue-error-handling",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-248",
                )
            )

    return findings
