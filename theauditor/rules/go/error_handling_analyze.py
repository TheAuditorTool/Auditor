"""Go Error Handling Analyzer.

Detects common Go error handling anti-patterns:
1. Ignored errors via blank identifier (_ = func()) - CWE-391
2. Panic in library code (non-main packages) - CWE-248
3. Type assertions without recover - CWE-248
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
    name="go_error_handling",
    category="error_handling",
    target_extensions=[".go"],
    exclude_patterns=[
        "vendor/",
        "node_modules/",
        "testdata/",
        "_test.go",
    ],
    execution_scope="database",
    primary_table="go_variables",
)


ERROR_RETURNING_FUNCS = frozenset(
    {
        "Close",
        "Write",
        "Read",
        "Scan",
        "Exec",
        "Query",
        "QueryRow",
        "Prepare",
        "Begin",
        "Commit",
        "Rollback",
        "Marshal",
        "Unmarshal",
        "Decode",
        "Encode",
        "Parse",
        "Open",
        "Create",
        "Remove",
        "Rename",
        "Mkdir",
    }
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Go error handling issues.

    Args:
        context: Provides db_path and project context

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_ignored_errors(db))
        findings.extend(_check_panic_in_library(db))
        findings.extend(_check_defer_without_recover(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_ignored_errors(db: RuleDB) -> list[StandardFinding]:
    """Detect ignored errors via blank identifier assignment.

    Pattern: _ = someFunc() where someFunc returns error.
    This is a common and dangerous anti-pattern in Go code.

    Note: Fire-and-forget calls (e.g., db.Close() without assignment)
    require go_expression_statements table which needs Go extractor enhancement.
    """
    findings = []

    blank_rows = db.query(
        Q("go_variables")
        .select("file", "line", "name", "initial_value")
        .where("name = ?", "_")
        .where("initial_value IS NOT NULL")
        .where("initial_value != ?", "")
    )

    for file_path, line, _name, initial_value in blank_rows:
        initial_value = initial_value or ""

        if "(" not in initial_value or ")" not in initial_value:
            continue

        func_name = initial_value.split("(")[0].strip()
        if "." in func_name:
            func_name = func_name.split(".")[-1]

        error_return_rows = db.query(
            Q("go_error_returns")
            .select("func_name")
            .where("func_name = ?", func_name)
            .where("returns_error = ?", 1)
            .limit(1)
        )
        returns_error = len(list(error_return_rows)) > 0

        if returns_error or func_name in ERROR_RETURNING_FUNCS:
            findings.append(
                StandardFinding(
                    rule_name="go-ignored-error",
                    message=f"Error ignored via blank identifier: _ = {initial_value}",
                    file_path=file_path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="error_handling",
                    confidence=Confidence.HIGH if returns_error else Confidence.MEDIUM,
                    cwe_id="CWE-391",
                    additional_info={
                        "ignored_call": initial_value,
                        "suggestion": "Handle or explicitly document why error is ignored",
                    },
                )
            )

    return findings


def _check_panic_in_library(db: RuleDB) -> list[StandardFinding]:
    """Detect process termination in non-main packages.

    Libraries should return errors, not terminate the process.
    Detects: panic(), log.Fatal(), log.Panic()
    """
    findings = []

    lib_package_rows = db.query(Q("go_packages").select("file").where("name != ?", "main"))
    library_files = {file_path for (file_path,) in lib_package_rows}

    if not library_files:
        return findings

    termination_rows = db.query(
        Q("go_variables")
        .select("file", "line", "initial_value")
        .where(
            "initial_value LIKE ? OR initial_value LIKE ? OR initial_value LIKE ?",
            "%panic(%",
            "%log.Fatal%",
            "%log.Panic%",
        )
    )

    for file_path, line, initial_value in termination_rows:
        if file_path not in library_files:
            continue

        value = initial_value or ""
        if "panic(" in value:
            term_type = "panic()"
        elif "log.Fatal" in value:
            term_type = "log.Fatal()"
        else:
            term_type = "log.Panic()"

        findings.append(
            StandardFinding(
                rule_name="go-termination-in-library",
                message=f"{term_type} in library code terminates process - return error instead",
                file_path=file_path,
                line=line,
                severity=Severity.MEDIUM,
                category="error_handling",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-248",
            )
        )

    defer_termination_rows = db.query(
        Q("go_defer_statements")
        .select("file", "line", "deferred_expr")
        .where(
            "deferred_expr LIKE ? OR deferred_expr LIKE ? OR deferred_expr LIKE ?",
            "%panic(%",
            "%log.Fatal%",
            "%log.Panic%",
        )
    )

    for file_path, line, deferred_expr in defer_termination_rows:
        if file_path not in library_files:
            continue

        expr = deferred_expr or ""
        if "panic(" in expr:
            term_type = "panic()"
        elif "log.Fatal" in expr:
            term_type = "log.Fatal()"
        else:
            term_type = "log.Panic()"

        findings.append(
            StandardFinding(
                rule_name="go-termination-in-library-defer",
                message=f"{term_type} in deferred function in library code",
                file_path=file_path,
                line=line,
                severity=Severity.MEDIUM,
                category="error_handling",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-248",
            )
        )

    return findings


def _check_defer_without_recover(db: RuleDB) -> list[StandardFinding]:
    """Detect type assertions without recover().

    Type assertions without comma-ok pattern can panic.
    Files with type assertions but no recover() are at risk.
    """
    findings = []

    defer_file_rows = db.query(Q("go_defer_statements").select("file"))
    files_with_defer = {file_path for (file_path,) in defer_file_rows}

    for file_path in files_with_defer:
        recover_rows = db.query(
            Q("go_defer_statements")
            .select("file")
            .where("file = ?", file_path)
            .where("deferred_expr LIKE ?", "%recover()%")
            .limit(1)
        )
        has_recover = len(list(recover_rows)) > 0

        if has_recover:
            continue

        type_assert_rows = db.query(
            Q("go_type_assertions")
            .select("file")
            .where("file = ?", file_path)
            .where("is_type_switch = ?", 0)
            .limit(1)
        )
        has_type_assertions = len(list(type_assert_rows)) > 0

        if has_type_assertions:
            findings.append(
                StandardFinding(
                    rule_name="go-type-assertion-no-recover",
                    message="Type assertions without recover() - may panic",
                    file_path=file_path,
                    line=1,
                    severity=Severity.LOW,
                    category="error_handling",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-248",
                    additional_info={
                        "suggestion": "Use comma-ok pattern: v, ok := x.(T)",
                    },
                )
            )

    return findings
