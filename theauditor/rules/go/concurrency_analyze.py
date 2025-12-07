"""Go Concurrency Issue Analyzer.

Detects common Go concurrency bugs:
1. Captured loop variables in goroutines (data race) - CRITICAL
2. Package-level variable access from goroutines without sync - HIGH
3. Multiple goroutines without synchronization primitives - MEDIUM
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
    name="go_concurrency",
    category="concurrency",
    target_extensions=[".go"],
    exclude_patterns=[
        "vendor/",
        "node_modules/",
        "testdata/",
        "_test.go",
    ],
    execution_scope="database",
    primary_table="go_captured_vars",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Go concurrency issues.

    Args:
        context: Provides db_path and project context

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_captured_loop_variables(db))
        findings.extend(_check_package_var_goroutine_access(db))
        findings.extend(_check_goroutine_without_sync(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_captured_loop_variables(db: RuleDB) -> list[StandardFinding]:
    """CRITICAL: Detect captured loop variables in goroutines.

    This is the #1 source of data races in Go code:

        for i, v := range items {
            go func() {
                process(v)  // v is captured - RACE CONDITION!
            }()
        }

    HIGH CONFIDENCE because:
    1. go_captured_vars filters to anonymous goroutines
    2. is_loop_var is set by walking up to enclosing for/range
    3. This pattern is almost always a bug
    """
    findings = []

    rows = db.query(
        Q("go_captured_vars")
        .select("file", "line", "goroutine_id", "var_name")
        .where("is_loop_var = ?", 1)
        .order_by("file, line")
    )

    for file_path, line, goroutine_id, var_name in rows:
        findings.append(
            StandardFinding(
                rule_name="go-race-captured-loop-var",
                message=f"Loop variable '{var_name}' captured in goroutine - data race",
                file_path=file_path,
                line=line,
                severity=Severity.CRITICAL,
                category="concurrency",
                confidence=Confidence.HIGH,
                cwe_id="CWE-362",
                additional_info={
                    "goroutine_id": goroutine_id,
                    "var_name": var_name,
                    "fix": f"Pass '{var_name}' as parameter: go func({var_name} T) {{ ... }}({var_name})",
                },
            )
        )

    return findings


def _check_package_var_goroutine_access(db: RuleDB) -> list[StandardFinding]:
    """Detect goroutines accessing package-level variables without sync."""
    findings = []

    pkg_var_rows = db.query(
        Q("go_variables").select("file", "name").where("is_package_level = ?", 1)
    )

    pkg_vars: dict[str, set[str]] = {}
    for file_path, name in pkg_var_rows:
        if file_path not in pkg_vars:
            pkg_vars[file_path] = set()
        pkg_vars[file_path].add(name)

    if not pkg_vars:
        return findings

    goroutine_rows = db.query(
        Q("go_goroutines")
        .select("file", "line", "containing_func")
        .where("is_anonymous = ?", 1)
    )

    for file_path, line, _containing_func in goroutine_rows:
        if file_path not in pkg_vars:
            continue

        struct_mutex_rows = db.query(
            Q("go_struct_fields")
            .select("file")
            .where("file = ?", file_path)
            .where("field_type LIKE ? OR field_type LIKE ?", "%sync.Mutex%", "%sync.RWMutex%")
            .limit(1)
        )
        has_struct_mutex = len(list(struct_mutex_rows)) > 0

        global_mutex_rows = db.query(
            Q("go_variables")
            .select("file")
            .where("file = ?", file_path)
            .where("is_package_level = ?", 1)
            .where(
                "type LIKE ? OR type LIKE ? OR initial_value LIKE ? OR initial_value LIKE ?",
                "%sync.Mutex%",
                "%sync.RWMutex%",
                "%sync.Mutex%",
                "%sync.RWMutex%",
            )
            .limit(1)
        )
        has_global_mutex = len(list(global_mutex_rows)) > 0

        if has_struct_mutex or has_global_mutex:
            continue

        captured_rows = db.query(
            Q("go_captured_vars")
            .select("var_name")
            .where("file = ?", file_path)
            .where("line = ?", line)
        )

        captured = {var_name for (var_name,) in captured_rows}
        pkg_var_access = captured.intersection(pkg_vars[file_path])

        for var_name in pkg_var_access:
            findings.append(
                StandardFinding(
                    rule_name="go-race-pkg-var",
                    message=f"Package variable '{var_name}' accessed in goroutine without visible sync",
                    file_path=file_path,
                    line=line,
                    severity=Severity.HIGH,
                    category="concurrency",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-362",
                )
            )

    return findings


def _check_goroutine_without_sync(db: RuleDB) -> list[StandardFinding]:
    """Detect files with multiple goroutines but no sync primitives."""
    findings = []

    goroutine_count_rows = db.query(
        Q("go_goroutines").select("file", "COUNT(*) as goroutine_count").group_by("file")
    )

    multi_goroutine_files: dict[str, int] = {}
    for file_path, count in goroutine_count_rows:
        if count >= 2:
            multi_goroutine_files[file_path] = count

    for file_path, count in multi_goroutine_files.items():
        sync_import_rows = db.query(
            Q("go_imports")
            .select("path")
            .where("file = ?", file_path)
            .where("path = ? OR path = ?", "sync", "sync/atomic")
            .limit(1)
        )
        has_sync_import = len(list(sync_import_rows)) > 0

        channel_rows = db.query(
            Q("go_channels").select("file").where("file = ?", file_path).limit(1)
        )
        has_channels = len(list(channel_rows)) > 0

        if not has_sync_import and not has_channels:
            findings.append(
                StandardFinding(
                    rule_name="go-goroutines-no-sync",
                    message=f"File has {count} goroutines but no sync primitives or channels",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="concurrency",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-362",
                    additional_info={
                        "goroutine_count": count,
                        "suggestion": "Consider using sync.Mutex, sync.WaitGroup, or channels for coordination",
                    },
                )
            )

    return findings
